from __future__ import annotations

import asyncio
import json

import pytest

from app.baselines.metrics import evaluate_output
from app.baselines.runner import BaselineRunner, EvalAnnotations
from app.llm import MockLLMClient
from app.schemas import StoryState
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict, sample_target_script_dict


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
    client.set_response("baseline_translate", sample_target_script_dict("TRANSLATE"))
    client.set_response("baseline_strong_prompt", sample_target_script_dict("STRONG"))

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
    with pytest.raises(Exception):
        await runner.run_experiment(
            "garbage", "script", [("CM01", "B")], MarketProfile(market="US")
        )


async def test_baseline_uses_external_annotations_without_circular_truth(tmp_path):
    wf, client = _wf(tmp_path)
    client.set_response("baseline_translate", sample_target_script_dict("TRANSLATE"))
    client.set_response("baseline_strong_prompt", sample_target_script_dict("STRONG"))

    result = await BaselineRunner(wf, client).run_experiment(
        "annotated",
        "script",
        [("CM01", "B")],
        MarketProfile(market="US"),
        annotations=EvalAnnotations(
            expected_affected_ids=["S08", "S01", "S01"],
            forbidden_target_terms={"CM01": ["civil service tenure"]},
            source="reviewer-v1",
        ),
    )

    assert result.annotation_source == "reviewer-v1"
    assert result.run_manifest["annotation_source"] == "reviewer-v1"
    assert result.run_manifest["annotations_blake2b"]
    assert result.run_manifest["input_blake2b"]
    assert result.run_manifest["models"]["baseline_translate"]["model"] == "mock-model"
    assert all(metric.expected_scene_ids == ["S01", "S08"] for metric in result.metrics)
    assert result.metrics[0].affected_scene_recall == 0
    assert result.metrics[1].affected_scene_recall == 1
    assert all(metric.stale_reference_count is not None for metric in result.metrics)


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
    assert [revision.revision_id for revision in revisions] == [1, 2, 3]
    assert [revision.state_version for revision in revisions] == [1, 2, 3]
    assert final.version == 3
    applied = wf.store.load_applied(meta.id)
    assert [item.state_version for item in applied] == [2, 3]
    assert {r1.applied.state_version, r2.applied.state_version} == {2, 3}


async def test_duplicate_analyze_jobs_same_project(tmp_path):
    wf, _ = _wf(tmp_path)
    meta = await wf.create_project("dupjobs", "script", MarketProfile())

    await asyncio.gather(wf.analyze(meta.id), wf.analyze(meta.id))
    revisions = wf.store.list_revisions(meta.id)
    assert len(revisions) == 2
    assert [revision.state_version for revision in revisions] == [1, 2]
    assert wf.store.load_state(meta.id) is not None


async def test_job_manager_idempotency_and_project_serialization():
    from app.jobs import JobManager

    manager = JobManager(max_concurrent=4)
    active = 0
    max_active = 0
    calls = 0

    async def work():
        nonlocal active, max_active, calls
        calls += 1
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return calls

    first = manager.submit("apply", "project-a", work, idempotency_key="same-op")
    duplicate = manager.submit("apply", "project-a", work, idempotency_key="same-op")
    second = manager.submit("verify", "project-a", work, idempotency_key="verify-op")

    assert first.id == duplicate.id
    while first.status in {"queued", "running"} or second.status in {"queued", "running"}:
        await asyncio.sleep(0.01)

    assert calls == 2
    assert max_active == 1


async def test_job_manager_allows_different_projects_in_parallel():
    from app.jobs import JobManager

    manager = JobManager(max_concurrent=4)
    both_started = asyncio.Event()
    active = 0

    async def work():
        nonlocal active
        active += 1
        if active == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.5)
        active -= 1

    jobs = [
        manager.submit("analyze", "project-a", work),
        manager.submit("analyze", "project-b", work),
    ]
    while any(job.status in {"queued", "running"} for job in jobs):
        await asyncio.sleep(0.01)

    assert all(job.status == "done" for job in jobs)


async def test_job_result_serialization_with_exotic_payload():
    from app.jobs import Job

    job = Job(id="x", kind="k", project_id="p", result={"nested": [1, {"deep": True}]})
    payload = job.serialize()
    restored = json.dumps(payload, ensure_ascii=False)
    assert "nested" in restored
