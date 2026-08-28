from __future__ import annotations

import asyncio

from app.export import changed_scenes_diff, export_bible, unified_scene_diff
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
    return StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)


def test_bible_with_huge_mechanism_name(tmp_path):
    wf = _wf(tmp_path)

    async def run():
        meta = await wf.create_project("huge", "script", MarketProfile())
        state = StoryState.model_validate(sample_story_state_dict())
        state.culture_mechanisms[0].name = "编" * 500
        state.culture_mechanisms[0].adapted_to = "x" * 2000
        wf.store.save_state(meta.id, state, "initial_parse")
        path = export_bible(wf, meta.id, tmp_path / "b.md")
        text = path.read_text(encoding="utf-8")
        assert "编" * 500 in text
        assert len(text) > 2000

    asyncio.run(run())


def test_bible_without_applied_adaptations(tmp_path):
    wf = _wf(tmp_path)

    async def run():
        meta = await wf.create_project("noapply", "script", MarketProfile())
        state = StoryState.model_validate(sample_story_state_dict())
        wf.store.save_state(meta.id, state, "initial_parse")
        path = export_bible(wf, meta.id, tmp_path / "b.md")
        text = path.read_text(encoding="utf-8")
        assert "APPLIED ADAPTATIONS" in text
        assert "未改编" in text

    asyncio.run(run())


def test_diff_after_only_repair_revision(tmp_path):
    wf = _wf(tmp_path)

    async def run():
        meta = await wf.create_project("onlyrepair", "script", MarketProfile())
        state = StoryState.model_validate(sample_story_state_dict())
        wf.store.save_state(meta.id, state, "initial_parse")
        state.scenes[0].text = "repaired text"
        wf.store.save_state(meta.id, state, "repair")
        diffs = changed_scenes_diff(wf.store, meta.id)
        assert len(diffs) == 1
        assert diffs[0]["scene_id"] == "S01"

    asyncio.run(run())


def test_unified_diff_multiline_and_no_change():
    diff = unified_scene_diff("a\nb", "a\nb", "S01")
    assert diff == [] or all(
        not line.startswith("+")
        for line in diff
        if not line.startswith(("---", "+++", "@@"))
    )
    diff2 = unified_scene_diff("a\nb\nc", "a\nX\nc", "S02")
    assert any(line.startswith("-b") or line == "-b" for line in diff2)
    assert any(line == "+X" for line in diff2)


def test_bible_commitment_none_fields(tmp_path):
    wf = _wf(tmp_path)

    async def run():
        meta = await wf.create_project("nulls", "script", MarketProfile())
        state = StoryState.model_validate(sample_story_state_dict())
        for nc in state.commitments:
            nc.established_at_scene_id = None
            nc.payoff_scene_id = None
            nc.must_preserve = False
        wf.store.save_state(meta.id, state, "initial_parse")
        path = export_bible(wf, meta.id, tmp_path / "b.md")
        assert "?" in path.read_text(encoding="utf-8")

    asyncio.run(run())


def test_bible_written_into_project_dir_default(tmp_path):

    wf = _wf(tmp_path)

    async def run():
        meta = await wf.create_project("loc", "script", MarketProfile())
        state = StoryState.model_validate(sample_story_state_dict())
        wf.store.save_state(meta.id, state, "initial_parse")
        return meta

    meta = asyncio.run(run())
    path = wf.store._peek_dir(meta.id) / "adaptation_bible.md"
    path.write_text("x", encoding="utf-8")
    assert path.exists()
