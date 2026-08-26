from __future__ import annotations

import json
import re

import pytest

from app.llm import MockLLMClient
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


def rewrite_handler(request) -> str:
    match = re.search(r'"id": "(S\d+)"', request.user_prompt)
    scene_id = match.group(1)
    return json.dumps(
        {
            "id": scene_id,
            "title": f"{scene_id} adapted",
            "summary": f"[REWRITTEN-SUMMARY {scene_id}]",
            "text": f"[REWRITTEN {scene_id}] career-stability conflict resolved",
        },
        ensure_ascii=False,
    )


@pytest.fixture
def mock_client() -> MockLLMClient:
    client = MockLLMClient(handler=rewrite_handler)
    client.set_response("parse_story", sample_story_state_dict())

    client.set_response(
        "detect_frictions",
        {
            "mechanisms": [
                {
                    "id": "CM01",
                    "friction_level": "high",
                    "narrative_importance": "high",
                    "functions": {
                        "plot": ["conflict", "foreshadowing"],
                        "social": ["status", "economic_security"],
                        "emotional": ["humiliation"],
                    },
                },
                {
                    "id": "CM02",
                    "friction_level": "high",
                    "narrative_importance": "high",
                    "functions": {"plot": ["conflict"], "social": ["obligation"]},
                },
                {
                    "id": "CM03",
                    "friction_level": "medium",
                    "narrative_importance": "medium",
                    "functions": {"social": ["status"]},
                },
            ]
        },
    )

    client.set_response(
        "plan_adaptation",
        {
            "culture_mechanism_id": "CM01",
            "original_name": "编制",
            "friction_level": "high",
            "options": [
                {
                    "option_label": "A",
                    "strategy": "preserve",
                    "title": "保留并加注",
                    "replacement_definition": "保留'体制内职位'概念并加脚注",
                    "rationale": "最小改动",
                    "preserved_functions": ["status"],
                    "lost_functions": [],
                    "risks": ["观众理解成本高"],
                },
                {
                    "option_label": "B",
                    "strategy": "functional_replacement",
                    "replacement_definition": "男主在一家没有前景的传统公司做底层职员，女方家庭要求他在有养老金和晋升通道的大机构工作",
                    "title": "职业稳定性机制等效替换",
                    "rationale": "保留社会地位与经济安全功能",
                    "preserved_functions": ["status", "economic_security", "humiliation"],
                    "lost_functions": [],
                    "risks": ["需同步修改多处台词"],
                },
                {
                    "option_label": "C",
                    "strategy": "plot_reconstruction",
                    "replacement_definition": "重构为男主背负家庭债务被女方家庭否定",
                    "title": "冲突机制重构",
                    "rationale": "彻底本土化但改动大",
                    "preserved_functions": ["conflict"],
                    "lost_functions": ["institutional_access"],
                    "risks": ["后续剧情需要连锁调整"],
                },
            ],
        },
    )

    verify_first_pass = {
        "issues": [
            {
                "issue_type": "fact_conflict",
                "severity": "error",
                "scene_id": "S05",
                "description": "S05 仍引用旧设定'编制'，与改编决定冲突",
                "evidence": "没有编制、没有存款的人，给不了安全感。",
            }
        ],
        "commitment_checks": [
            {"commitment_id": "NC01", "status": "preserved", "explanation": ""},
            {"commitment_id": "NC02", "status": "preserved", "explanation": ""},
            {"commitment_id": "NC03", "status": "needs_review", "explanation": "彩礼线未动"},
        ],
    }
    verify_clean = {
        "issues": [],
        "commitment_checks": [
            {"commitment_id": "NC01", "status": "preserved", "explanation": ""},
            {"commitment_id": "NC02", "status": "preserved", "explanation": ""},
            {"commitment_id": "NC03", "status": "preserved", "explanation": ""},
        ],
    }
    client.set_response("verify_consistency", [verify_first_pass, verify_clean])
    return client


