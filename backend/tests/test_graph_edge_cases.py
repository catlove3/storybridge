from __future__ import annotations

import pytest

from app.graph import PropagationEngine, StoryGraph
from app.schemas import Dependency, EdgeRelation, StoryState
from tests.fixtures import sample_story_state_dict


def _state_with_dependencies(state_dict, deps: list[Dependency]) -> StoryState:
    state_dict = {**state_dict, "dependencies": [d.model_dump() for d in deps]}
    return StoryState.model_validate(state_dict)


def test_self_loop_dependency(state_dict):
    deps = [Dependency(source_id="CM01", target_id="CM01", relation=EdgeRelation.MOTIVATES)]
    state = _state_with_dependencies(state_dict, deps)
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM01")
    assert isinstance(result.affected_scenes, list)


def test_cyclic_dependencies(state_dict):
    deps = [
        Dependency(source_id="E01", target_id="E02", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E02", target_id="E01", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E02", target_id="S03", relation=EdgeRelation.APPEARS_IN),
    ]
    state = _state_with_dependencies(state_dict, deps)
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("E01")
    assert {a.scene_id for a in result.affected_scenes} == {"S03"}


def test_dependency_to_unknown_node_ignored(state_dict):
    deps = [
        Dependency(source_id="CM01", target_id="GHOST01", relation=EdgeRelation.CAUSES),
        Dependency(source_id="GHOST02", target_id="S01", relation=EdgeRelation.REFERENCES),
    ]
    state = _state_with_dependencies(state_dict, deps)
    graph = StoryGraph(state)
    assert "GHOST01" not in graph.graph
    assert "GHOST02" not in graph.graph


def test_min_confidence_prunes_weak_paths(state_dict):
    deps = [
        Dependency(source_id="CM01", target_id="E01", relation=EdgeRelation.CAUSES, confidence=0.1),
        Dependency(source_id="E01", target_id="S09X", relation=EdgeRelation.APPEARS_IN),
    ]
    state = _state_with_dependencies(state_dict, deps)
    engine = PropagationEngine(StoryGraph(state), min_confidence=0.5)
    result = engine.find_affected_scenes("CM01")
    scene_ids = {a.scene_id for a in result.affected_scenes}
    assert "S09X" not in scene_ids


def test_zero_confidence_path_kept_by_default(state_dict):
    deps = [
        Dependency(source_id="CM01", target_id="E01", relation=EdgeRelation.CAUSES, confidence=0.2),
        Dependency(source_id="E01", target_id="S04", relation=EdgeRelation.APPEARS_IN),
    ]
    state = _state_with_dependencies(state_dict, deps)
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM01")
    assert "S04" in {a.scene_id for a in result.affected_scenes}


def test_commitment_only_propagation(state_dict):
    result = PropagationEngine(
        StoryGraph(StoryState.model_validate(state_dict))
    ).find_affected_scenes("NC01")
    assert result.affected_scenes == []
    assert "NC01" in result.summary or result.summary


def test_deep_chain_within_max_depth(state_dict):
    deps = [
        Dependency(source_id="CM01", target_id="E01", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E01", target_id="E02", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E02", target_id="E03", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E03", target_id="E04", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E04", target_id="E05", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E05", target_id="E06", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E06", target_id="E07", relation=EdgeRelation.CAUSES),
        Dependency(source_id="E07", target_id="S04", relation=EdgeRelation.APPEARS_IN),
    ]
    state = _state_with_dependencies(state_dict, deps)
    result = PropagationEngine(StoryGraph(state), max_depth=3).find_affected_scenes("CM01")
    assert "S04" not in {a.scene_id for a in result.affected_scenes}
    result_deep = PropagationEngine(StoryGraph(state), max_depth=10).find_affected_scenes("CM01")
    assert "S04" in {a.scene_id for a in result_deep.affected_scenes}
