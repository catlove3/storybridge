from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import AdaptationPlan, StoryState, TargetScript
from tests.fixtures import sample_story_state_dict


def _valid_option(label: str, strategy: str) -> dict:
    return {
        "option_label": label,
        "strategy": strategy,
        "title": f"option {label}",
        "replacement_definition": "replacement",
        "rationale": "rationale",
    }


def test_story_state_rejects_duplicate_node_ids():
    payload = sample_story_state_dict()
    payload["characters"].append(dict(payload["characters"][0]))

    with pytest.raises(ValidationError, match="duplicate node ids"):
        StoryState.model_validate(payload)


@pytest.mark.parametrize(
    ("collection", "field", "unknown_id"),
    [
        ("scenes", "character_ids", "C99"),
        ("scenes", "event_ids", "E99"),
        ("events", "scene_ids", "S99"),
        ("culture_mechanisms", "scene_ids", "S99"),
    ],
)
def test_story_state_rejects_dangling_nested_references(collection, field, unknown_id):
    payload = sample_story_state_dict()
    payload[collection][0][field] = [unknown_id]

    with pytest.raises(ValidationError, match="dangling references"):
        StoryState.model_validate(payload)


def test_story_state_rejects_dangling_commitment_scene():
    payload = sample_story_state_dict()
    payload["commitments"][0]["payoff_scene_id"] = "S99"

    with pytest.raises(ValidationError, match="dangling references"):
        StoryState.model_validate(payload)


def test_adaptation_plan_normalizes_and_orders_labels():
    plan = AdaptationPlan.model_validate(
        {
            "culture_mechanism_id": "CM01",
            "original_name": "编制",
            "options": [
                _valid_option("c", "plot_reconstruction"),
                _valid_option("a", "preserve"),
                _valid_option("b", "functional_replacement"),
            ],
        }
    )

    assert [option.option_label for option in plan.options] == ["A", "B", "C"]


def test_adaptation_plan_rejects_missing_or_duplicate_labels():
    with pytest.raises(ValidationError, match="exactly one option"):
        AdaptationPlan.model_validate(
            {
                "culture_mechanism_id": "CM01",
                "original_name": "编制",
                "options": [
                    _valid_option("A", "preserve"),
                    _valid_option("A", "preserve"),
                    _valid_option("C", "plot_reconstruction"),
                ],
            }
        )


def test_adaptation_plan_rejects_strategy_label_mismatch():
    with pytest.raises(ValidationError, match="option B must use strategy"):
        AdaptationPlan.model_validate(
            {
                "culture_mechanism_id": "CM01",
                "original_name": "编制",
                "options": [
                    _valid_option("A", "preserve"),
                    _valid_option("B", "plot_reconstruction"),
                    _valid_option("C", "functional_replacement"),
                ],
            }
        )


def test_target_script_rejects_blank_text_and_duplicate_scenes():
    payload = {
        "target_language": " English ",
        "scenes": [{"id": "S01", "text": "   "}],
    }
    with pytest.raises(ValidationError):
        TargetScript.model_validate(payload)

    payload["scenes"] = [
        {"id": "S01", "text": "one"},
        {"id": "S01", "text": "two"},
    ]
    with pytest.raises(ValidationError, match="scene ids must be unique"):
        TargetScript.model_validate(payload)
