"""Freeze presentation-safe evidence from a completed StoryBridge project.

The SQLite database is intentionally ignored by Git. This script extracts only
the selected plan, propagation result, verification report, and repair history
needed to reproduce the three method evidence images.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "backend/data/storybridge.sqlite3"
OUTPUT = Path(__file__).resolve().parent / "evidence/method_evidence.json"
PROJECT_ID = "fde7ef149e074c4f95d696a88cc82dbc"
MECHANISM_ID = "CM01"


def load_json(value: str | None):
    return json.loads(value) if value else None


def main() -> None:
    connection = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    project = connection.execute(
        "SELECT name, created_at FROM projects WHERE id = ?", (PROJECT_ID,)
    ).fetchone()
    current_row = connection.execute(
        "SELECT version, payload_json, updated_at FROM states WHERE project_id = ?",
        (PROJECT_ID,),
    ).fetchone()
    original_row = connection.execute(
        "SELECT payload_json FROM state_history WHERE project_id = ? AND version = 1",
        (PROJECT_ID,),
    ).fetchone()
    plan_row = connection.execute(
        "SELECT payload_json FROM plans WHERE project_id = ? AND mechanism_id = ?",
        (PROJECT_ID, MECHANISM_ID),
    ).fetchone()
    report_row = connection.execute(
        "SELECT state_version, payload_json FROM verification_reports WHERE project_id = ?",
        (PROJECT_ID,),
    ).fetchone()
    if not all((project, current_row, original_row, plan_row, report_row)):
        raise RuntimeError("The frozen demonstration project is incomplete")

    current_state = load_json(current_row["payload_json"])
    original_state = load_json(original_row["payload_json"])
    plan = load_json(plan_row["payload_json"])
    mechanism = next(
        item for item in original_state["culture_mechanisms"] if item["id"] == MECHANISM_ID
    )

    adaptation = None
    for row in connection.execute(
        "SELECT payload_json FROM adaptations WHERE project_id = ? ORDER BY sequence_id",
        (PROJECT_ID,),
    ):
        candidate = load_json(row["payload_json"])
        if candidate["plan_culture_mechanism_id"] == MECHANISM_ID:
            adaptation = candidate
            break
    if adaptation is None:
        raise RuntimeError(f"No applied adaptation found for {MECHANISM_ID}")

    revisions = []
    for row in connection.execute(
        """
        SELECT revision_id, state_version, kind, description,
               changed_scene_ids_json, applied_option_json, created_at
          FROM revisions
         WHERE project_id = ?
         ORDER BY revision_id
        """,
        (PROJECT_ID,),
    ):
        applied = load_json(row["applied_option_json"])
        revisions.append(
            {
                "revision_id": row["revision_id"],
                "state_version": row["state_version"],
                "kind": row["kind"],
                "description": row["description"],
                "changed_scene_ids": load_json(row["changed_scene_ids_json"]),
                "repair_suggestion": (applied or {}).get("repair_suggestion"),
                "created_at": row["created_at"],
            }
        )

    payload = {
        "source": "real saved StoryBridge output",
        "project": {
            "name": project["name"],
            "created_at": project["created_at"],
            "original_state_version": 1,
            "current_state_version": current_row["version"],
            "updated_at": current_row["updated_at"],
        },
        "counts": {
            key: len(current_state[key])
            for key in (
                "characters",
                "scenes",
                "events",
                "settings",
                "culture_mechanisms",
                "commitments",
                "dependencies",
            )
        },
        "story_state": {
            "version": original_state["version"],
            "source_language": original_state["source_language"],
            "target_language": original_state["target_language"],
            "target_locale": original_state["target_locale"],
            "characters": original_state["characters"],
            "scenes": [
                {
                    "id": scene["id"],
                    "title": scene["title"],
                    "summary": scene["summary"],
                }
                for scene in original_state["scenes"]
            ],
            "settings": original_state["settings"],
            "culture_mechanisms": original_state["culture_mechanisms"],
            "commitments": original_state["commitments"],
        },
        "scene_titles": {
            scene["id"]: scene["title"] for scene in current_state["scenes"]
        },
        "culture_node": mechanism,
        "plan": plan,
        "selected_option": adaptation["chosen_option"],
        "propagation": adaptation["propagation"],
        "rewritten_scene_ids": adaptation["rewritten_scene_ids"],
        "verification": {
            "state_version": report_row["state_version"],
            **load_json(report_row["payload_json"]),
        },
        "revisions": revisions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
