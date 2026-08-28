from __future__ import annotations

import asyncio

import pytest

from app.config import LLMConfig, ProfileConfig
from app.graph import PropagationEngine, StoryGraph
from app.llm import MockLLMClient
from app.llm.router import LLMRouter
from app.llm.structured import _unwrap_array
from app.schemas import StoryState
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


def test_scene_ordering_ten_plus_scenes(state_dict):
    extra_scenes = []
    for i in range(9, 13):
        extra_scenes.append(
            {
                "id": f"S{i}",
                "summary": f"scene {i}",
                "text": "x",
                "character_ids": [],
                "event_ids": [],
            }
        )
    state_dict["scenes"].extend(extra_scenes)
    state_dict["dependencies"].extend(
        [
            {"source_id": f"S{i}", "target_id": "CM01", "relation": "references"}
            for i in range(9, 13)
        ]
    )
    state = StoryState.model_validate(state_dict)
    result = PropagationEngine(StoryGraph(state)).find_affected_scenes("CM01")
    ids = [a.scene_id for a in result.affected_scenes]
    assert "S9" in ids and "S12" in ids
    assert ids == sorted(ids, key=lambda s: int(s[1:])), ids


def test_router_missing_profile_for_step():
    config = LLMConfig(
        default_profile="general",
        profiles={"general": ProfileConfig(model="m")},
        step_routes={"parse_story": "nonexistent"},
    )
    router = LLMRouter(config=config)
    with pytest.raises(KeyError):
        router.client_for_step("parse_story")


def test_router_default_profile_fallback():
    config = LLMConfig(
        default_profile="general",
        profiles={"general": ProfileConfig(model="m")},
    )
    router = LLMRouter(config=config)
    client = router.client_for_step("unknown_step")
    assert client.profile.model == "m"


def test_config_paths_are_resolved_against_backend_root():
    from app.config import BACKEND_ROOT, get_config

    get_config.cache_clear()
    config = get_config()
    try:
        assert config.storage.projects_dir == (BACKEND_ROOT / "data/projects").resolve()
        assert config.storage.jobs_file == (BACKEND_ROOT / "data/jobs.json").resolve()
        assert config.logging.sft_log_dir == (BACKEND_ROOT / "data/sft_logs").resolve()
        assert config.logging.sft_log_enabled is False
    finally:
        get_config.cache_clear()


def test_config_storage_paths_support_environment_overrides(tmp_path, monkeypatch):
    from app.config import get_config

    monkeypatch.setenv("STORYBRIDGE_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setenv("STORYBRIDGE_JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("STORYBRIDGE_SFT_LOG_DIR", str(tmp_path / "sft"))
    get_config.cache_clear()
    try:
        config = get_config()
        assert config.storage.projects_dir == (tmp_path / "projects").resolve()
        assert config.storage.jobs_file == (tmp_path / "jobs.json").resolve()
        assert config.logging.sft_log_dir == (tmp_path / "sft").resolve()
    finally:
        get_config.cache_clear()


def test_unwrap_array_empty_list():
    assert _unwrap_array([], StoryState) == []


def test_unwrap_array_primitive_list():
    assert _unwrap_array(["a", "b"], StoryState) == ["a", "b"]


async def test_ten_concurrent_jobs(tmp_path):
    from app.cli import _load_default_mock_fixtures
    from app.jobs import JobManager

    client = MockLLMClient()
    _load_default_mock_fixtures(client)
    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)
    metas = [await wf.create_project(f"p{i}", "s", MarketProfile()) for i in range(10)]

    manager = JobManager(max_concurrent=3)
    jobs = [manager.submit("analyze", m.id, (lambda mid=m.id: wf.analyze(mid))) for m in metas]
    await asyncio.sleep(1.0)
    statuses = [manager.get(j.id).status for j in jobs]
    assert all(s == "done" for s in statuses), statuses
    assert len(manager.list_for_project(metas[0].id)) == 1


async def test_failed_job_error_surfaced(tmp_path):
    from app.jobs import JobManager

    async def boom():
        raise RuntimeError("llm down")

    manager = JobManager()
    job = manager.submit("analyze", "p1", boom)
    await asyncio.sleep(0.2)
    done = manager.get(job.id)
    assert done.status == "failed"
    assert done.error == "job_execution_failed"
    payload = done.serialize()
    assert payload["status"] == "failed"


def test_cli_missing_script_file():
    from pathlib import Path

    from app.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["create", "/nonexistent/script.md"])
    assert exc_info.value.code == 2
    with pytest.raises(KeyError):
        asyncio.run(
            StoryBridgeWorkflow(
                ProjectStore(Path("/tmp/opencode/nul")), MockLLMClient()
            ).analyze("fake-project")
        )


def test_cli_unknown_subcommand():
    from app.cli import main

    with pytest.raises(SystemExit):
        main(["frobnicate"])


async def test_apply_with_scene_ids_unpadded(tmp_path):
    from app.cli import _load_default_mock_fixtures

    state_dict = sample_story_state_dict()
    for scene in state_dict["scenes"]:
        num = int(scene["id"][1:])
        scene["id"] = f"S{num}"
    for dep in state_dict["dependencies"]:
        for field in ("source_id", "target_id"):
            if dep[field].startswith("S") and dep[field][1:].isdigit():
                dep[field] = f"S{int(dep[field][1:])}"
    for cm in state_dict["culture_mechanisms"]:
        cm["scene_ids"] = [f"S{int(s[1:])}" for s in cm["scene_ids"]]
    for event in state_dict["events"]:
        event["scene_ids"] = [f"S{int(s[1:])}" for s in event["scene_ids"]]
    for commitment in state_dict["commitments"]:
        for field in ("established_at_scene_id", "payoff_scene_id"):
            scene_id = commitment[field]
            if scene_id is not None:
                commitment[field] = f"S{int(scene_id[1:])}"

    client = MockLLMClient()
    _load_default_mock_fixtures(client)
    client.set_response("parse_story", state_dict)
    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)
    meta = await wf.create_project("unpad", "s", MarketProfile())
    await wf.analyze(meta.id)
    propagation = wf.propagate(meta.id, "CM01")
    ids = [a.scene_id for a in propagation.affected_scenes]
    assert "S1" in ids and "S8" in ids
