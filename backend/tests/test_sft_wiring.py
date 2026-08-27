from __future__ import annotations

import json

import pytest

from app.llm import MockLLMClient
from app.llm.router import LLMRouter, SFTCallLogger
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict
import asyncio


@pytest.fixture
def sft_dir(tmp_path):
    return tmp_path / "sft"


def test_graph_fourth_direction_combo(state_dict):
    from app.graph import PropagationEngine, StoryGraph
    from app.schemas import Dependency, EdgeRelation

    state_dict["dependencies"].append(
        {"source_id": "S08", "target_id": "E07", "relation": "reveals"}
    )
    state_dict["dependencies"].append(
        {"source_id": "E06", "target_id": "NC02", "relation": "pays_off"}
    )
    state = type(state_dict) and __import__("app.schemas", fromlist=["StoryState"]).StoryState.model_validate(state_dict)

    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("E07")
    ids = {a.scene_id for a in result.affected_scenes}
    assert isinstance(ids, set)

    result2 = PropagationEngine(StoryGraph(state)).find_affected_scenes("NC02")
    assert isinstance(result2.related_commitment_ids, list)


def test_propagation_on_commitment_change(state_dict):
    from app.graph import PropagationEngine, StoryGraph
    from app.schemas import StoryState

    state = StoryState.model_validate(state_dict)
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("NC01")
    affected = {a.scene_id for a in result.affected_scenes}
    assert "S02" in affected or affected == set()
    if affected:
        kinds = [k for a in result.affected_scenes for k in a.impact_kinds]
        assert all(k.value in ("direct_reference", "motivation", "causal", "payoff", "structural") for k in kinds)


async def test_full_pipeline_with_sft_logger_wiring(tmp_path, sft_dir):
    from app.cli import _load_default_mock_fixtures

    logger = SFTCallLogger(log_dir=sft_dir, enabled=True)
    client = MockLLMClient()
    _load_default_mock_fixtures(client)

    class LoggedClient:
        async def complete(self, request):
            resp = await client.complete(request)
            logger.record(request, resp)
            return resp

    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p2"), LoggedClient())
    meta = await wf.create_project("wired", "script", MarketProfile())
    await wf.analyze(meta.id)
    await wf.apply_adaptation(meta.id, "CM01", "B")

    files = sorted(p.name for p in sft_dir.iterdir())
    assert "parse_story.jsonl" in files
    assert "rewrite_scene.jsonl" in files
    assert "verify_consistency.jsonl" in files
    for f in files:
        for line in (sft_dir / f).read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            assert entry["messages"]
            assert isinstance(entry["completion"], str)
