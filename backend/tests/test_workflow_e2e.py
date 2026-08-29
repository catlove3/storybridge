from __future__ import annotations

import pytest

from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import AdaptationSelection, StoryBridgeWorkflow


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
    assert result.report.overall_status == "pass"
    assert result.report.static_checks_passed == result.report.static_checks_total == 3
    assert result.report.commitments_verified == result.report.commitments_total == 3
    assert result.report.scenes_checked == result.report.scenes_total == 8

    final_state = store.load_state(meta.id)
    s05 = final_state.scene_by_id("S05")
    assert s05.text.startswith("[REWRITTEN S05]")
    cm01_final = next(m for m in final_state.culture_mechanisms if m.id == "CM01")
    assert cm01_final.adapted_to == plan.options[1].replacement_definition
    assert cm01_final.adapted_strategy == "functional_replacement"

    revisions = store.list_revisions(meta.id)
    assert [r.kind for r in revisions] == ["initial_parse", "adaptation_applied"]
    assert [r.state_version for r in revisions] == [1, 2]
    assert final_state.version == 2

    applied_list = store.load_applied(meta.id)
    assert len(applied_list) == 1
    assert applied_list[0].state_version == 2
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


async def test_batch_apply_iterates_on_one_candidate_and_commits_once(
    tmp_path, mock_client
):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("batch", "script", MarketProfile())
    initial = await workflow.analyze(meta.id)

    cm01_plan = await workflow.plan(meta.id, "CM01")
    cm02_plan = cm01_plan.model_copy(
        deep=True,
        update={"culture_mechanism_id": "CM02", "original_name": "彩礼"},
    )
    store.save_plan(meta.id, cm02_plan)

    result = await workflow.apply_adaptations(
        meta.id,
        [
            AdaptationSelection(culture_mechanism_id="CM01", option_label="B"),
            AdaptationSelection(culture_mechanism_id="CM02", option_label="C"),
        ],
        auto_verify_and_repair=False,
        based_on_version=initial.version,
        operation_id="batch-once",
    )

    assert [item.plan_culture_mechanism_id for item in result.applied] == [
        "CM01",
        "CM02",
    ]
    assert result.from_version == 1
    assert result.to_version == 2
    assert all(item.operation_id == "batch-once" for item in result.applied)
    assert all(item.state_version == 2 for item in result.applied)
    assert [revision.state_version for revision in store.list_revisions(meta.id)] == [1, 2]
    assert len(store.load_applied(meta.id)) == 2

    final_state = workflow.require_state(meta.id)
    adapted = {item.id: item.adapted_to for item in final_state.culture_mechanisms}
    assert adapted["CM01"] == cm01_plan.option_by_label("B").replacement_definition
    assert adapted["CM02"] == cm02_plan.option_by_label("C").replacement_definition

    cm02_s05_call = next(
        call
        for call in mock_client.calls["rewrite_scene"]
        if '"id": "S05"' in call.user_prompt and "彩礼" in call.user_prompt
    )
    assert "[REWRITTEN S05]" in cm02_s05_call.user_prompt


async def test_batch_apply_failure_does_not_commit_partial_state(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("atomic-batch", "script", MarketProfile())
    await workflow.analyze(meta.id)
    cm01_plan = await workflow.plan(meta.id, "CM01")
    store.save_plan(
        meta.id,
        cm01_plan.model_copy(
            deep=True,
            update={"culture_mechanism_id": "CM02", "original_name": "彩礼"},
        ),
    )
    original_handler = mock_client.handler

    def fail_second_mechanism(request):
        if request.step == "rewrite_scene" and "彩礼" in request.user_prompt:
            raise RuntimeError("second adaptation failed")
        return original_handler(request)

    mock_client.handler = fail_second_mechanism
    with pytest.raises(RuntimeError, match="second adaptation failed"):
        await workflow.apply_adaptations(
            meta.id,
            [
                AdaptationSelection(culture_mechanism_id="CM01", option_label="B"),
                AdaptationSelection(culture_mechanism_id="CM02", option_label="B"),
            ],
            auto_verify_and_repair=False,
        )

    state = workflow.require_state(meta.id)
    assert state.version == 1
    assert all(item.adapted_to is None for item in state.culture_mechanisms)
    assert store.load_applied(meta.id) == []
    assert len(store.list_revisions(meta.id)) == 1


async def test_target_script_is_version_bound_and_regenerated_after_apply(
    tmp_path, mock_client
):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project(
        "target",
        "script",
        MarketProfile(target_language="English", target_locale="en-US"),
    )
    state = await workflow.analyze(meta.id)

    first = await workflow.render_target_script(meta.id)
    cached = await workflow.render_target_script(meta.id)

    assert first.model_dump() == cached.model_dump()
    assert first.source_state_version == state.version == 1
    assert [scene.id for scene in first.scenes] == [scene.id for scene in state.scenes]
    assert len(mock_client.calls["render_target_script"]) == 1

    await workflow.apply_adaptation(meta.id, "CM01", "B")
    assert store.load_target_script(meta.id) is None
    second = await workflow.render_target_script(meta.id)

    assert second.source_state_version == 2
    assert len(mock_client.calls["render_target_script"]) == 2


async def test_apply_requires_valid_option(tmp_path, mock_client):
    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("demo3", "script", MarketProfile())
    await workflow.analyze(meta.id)

    with pytest.raises(KeyError):
        await workflow.apply_adaptation(meta.id, "CM01", "Z")


async def test_plan_is_bound_to_state_version_and_stale_apply_is_rejected(
    tmp_path, mock_client
):
    from app.workflow.engine import StateVersionConflict

    store = ProjectStore(tmp_path / "projects")
    workflow = StoryBridgeWorkflow(store, mock_client)
    meta = await workflow.create_project("versioned", "script", MarketProfile())
    first_state = await workflow.analyze(meta.id)
    old_plan = await workflow.plan(meta.id, "CM01")

    assert first_state.version == old_plan.based_on_version == 1

    second_state = await workflow.analyze(meta.id)
    assert second_state.version == 2
    with pytest.raises(StateVersionConflict):
        await workflow.apply_adaptation(
            meta.id,
            "CM01",
            "B",
            based_on_version=old_plan.based_on_version,
        )

    assert workflow.require_state(meta.id).version == 2
    assert len(store.list_revisions(meta.id)) == 2
    refreshed_plan = await workflow.plan(meta.id, "CM01")
    assert refreshed_plan.based_on_version == 2


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
    assert report.overall_status == "fail"


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