async def test_full_pipeline(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)

    meta = await workflow.create_project(
        "demo", "S01 ... S08 ...", MarketProfile(market="United States")
    )
    state = await workflow.analyze(meta.id)

    assert len(state.scenes) == 8
    assert len(state.dependencies) >= 20
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    assert cm01.friction_level == "high"
    assert cm01.functions.social

    plan = await workflow.plan(meta.id, "CM01")
    assert [o.option_label for o in plan.options] == ["A", "B", "C"]
    cached = await workflow.plan(meta.id, "CM01")
    assert cached.model_dump() == plan.model_dump()

    result = await workflow.apply_adaptation(meta.id, "CM01", "B")

    assert {a.scene_id for a in result.applied.propagation.affected_scenes} == {
        "S01", "S02", "S05", "S06", "S08",
    }
    assert sorted(result.applied.rewritten_scene_ids) == ["S01", "S02", "S05", "S06", "S08"]
    assert result.repair_rounds == 1
    assert "S05" in result.repaired_scene_ids
    assert not result.report.blocking_issues
    assert result.report.consistency_score == 1.0

    final_state = store.load_state(meta.id)
    s05 = final_state.scene_by_id("S05")
    assert s05.text.startswith("[REWRITTEN S05]")
    cm01_final = next(m for m in final_state.culture_mechanisms if m.id == "CM01")
    assert cm01_final.adapted_to == plan.options[1].replacement_definition
    assert cm01_final.adapted_strategy == "functional_replacement"

    revisions = store.list_revisions(meta.id)
    assert [r.kind for r in revisions] == ["initial_parse", "adaptation_applied", "repair"]

    applied_list = store.load_applied(meta.id)
    assert len(applied_list) == 1
    assert applied_list[0].chosen_option.strategy.value == "functional_replacement"


async def test_propagate_endpoint_logic(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("demo2", "script", MarketProfile())
    await workflow.analyze(meta.id)

    propagation = workflow.propagate(meta.id, "CM02")
    assert {a.scene_id for a in propagation.affected_scenes} == {"S03", "S04", "S05", "S06", "S08"}

    try:
        workflow.propagate(meta.id, "NOPE")
        raise AssertionError("should have raised KeyError")
    except KeyError:
        pass


async def test_apply_requires_valid_option(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("demo3", "script", MarketProfile())
    await workflow.analyze(meta.id)

    with pytest.raises(KeyError):
        await workflow.apply_adaptation(meta.id, "CM01", "Z")


async def test_verify_standalone(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("demo4", "script", MarketProfile())
    await workflow.analyze(meta.id)

    report = await workflow.verify(meta.id)
    assert len(report.blocking_issues) == 1
    assert report.blocking_issues[0].scene_id == "S05"
    assert {c.commitment_id for c in report.commitment_checks} == {"NC01", "NC02", "NC03"}
    assert report.consistency_score < 1.0


async def test_hallucination_guard_drops_fabricated_stale_refs(tmp_path, mock_client):
    from app.schemas import IssueType

    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("guard", "script", MarketProfile())
    await workflow.analyze(meta.id)

    state = workflow.require_state(meta.id)
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    cm01.adapted_to = "stable corporate career"
    for scene in state.scenes:
        scene.text = scene.text.replace("编制", "stable career")
        scene.summary = scene.summary.replace("编制", "stable career")

    mock_client.set_response(
        "verify_consistency",
        {
            "issues": [
                {
                    "issue_type": "stale_reference",
                    "severity": "error",
                    "scene_id": "S05",
                    "description": "S05 仍引用旧设定'编制'（幻觉捏造）",
                    "evidence": "没有编制的人给不了安全感",
                },
                {
                    "issue_type": "stale_reference",
                    "severity": "error",
                    "scene_id": "S03",
                    "description": "S03 出现'彩礼'相关表述（未改编机制，不该报）",
                    "evidence": "苏父母提出彩礼三十八万八",
                },
                {
                    "issue_type": "stale_reference",
                    "severity": "error",
                    "scene_id": "S04",
                    "description": "S04 出现疑似旧表述（实为新表述被冤枉）",
                    "evidence": "林晓东为攒创业基金推掉了核心岗位邀请",
                },
            ],
            "commitment_checks": [],
        },
    )
    report = await workflow.verifier.verify(state)
    stale = [i for i in report.issues if i.issue_type == IssueType.STALE_REFERENCE]
    assert stale == []


async def test_cross_check_keeps_real_stale_ref(tmp_path, mock_client):
    from app.schemas import IssueType

    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("real-stale", "script", MarketProfile())
    await workflow.analyze(meta.id)

    state = workflow.require_state(meta.id)
    cm01 = next(m for m in state.culture_mechanisms if m.id == "CM01")
    cm01.adapted_to = "stable corporate career"
    for scene in state.scenes:
        if scene.id != "S05":
            scene.text = scene.text.replace("编制", "stable career")
            scene.summary = scene.summary.replace("编制", "stable career")
    state.scene_by_id("S05").text = "苏婉：没有编制的人给不了安全感。"

    mock_client.set_response(
        "verify_consistency",
        {
            "issues": [
                {
                    "issue_type": "stale_reference",
                    "severity": "error",
                    "scene_id": "S05",
                    "description": "S05 真残留旧设定",
                    "evidence": "没有编制的人给不了安全感",
                }
            ],
            "commitment_checks": [],
        },
    )
    report = await workflow.verifier.verify(state)
    stale = [i for i in report.issues if i.issue_type == IssueType.STALE_REFERENCE]
    assert len(stale) == 1
    assert stale[0].scene_id == "S05"
