from __future__ import annotations

from app.baselines.metrics import (
    compute_scene_recall,
    count_stale_references,
    evaluate_output,
    format_metrics_table,
)
from app.schemas import StoryState


def test_count_stale_references(state_dict):
    original = StoryState.model_validate(state_dict)
    cm01 = next(m for m in original.culture_mechanisms if m.id == "CM01")
    cm01.adapted_to = "stable corporate career"

    adapted = "Scene 1: Her mother asks about his job stability...\nScene 5: 没有编制的人给不了安全感。"
    count, details = count_stale_references(original, adapted)
    assert count == 1
    assert "CM01" in details[0]

    clean = "Scene 1: job stability... Scene 5: A man without a secure career cannot promise safety."
    count2, _ = count_stale_references(original, clean)
    assert count2 == 0


def test_compute_scene_recall(state_dict):
    original = StoryState.model_validate(state_dict)
    output = StoryState.model_validate(state_dict)

    for sid in ("S01", "S02", "S05"):
        output.scene_by_id(sid).text = "rewritten text"

    expected = ["S01", "S02", "S05", "S06", "S08"]
    recall, changed = compute_scene_recall(expected, output, original)
    assert recall == 0.6
    assert set(changed) == {"S01", "S02", "S05"}


def test_evaluate_output_and_table(state_dict):
    original = StoryState.model_validate(state_dict)
    cm01 = next(m for m in original.culture_mechanisms if m.id == "CM01")
    cm01.adapted_to = "stable corporate career"

    output = StoryState.model_validate(state_dict)
    for sid in ("S01", "S02", "S05", "S06", "S08"):
        output.scene_by_id(sid).text = "rewritten"
    script = "\n".join(s.text for s in output.scenes)

    metrics = evaluate_output(
        original,
        output,
        script,
        "C StoryBridge",
        expected_affected_ids=["S01", "S02", "S05", "S06", "S08"],
        commitment_checks=[
            {"commitment_id": "NC01", "status": "preserved"},
            {"commitment_id": "NC02", "status": "preserved"},
            {"commitment_id": "NC03", "status": "violated"},
        ],
    )
    assert metrics.stale_reference_count == 0
    assert metrics.affected_scene_recall == 1.0
    assert metrics.commitment_preserved == 2
    assert metrics.commitment_total == 3

    table = format_metrics_table([metrics])
    assert "C StoryBridge" in table
    assert "2/3" in table
