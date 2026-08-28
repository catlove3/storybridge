from __future__ import annotations

from app.llm import MockLLMClient
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


async def test_detector_drops_misextracted_mechanism(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["dependencies"].append(
        {"source_id": "CM03", "target_id": "E06", "relation": "causes"}
    )
    wf, client = _wf(tmp_path, {"parse_story": state_dict})
    client.set_response(
        "detect_frictions",
        {
            "mechanisms": [
                {"id": "CM01", "friction_level": "high", "narrative_importance": "high"},
                {"id": "CM02", "friction_level": "high", "narrative_importance": "high"},
                {"id": "CM03", "friction_level": "low", "narrative_importance": "low", "drop": True},
            ]
        },
    )
    meta = await wf.create_project("drop", "script", MarketProfile())
    state = await wf.analyze(meta.id)

    assert [cm.id for cm in state.culture_mechanisms] == ["CM01", "CM02"]
    assert all(
        d.source_id != "CM03" and d.target_id != "CM03" for d in state.dependencies
    )


async def test_detector_keeps_all_when_no_drop(tmp_path):
    wf, _ = _wf(tmp_path)
    meta = await wf.create_project("keep", "script", MarketProfile())
    state = await wf.analyze(meta.id)
    assert len(state.culture_mechanisms) == 3


async def test_drop_all_mechanisms_survives_verify(tmp_path):
    state_dict = sample_story_state_dict()
    wf, client = _wf(tmp_path, {"parse_story": state_dict})
    client.set_response(
        "detect_frictions",
        {
            "mechanisms": [
                {"id": "CM01", "drop": True},
                {"id": "CM02", "drop": True},
                {"id": "CM03", "drop": True},
            ]
        },
    )
    meta = await wf.create_project("dropall", "script", MarketProfile())
    state = await wf.analyze(meta.id)
    assert state.culture_mechanisms == []

    report = await wf.verify(meta.id)
    assert report.consistency_score >= 0
