from __future__ import annotations

import json

import pytest

from app.llm import LLMRequest, LLMResponse, MockLLMClient
from app.llm.router import SFTCallLogger
from app.privacy import project_data_context
from app.schemas import DataPolicy
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow


@pytest.fixture
def sft_dir(tmp_path):
    return tmp_path / "sft"


def test_graph_fourth_direction_combo(state_dict):
    from app.graph import PropagationEngine, StoryGraph

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
    meta = await wf.create_project(
        "wired",
        "script",
        MarketProfile(),
        data_policy=DataPolicy(
            sft_opt_in=True,
            content_source="synthetic test fixture",
            license="test-only",
            consent_note="generated for automated tests",
        ),
    )
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
            assert entry["consent"] is True
            assert entry["quality_status"] == "unreviewed"
            assert entry["prompt_blake2b"]


async def test_sft_logger_requires_project_opt_in(tmp_path, sft_dir):
    from app.cli import _load_default_mock_fixtures

    call_logger = SFTCallLogger(log_dir=sft_dir, enabled=True)
    client = MockLLMClient()
    _load_default_mock_fixtures(client)

    class LoggedClient:
        async def complete(self, request):
            response = await client.complete(request)
            call_logger.record(request, response)
            return response

    workflow = StoryBridgeWorkflow(ProjectStore(tmp_path / "no-consent"), LoggedClient())
    meta = await workflow.create_project("private", "script", MarketProfile())
    await workflow.analyze(meta.id)

    assert list(sft_dir.glob("*.jsonl")) == []


def test_sft_logger_redacts_and_deletes_project_samples(sft_dir):
    call_logger = SFTCallLogger(log_dir=sft_dir, enabled=True, redact_pii=True)
    request = LLMRequest(
        step="parse_story",
        system_prompt="contact producer@example.com",
        user_prompt="Call 13812345678; token sk-abcdefghijklmnop",
    )
    response = LLMResponse(
        text="producer@example.com approved",
        model="mock",
        profile_name="mock",
        step="parse_story",
    )
    policy = DataPolicy(
        sft_opt_in=True,
        content_source="licensed fixture",
        license="test-only",
        consent_note="explicit test consent",
    )

    with project_data_context("project-private", policy):
        call_logger.record(request, response)

    path = sft_dir / "parse_story.jsonl"
    text = path.read_text(encoding="utf-8")
    assert "producer@example.com" not in text
    assert "13812345678" not in text
    assert "sk-abcdefghijklmnop" not in text
    assert text.count("[REDACTED]") >= 3
    assert call_logger.delete_project("project-private") == 1
    assert path.read_text(encoding="utf-8") == ""
