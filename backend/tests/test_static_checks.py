from __future__ import annotations

from app.schemas import StoryState
from app.workflow.static_checks import (
    check_reconstructed_dependency_chains,
    check_stale_references,
    check_uncovered_commitments,
    run_static_checks,
)


def _state_with_stale(state_dict) -> StoryState:
    state = StoryState.model_validate(state_dict)
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    cm01.adapted_to = "stable career track in a legacy firm"
    return state


def test_no_stale_when_not_adapted(state_dict):
    state = StoryState.model_validate(state_dict)
    assert check_stale_references(state) == []


def test_detects_stale_reference_after_adaptation(state_dict):
    state = _state_with_stale(state_dict)
    issues = check_stale_references(state)
    scene_ids = {i.scene_id for i in issues}
    assert scene_ids == {"S01", "S02", "S05", "S06"}
    assert all(i.severity.value == "error" for i in issues)
    assert all(i.issue_type.value == "stale_reference" for i in issues)


def test_stale_cleared_when_scene_rewritten(state_dict):
    state = _state_with_stale(state_dict)
    for scene_id in ("S01", "S02", "S05", "S06"):
        scene = state.scene_by_id(scene_id)
        scene.text = scene.text.replace("编制", "tenure-track").replace("单位", "firm")
        scene.summary = scene.summary.replace("编制", "tenure-track").replace("单位", "firm")
    issues = check_stale_references(state)
    assert issues == []


def test_preserve_strategy_allows_original_term(state_dict):
    state = _state_with_stale(state_dict)
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    cm01.adapted_strategy = "preserve"

    assert check_stale_references(state) == []


def test_plot_reconstruction_flags_old_dependency_chain_for_review(state_dict):
    state = _state_with_stale(state_dict)
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    cm01.adapted_strategy = "plot_reconstruction"

    issues = check_reconstructed_dependency_chains(state)

    assert len(issues) == 1
    assert issues[0].severity.value == "warning"
    assert "CM01" in issues[0].evidence


def test_uncovered_commitment_missing_payoff_not_reported(state_dict):
    state = StoryState.model_validate(state_dict)
    state.commitments[0].payoff_scene_id = None
    issues = check_uncovered_commitments(state)
    assert issues == []


def test_uncovered_commitment_flags_broken_payoff(state_dict):
    state = StoryState.model_validate(state_dict)
    state.commitments[0].payoff_scene_id = "S99"
    issues = check_uncovered_commitments(state)
    assert issues[0].severity.value == "error"


def test_run_static_checks_combines(state_dict):
    state = _state_with_stale(state_dict)
    state.commitments[0].payoff_scene_id = None
    issues = run_static_checks(state)
    kinds = {i.issue_type.value for i in issues}
    assert kinds == {"stale_reference"}
