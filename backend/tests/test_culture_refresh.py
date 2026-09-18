from __future__ import annotations

import pytest

from app.llm import MockLLMClient
from app.schemas import StoryState
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


def _post_setting_state() -> StoryState:
    state = StoryState.model_validate(sample_story_state_dict())
    state.settings[0].adapted_to = "改为美国联邦机构中的稳定职业竞争"
    state.settings[0].adapted_strategy = "functional_replacement"
    for scene in state.scenes:
        scene.title = scene.title.replace("编制", "稳定岗位")
        scene.summary = scene.summary.replace("编制", "稳定岗位")
        scene.text = scene.text.replace("编制", "稳定岗位")
    state.scenes[0].text += " 家人尤其看重职业稳定性。"
    return state


async def test_refresh_replaces_stale_mechanisms_and_rebuilds_scene_evidence(tmp_path):
    client = MockLLMClient(
        responses={
            "refresh_culture": {
                "culture_mechanisms": [
                    {
                        "id": "CM01",
                        "name": "职业稳定性",
                        "description": "以稳定职业衡量婚姻对象社会地位的观念",
                        "surface_text": ["职业稳定性"],
                        "scene_ids": ["S01"],
                    }
                ]
            },
            "detect_frictions": {
                "mechanisms": [
                    {
                        "id": "CM01",
                        "friction_level": "medium",
                        "narrative_importance": "high",
                        "functions": {"plot": ["conflict"], "social": ["status"]},
                    }
                ]
            },
        }
    )
    store = ProjectStore(tmp_path / "projects")
    meta = store.create_project("新版故事", "原稿", MarketProfile(market="美国"))
    store.save_state(meta.id, _post_setting_state(), kind="initial_parse")
    workflow = StoryBridgeWorkflow(store, client)

    refreshed = await workflow.refresh_culture(meta.id)

    assert refreshed.version == 2
    assert [item.name for item in refreshed.culture_mechanisms] == ["职业稳定性"]
    assert refreshed.culture_mechanisms[0].friction_level.value == "medium"
    assert all(
        not edge.source_id.startswith("CM") and edge.target_id != "CM02"
        for edge in refreshed.dependencies
    )
    reference = next(
        edge
        for edge in refreshed.dependencies
        if edge.source_id == "S01" and edge.target_id == "CM01"
    )
    assert reference.evidence == "职业稳定性"
    assert store.list_revisions(meta.id)[-1].kind == "culture_refresh"


async def test_stale_post_setting_mechanism_cannot_be_planned(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    meta = store.create_project("新版故事", "原稿", MarketProfile(market="美国"))
    store.save_state(meta.id, _post_setting_state(), kind="initial_parse")
    workflow = StoryBridgeWorkflow(store, MockLLMClient())

    with pytest.raises(ValueError, match="不再出现在当前中文稿"):
        await workflow.plan(meta.id, "CM01")
