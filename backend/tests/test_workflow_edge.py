from __future__ import annotations

import json

import pytest

from app.llm import MockLLMClient
from app.schemas import StoryState
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from app.workflow.rewriter import SceneRewriter
from app.export.bible import export_bible, changed_scenes_diff
from tests.fixtures import sample_story_state_dict


def _wf(tmp_path, responses=None, handler=None):
    from app.cli import _load_default_mock_fixtures

    client = MockLLMClient(handler=handler)
    _load_default_mock_fixtures(client)
    for step, payload in (responses or {}).items():
        client.set_response(step, payload)
    return StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client), client


async def test_scene_listed_in_propagation_but_missing(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["dependencies"].append(
        {"source_id": "CM01", "target_id": "S77", "relation": "references"}
    )
    wf, _ = _wf(tmp_path, {"parse_story": state_dict})
    meta = await wf.create_project("ghostscene", "script", MarketProfile())
    await wf.analyze(meta.id)
    propagation = wf.propagate(meta.id, "CM01")
    assert "S77" not in {a.scene_id for a in propagation.affected_scenes}
    result = await wf.apply_adaptation(meta.id, "CM01", "B")
    assert "S77" not in result.applied.rewritten_scene_ids


async def test_zero_affected_scenes_apply(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["dependencies"] = [
        d for d in state_dict["dependencies"] if "CM" not in d["source_id"]
    ]
    for cm in state_dict["culture_mechanisms"]:
        cm["scene_ids"] = []
    wf, _ = _wf(tmp_path, {"parse_story": state_dict})
    meta = await wf.create_project("noaff", "script", MarketProfile())
    await wf.analyze(meta.id)
    propagation = wf.propagate(meta.id, "CM01")
    assert propagation.affected_scenes == []
    result = await wf.apply_adaptation(meta.id, "CM01", "B")
    assert result.applied.rewritten_scene_ids == []
    assert result.report.consistency_score >= 0


async def test_no_commitments_verify(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["commitments"] = []
    wf, client = _wf(tmp_path, {"parse_story": state_dict})
    meta = await wf.create_project("nocommit", "script", MarketProfile())
    await wf.analyze(meta.id)
    client.set_response("verify_consistency", {"issues": [], "commitment_checks": []})
    report = await wf.verify(meta.id)
    assert report.commitment_checks == []


async def test_repair_loop_hits_max_rounds(tmp_path):
    wf, client = _wf(tmp_path)
    meta = await wf.create_project("loop", "script", MarketProfile())
    await wf.analyze(meta.id)

    stuck_issue = {
        "issues": [
            {
                "issue_type": "fact_conflict",
                "severity": "error",
                "scene_id": "S05",
                "description": "永远修不好的问题",
                "evidence": "xxx",
            }
        ],
        "commitment_checks": [],
    }
    client.set_response("verify_consistency", stuck_issue)

    wf.max_repair_rounds = 3
    result = await wf.apply_adaptation(meta.id, "CM01", "B")
    assert result.repair_rounds == 3
    assert len(result.report.blocking_issues) == 1
    assert result.report.consistency_score < 1.0


async def test_repair_issue_without_scene_id_noop(tmp_path):
    wf, client = _wf(tmp_path)
    meta = await wf.create_project("nosid", "script", MarketProfile())
    await wf.analyze(meta.id)
    client.set_response(
        "verify_consistency",
        {
            "issues": [
                {
                    "issue_type": "fact_conflict",
                    "severity": "error",
                    "scene_id": None,
                    "description": "无场景的全局错误",
                    "evidence": "",
                }
            ],
            "commitment_checks": [],
        },
    )
    result = await wf.apply_adaptation(meta.id, "CM01", "B")
    assert result.repair_rounds == 0
    assert result.report.blocking_issues


def test_bible_project_without_state_raises(tmp_path):
    wf, _ = _wf(tmp_path)
    store = wf.store
    meta_store = ProjectStore(tmp_path / "p")
    meta = meta_store.create_project("empty", "script", MarketProfile())
    with pytest.raises(KeyError):
        export_bible(wf, meta.id, tmp_path / "b.md")


def test_diff_project_with_single_revision(tmp_path):
    wf, _ = _wf(tmp_path)
    meta = await_sync_create(wf)
    state = StoryState.model_validate(sample_story_state_dict())
    wf.store.save_state(meta.id, state, "initial_parse")
    diffs = changed_scenes_diff(wf.store, meta.id)
    assert diffs == []


def await_sync_create(wf):
    import asyncio

    return asyncio.run(wf.create_project("diffonly", "script", MarketProfile()))


async def test_concurrent_projects_isolation(tmp_path):
    import asyncio

    wf, _ = _wf(tmp_path)
    ids = []
    for i in range(5):
        meta = await wf.create_project(f"p{i}", f"script {i}", MarketProfile())
        ids.append(meta.id)
    for i, pid in enumerate(ids):
        await wf.analyze(pid)
        state = wf.store.load_state(pid)
        assert state is not None
    assert len(set(ids)) == 5
    listing = wf.store.list_projects()
    assert len(listing) == 5
