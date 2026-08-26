from __future__ import annotations

import pytest

from app.graph import PropagationEngine, StoryGraph
from app.schemas import ImpactKind, StoryState


@pytest.fixture
def state(state_dict) -> StoryState:
    return StoryState.model_validate(state_dict)


def test_build_graph_nodes_and_edges(state):
    graph = StoryGraph(state)
    assert "CM01" in graph.graph
    assert "S08" in graph.graph
    assert graph.graph.number_of_edges() >= len(state.dependencies)


def test_find_affected_scenes_for_bianzhi(state):
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM01")
    affected_ids = {a.scene_id for a in result.affected_scenes}
    assert affected_ids == {"S01", "S02", "S05", "S06", "S08"}
    assert set(result.related_commitment_ids) == {"NC01", "NC02"}

    by_id = {a.scene_id: a for a in result.affected_scenes}
    assert ImpactKind.DIRECT_REFERENCE in by_id["S01"].impact_kinds
    assert ImpactKind.MOTIVATION in by_id["S02"].impact_kinds
    assert ImpactKind.PAYOFF in by_id["S08"].impact_kinds
    assert by_id["S05"].reason_path[0] == "CM01"


def test_find_affected_scenes_for_caili(state):
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM02")
    affected_ids = {a.scene_id for a in result.affected_scenes}
    assert affected_ids == {"S03", "S04", "S05", "S06", "S08"}
    assert set(result.related_commitment_ids) == {"NC03"}


def test_no_cross_propagation_from_985(state):
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM03")
    affected_ids = {a.scene_id for a in result.affected_scenes}
    assert affected_ids == {"S07"}


def test_unknown_node_raises(state):
    with pytest.raises(KeyError):
        PropagationEngine(StoryGraph(state)).find_affected_scenes("CM99")


def test_reason_paths_record_evidence(state):
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM01")
    s02 = next(a for a in result.affected_scenes if a.scene_id == "S02")
    assert "references" in s02.evidence or "motivates" in s02.evidence
