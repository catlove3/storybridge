from __future__ import annotations

import difflib
from pathlib import Path

from app.schemas import StoryState
from app.storage import ProjectStore
from app.workflow.engine import StoryBridgeWorkflow


def unified_scene_diff(old_text: str, new_text: str, scene_id: str) -> list[str]:
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"{scene_id} (before)",
        tofile=f"{scene_id} (after)",
    )
    return [line.rstrip("\n") for line in diff]


def changed_scenes_diff(store: ProjectStore, project_id: str) -> list[dict]:
    revisions = store.list_revisions(project_id)
    state = store.load_state(project_id)
    if state is None or not revisions:
        return []

    baseline_rev = next(
        (r for r in revisions if r.kind == "initial_parse"), revisions[0]
    )
    baseline_path = (
        store._dir(project_id) / "history" / f"rev{baseline_rev.revision_id:03d}.json"
    )
    import json

    if not baseline_path.exists():
        return []
    baseline_state = StoryState.model_validate(
        json.loads(baseline_path.read_text(encoding="utf-8"))
    )

    diffs: list[dict] = []
    for scene in state.scenes:
        old = next((s for s in baseline_state.scenes if s.id == scene.id), None)
        if old is None or old.text == scene.text:
            continue
        diffs.append(
            {
                "scene_id": scene.id,
                "before": old.text,
                "after": scene.text,
                "diff": unified_scene_diff(old.text, scene.text, scene.id),
            }
        )
    return diffs


def export_bible(workflow: StoryBridgeWorkflow, project_id: str, out_path: Path) -> Path:
    store = workflow.store
    meta = store.load_meta(project_id)
    state = store.load_state(project_id)
    if meta is None or state is None:
        raise KeyError(f"unknown project or no state: {project_id}")

    lines: list[str] = ["# Adaptation Bible", ""]
    lines += [f"PROJECT: {meta.name or project_id}", ""]
    lines += [
        "## TARGET",
        f"- Market: {state.target_market or 'N/A'}",
        f"- Audience: {state.audience or 'N/A'}",
        f"- Format: {state.format or 'N/A'}",
        f"- Genre: {state.genre or 'N/A'}",
        "",
    ]

    lines += ["## CORE NARRATIVE COMMITMENTS", ""]
    for nc in state.commitments:
        flag = "MUST-PRESERVE" if nc.must_preserve else "OPTIONAL"
        lines.append(
            f"- {nc.id} [{flag}]: {nc.description}"
            f"（established {nc.established_at_scene_id or '?'}, payoff {nc.payoff_scene_id or '?'}）"
        )
    lines.append("")

    lines += ["## CULTURE MECHANISMS", ""]
    for cm in state.culture_mechanisms:
        lines.append(f"### {cm.id} {cm.name}")
        lines.append(f"- Friction: {cm.friction_level.value}")
        lines.append(f"- Importance: {cm.narrative_importance.value}")
        lines.append(f"- Scenes: {', '.join(cm.scene_ids) or 'N/A'}")
        if cm.adapted_to:
            lines.append(f"- Adapted to: {cm.adapted_to}")
            lines.append(f"- Strategy: {cm.adapted_strategy}")
        else:
            lines.append("- Adapted to: (未改编)")
        lines.append("")

    lines += ["## APPLIED ADAPTATIONS", ""]
    for applied in store.load_applied(project_id):
        option = applied.chosen_option
        affected = ", ".join(
            a.scene_id for a in applied.propagation.affected_scenes
        )
        lines += [
            f"### {applied.plan_culture_mechanism_id} -> Option {option.option_label}",
            f"- Title: {option.title}",
            f"- Strategy: {option.strategy.value}",
            f"- Replacement: {option.replacement_definition}",
            f"- Affected scenes: {affected}",
            f"- Rewritten: {', '.join(applied.rewritten_scene_ids)}",
            "",
        ]

    lines += ["## REVISION HISTORY", ""]
    for rev in store.list_revisions(project_id):
        lines.append(
            f"- rev{rev.revision_id:03d} [{rev.kind}] {rev.description} "
            f"changed={rev.changed_scene_ids or '[]'}"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
