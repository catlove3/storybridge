from __future__ import annotations

import pytest

from app.llm import MockLLMClient
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


def _workflow(tmp_path, client=None) -> tuple[StoryBridgeWorkflow, MockLLMClient]:
    from app.cli import _load_default_mock_fixtures

    client = client or MockLLMClient()
    _load_default_mock_fixtures(client)
    store = ProjectStore(tmp_path / "projects")
    return StoryBridgeWorkflow(store, client), client


async def test_empty_script_project(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("empty", "", MarketProfile())
    assert meta.script_text == ""
    assert wf.store.load_state(meta.id) is None


async def test_garbage_script_still_creates_project(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("garbage", "!!!!!\n@@@\n%%%", MarketProfile())
    assert meta.id


async def test_analyze_twice_creates_two_revisions(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("dup", "script", MarketProfile())
    await wf.analyze(meta.id)
    await wf.analyze(meta.id)
    revisions = wf.store.list_revisions(meta.id)
    assert len(revisions) == 2
    assert all(r.kind == "initial_parse" for r in revisions)


async def test_apply_twice_same_mechanism(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("twice", "script", MarketProfile())
    await wf.analyze(meta.id)

    first = await wf.apply_adaptation(meta.id, "CM01", "B")
    assert first.repair_rounds >= 0

    state_before = wf.require_state(meta.id)
    s01_before = state_before.scene_by_id("S01").text

    second = await wf.apply_adaptation(meta.id, "CM01", "B")
    assert second.applied.chosen_option.option_label == "B"
    assert wf.require_state(meta.id).scene_by_id("S01").text


async def test_apply_option_a_and_c(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("ac", "script", MarketProfile())
    await wf.analyze(meta.id)

    for label in ("A", "C"):
        result = await wf.apply_adaptation(meta.id, "CM01", label)
        assert result.applied.chosen_option.option_label == label


async def test_apply_multiple_mechanisms_sequentially(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("multi", "script", MarketProfile())
    await wf.analyze(meta.id)

    await wf.apply_adaptation(meta.id, "CM01", "B")
    result2 = await wf.apply_adaptation(meta.id, "CM02", "B")

    state = wf.require_state(meta.id)
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    cm02 = next(m for m in state.culture_mechanisms if m.id == "CM02")
    assert cm01.adapted_to and cm02.adapted_to

    static_issues = wf.verifier and result2.report
    applied_list = wf.store.load_applied(meta.id)
    assert len(applied_list) == 2


async def test_apply_unknown_mechanism(tmp_path):
    wf, _ = _workflow(tmp_path)
    meta = await wf.create_project("unknown", "script", MarketProfile())
    await wf.analyze(meta.id)
    with pytest.raises(KeyError):
        await wf.apply_adaptation(meta.id, "CM99", "B")


async def test_state_without_mechanisms_skips_friction(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["culture_mechanisms"] = []
    client = MockLLMClient()
    client.set_response("parse_story", state_dict)
    client.set_response("detect_frictions", {"mechanisms": []})
    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)

    meta = await wf.create_project("nomech", "script", MarketProfile())
    state = await wf.analyze(meta.id)
    assert state.culture_mechanisms == []
    assert "detect_frictions" not in client.calls


async def test_plan_cached_after_first_call(tmp_path):
    wf, client = _workflow(tmp_path)
    meta = await wf.create_project("cache", "script", MarketProfile())
    await wf.analyze(meta.id)

    await wf.plan(meta.id, "CM01")
    calls_after_first = len(client.calls.get("plan_adaptation", []))
    await wf.plan(meta.id, "CM01")
    calls_after_second = len(client.calls.get("plan_adaptation", []))
    assert calls_after_first == calls_after_second
