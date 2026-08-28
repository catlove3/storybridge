from __future__ import annotations

import asyncio
import json

import pytest

from app.baselines.metrics import evaluate_output
from app.baselines.runner import BaselineRunner
from app.llm import MockLLMClient
from app.schemas import StoryState
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


def _wf(tmp_path, responses=None):
    from app.cli import _load_default_mock_fixtures

    client = MockLLMClient()
    _load_default_mock_fixtures(client)
    for step, payload in (responses or {}).items():
        client.set_response(step, payload)
    return StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client), client


async def test_baseline_empty_mechanism_list(tmp_path):
    wf, client = _wf(tmp_path)
    state_dict = sample_story_state_dict()
    state_dict["culture_mechanisms"] = []
    state_dict["dependencies"] = [
        dependency
        for dependency in state_dict["dependencies"]
        if not dependency["source_id"].startswith("CM")
        and not dependency["target_id"].startswith("CM")
    ]
    client.set_response("parse_story", state_dict)
    client.set_response("detect_frictions", {"mechanisms": []})
    client.set_response("baseline_translate", "english text")
    client.set_response("baseline_strong_prompt", "SCENE 1 rewritten")

    runner = BaselineRunner(wf, client)
    with pytest.raises(KeyError):
        await runner.run_experiment(
            "empty", "script", [("CM01", "B")], MarketProfile(market="US")
        )


async def test_baseline_ground_truth_empty_mechanism_not_in_script(tmp_path):
    wf, client = _wf(tmp_path)
    client.set_response("baseline_translate", "plain english")
    client.set_response("baseline_strong_prompt", "rewritten")

    state_dict = sample_story_state_dict()
    state_dict["culture_mechanisms"][0]["surface_text"] = ["不存在的词xyz"]
    client.set_response("parse_story", state_dict)

    runner = BaselineRunner(wf, client)
    result = await runner.run_experiment(
        "ghost", "script", [("CM01", "B")], MarketProfile(market="US")
    )
    table_clients = [m for m in result.metrics if m.system_name.startswith("C")]
    assert table_clients[0].affected_scene_recall is not None


async def test_baseline_llm_output_garbage(tmp_path):
    wf, client = _wf(tmp_path)
    client.set_response("baseline_translate", "")
    client.set_response("baseline_strong_prompt", "")

    runner = BaselineRunner(wf, client)
    result = await runner.run_experiment(
        "garbage", "script", [("CM01", "B")], MarketProfile(market="US")
    )
    assert all(isinstance(m.stale_reference_count, int) for m in result.metrics)


async def test_evaluate_output_zero_expected(tmp_path):
    original = StoryState.model_validate(sample_story_state_dict())
    metrics = evaluate_output(original, None, "text", "X", [])
    assert metrics.affected_scene_recall is None


async def test_concurrent_apply_same_project(tmp_path):
    wf, _ = _wf(tmp_path)
    meta = await wf.create_project("race", "script", MarketProfile())
    await wf.analyze(meta.id)
    await wf.plan(meta.id, "CM01")

    r1, r2 = await asyncio.gather(
        wf.apply_adaptation(meta.id, "CM01", "B"),
        wf.apply_adaptation(meta.id, "CM01", "B"),
    )
    final = wf.require_state(meta.id)
    assert len(final.scenes) == 8
    revisions = wf.store.list_revisions(meta.id)
    assert all(r.kind in ("initial_parse", "adaptation_applied", "repair") for r in revisions)


async def test_duplicate_analyze_jobs_same_project(tmp_path):
    wf, _ = _wf(tmp_path)
    meta = await wf.create_project("dupjobs", "script", MarketProfile())

    await asyncio.gather(wf.analyze(meta.id), wf.analyze(meta.id))
    revisions = wf.store.list_revisions(meta.id)
    assert len(revisions) == 2
    assert wf.store.load_state(meta.id) is not None


async def test_job_result_serialization_with_exotic_payload():
    from app.jobs import Job

    job = Job(id="x", kind="k", project_id="p", result={"nested": [1, {"deep": True}]})
    payload = job.serialize()
    restored = json.dumps(payload, ensure_ascii=False)
    assert "nested" in restored
