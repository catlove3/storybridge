from __future__ import annotations

from app.export import changed_scenes_diff, export_bible
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.test_workflow_e2e import mock_client


async def test_export_bible_after_apply(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("bible", "script", MarketProfile())
    await workflow.analyze(meta.id)
    await workflow.plan(meta.id, "CM01")
    await workflow.apply_adaptation(meta.id, "CM01", "B")

    out = tmp_path / "out" / "bible.md"
    path = export_bible(workflow, meta.id, out)

    text = path.read_text(encoding="utf-8")
    assert "# Adaptation Bible" in text
    assert "CORE NARRATIVE COMMITMENTS" in text
    assert "NC01" in text
    assert "CM01" in text
    assert "职业稳定性机制等效替换" in text
    assert "APPLIED ADAPTATIONS" in text
    assert "REVISION HISTORY" in text
    assert "adaptation_applied" in text


async def test_changed_scenes_diff(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("diff", "script", MarketProfile())
    await workflow.analyze(meta.id)
    await workflow.plan(meta.id, "CM01")
    await workflow.apply_adaptation(meta.id, "CM01", "B")

    diffs = changed_scenes_diff(store, meta.id)
    assert len(diffs) == 5
    ids = {d["scene_id"] for d in diffs}
    assert ids == {"S01", "S02", "S05", "S06", "S08"}
    for d in diffs:
        assert any(line.startswith("+") for line in d["diff"])
        assert any(line.startswith("-") for line in d["diff"])
        assert "REWRITTEN" in d["after"]
