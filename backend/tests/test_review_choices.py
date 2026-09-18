from unittest.mock import AsyncMock

import pytest

from app.schemas import IssueType, VerifyReport
from app.sqlite_storage import SQLiteProjectStore
from app.workflow.engine import StoryBridgeWorkflow


async def reviewed_workflow(tmp_path, mock_client):
    store = SQLiteProjectStore(tmp_path / 'stories.sqlite3', artifacts_dir=tmp_path / 'projects')
    workflow = StoryBridgeWorkflow(store, mock_client)
    project = await workflow.create_project('review choices', 'script')
    state = await workflow.analyze(project.id)
    report = VerifyReport.model_validate({
        'issues': [
            {'severity': 'error', 'issue_type': 'fact_conflict', 'scene_id': 'S01', 'description': '明确错误'},
            {'severity': 'warning', 'issue_type': 'fact_conflict', 'scene_id': 'S02', 'description': '待确认甲', 'evidence': '甲证据'},
            {'severity': 'warning', 'issue_type': 'fact_conflict', 'scene_id': 'S03', 'description': '待确认乙'},
            {'severity': 'warning', 'issue_type': 'motivation_break', 'description': 'CM02 全局因果关系待确认'},
        ],
        'commitment_checks': [
            {'commitment_id': 'NC01', 'status': 'needs_review', 'explanation': '承诺甲待确认'},
            {'commitment_id': 'NC03', 'status': 'needs_review', 'explanation': '承诺乙待确认'},
        ],
    })
    workflow._remember_report(project.id, state.version, report)
    workflow.rewriter.repair = AsyncMock(return_value=['S01'])
    workflow.verifier.verify = AsyncMock(return_value=VerifyReport(overall_status='pass'))
    return workflow, project.id, report


async def test_repair_only_errors_and_explicitly_selected_reviews(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    await workflow.repair_from_verification(
        project_id, based_on_report=report.review_token,
        review_issue_indexes=[1], review_commitment_ids=['NC01'],
    )
    _, issues, brief = workflow.rewriter.repair.call_args.args
    assert {scene_id for scene_id, _ in issues} == {'S01', 'S02', 'S08'}
    instructions = str(issues) + brief
    assert '甲证据' in instructions
    assert '承诺甲待确认' in instructions
    assert '待确认乙' not in instructions
    assert '全局因果' not in instructions
    assert '承诺乙待确认' not in instructions


async def test_unspecified_reviews_are_not_repaired(tmp_path, mock_client):
    workflow, project_id, _ = await reviewed_workflow(tmp_path, mock_client)
    await workflow.repair_from_verification(project_id)
    _, issues, brief = workflow.rewriter.repair.call_args.args
    assert issues == [('S01', '明确错误')]
    assert '待确认' not in brief


async def test_warning_only_global_review_can_be_selected_after_restart(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    report.issues = report.issues[3:]
    report.commitment_checks = []
    workflow._remember_report(project_id, 1, report)
    restored = StoryBridgeWorkflow(workflow.store, mock_client)
    assert restored.latest_report(project_id).review_token == report.review_token
    restored.rewriter.repair = AsyncMock(return_value=['S03'])
    restored.verifier.verify = AsyncMock(return_value=VerifyReport(overall_status='pass'))
    await restored.repair_from_verification(
        project_id, based_on_report=report.review_token, review_issue_indexes=[0],
    )
    _, issues, brief = restored.rewriter.repair.call_args.args
    assert 'S03' in {scene_id for scene_id, _ in issues}
    assert '全局因果关系' in brief


async def test_changed_report_rejects_old_choices_before_generation(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    old_token = report.review_token
    report.issues.reverse()
    workflow._remember_report(project_id, 1, report)
    with pytest.raises(ValueError, match='检查结果已更新'):
        await workflow.repair_from_verification(
            project_id, based_on_report=old_token, review_issue_indexes=[1],
        )
    workflow.rewriter.repair.assert_not_called()


@pytest.mark.parametrize('scene_ids', [[], ['S03']])
async def test_suggestion_alone_reaches_rewriter_and_verifier(tmp_path, mock_client, scene_ids):
    store = SQLiteProjectStore(tmp_path / 'notes.sqlite3', artifacts_dir=tmp_path / 'projects')
    workflow = StoryBridgeWorkflow(store, mock_client)
    project = await workflow.create_project('suggestions', 'script')
    state = await workflow.analyze(project.id)
    report = VerifyReport(overall_status='pass')
    workflow._remember_report(project.id, state.version, report)
    workflow.verifier.verify = AsyncMock(return_value=VerifyReport(overall_status='pass'))
    note = '让女主表达更坚定，并保留双方关系。'
    await workflow.repair_from_verification(
        project.id, based_on_report=report.review_token,
        repair_suggestion=note, repair_scene_ids=scene_ids,
    )
    expected = scene_ids or [scene.id for scene in state.scenes]
    calls = mock_client.calls['rewrite_scene']
    assert len(calls) == len(expected)
    assert all(note in call.user_prompt for call in calls)
    assert note in workflow.verifier.verify.call_args.kwargs['applied_adaptations_summary']
    revision = store.list_revisions(project.id)[-1]
    assert revision.kind == 'repair'
    assert revision.changed_scene_ids == expected
    assert revision.applied_option['repair_suggestion'] == note
    assert store.load_state(project.id).version == state.version + 1


async def test_suggestion_combines_with_confirmed_issues_only(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    await workflow.repair_from_verification(
        project_id, based_on_report=report.review_token,
        review_issue_indexes=[1], repair_suggestion='补充女主的动机', repair_scene_ids=['S04'],
    )
    _, issues, brief = workflow.rewriter.repair.call_args.args
    assert {scene_id for scene_id, _ in issues} == {'S01', 'S02', 'S04'}
    assert '补充女主的动机' in brief
    assert '待确认乙' not in str(issues) + brief


async def test_stale_reference_and_explicit_note_skip_global_fact_planning(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    report.issues = [report.issues[0].model_copy(update={
        'issue_type': IssueType.STALE_REFERENCE,
        'description': '仍残留旧术语“编制”',
    })]
    report.commitment_checks = []
    workflow._remember_report(project_id, 1, report)
    workflow.rewriter.prepare_repair = AsyncMock(
        side_effect=AssertionError('stale terminology must not create a global fact plan')
    )

    await workflow.repair_from_verification(
        project_id,
        based_on_report=report.review_token,
        repair_suggestion='以英雄执照体系为唯一世界观，删除其他体系。',
    )

    workflow.rewriter.prepare_repair.assert_not_called()
    _, issues, brief = workflow.rewriter.repair.call_args.args
    assert {scene_id for scene_id, _ in issues} == {
        scene.id for scene in workflow.require_state(project_id).scenes
    }
    assert '最高优先级' in brief
    assert '以本轮指令为准' in brief


@pytest.mark.parametrize('note,scene_ids,match', [
    ('   ', [], '没有可自动修复'),
    ('建议', ['S99'], '场景不存在'),
    ('', ['S01'], '请填写'),
    ('字' * 4001, [], '4000'),
])
async def test_invalid_or_empty_suggestions_do_not_generate(tmp_path, mock_client, note, scene_ids, match):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    report.issues = []
    report.commitment_checks = []
    workflow._remember_report(project_id, 1, report)
    with pytest.raises(ValueError, match=match):
        await workflow.repair_from_verification(
            project_id, based_on_report=report.review_token,
            repair_suggestion=note, repair_scene_ids=scene_ids,
        )
    workflow.rewriter.repair.assert_not_called()


async def test_verifier_and_repair_receive_timeline_titles_and_adapted_rules(mock_client):
    from app.schemas import Scene, Setting, StoryState
    from app.workflow.rewriter import SceneRewriter
    from app.workflow.verifier import Verifier

    state = StoryState(
        genre='重生复仇',
        scenes=[
            Scene(id='S01', title='前世·出分', summary='公布成绩', text='林知夏成绩487。'),
            Scene(id='S02', title='重生·出分', summary='换笔后公布成绩', text='林知夏成绩1580。'),
        ],
        settings=[Setting(id='SET01', name='换分系统', description='原高考设定', adapted_to='交换SAT成绩', adapted_strategy='functional_replacement')],
    )
    mock_client.set_response('verify_consistency', {'issues': [], 'checked_scene_ids': ['S01', 'S02']})
    verifier = Verifier(mock_client)
    await verifier.verify(state)
    prompt = mock_client.calls['verify_consistency'][-1].user_prompt
    assert '前世·出分' in prompt and '重生·出分' in prompt
    assert '交换SAT成绩' in prompt and '重生复仇' in prompt
    assert '同一时间线' in prompt and '原始成绩、交换后成绩' in prompt

    await SceneRewriter(mock_client).repair(state, [('S02', '疑似成绩变化')])
    repair_prompt = mock_client.calls['rewrite_scene'][-1].user_prompt
    assert '前世·出分' in repair_prompt and '重生·出分' in repair_prompt
    assert '检查意见可能误判' in repair_prompt
    # The context retains both original values; no keyword-based filter or
    # score normalization silently removes legitimate findings or changes text.
    assert state.scenes[0].text == '林知夏成绩487。'


async def test_human_can_keep_blocking_errors_and_violated_commitments(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    report.commitment_checks[0].status = 'violated'
    workflow._remember_report(project_id, 1, report)
    confirmed = await workflow.confirm_verification_review(project_id, report.review_token, [0], ['NC01'])
    assert confirmed.blocking_issues == []
    assert confirmed.overall_status != 'fail'
    assert confirmed.issues[0].severity.value == 'error'  # original finding retained
    restored = StoryBridgeWorkflow(workflow.store, mock_client)
    assert restored.latest_report(project_id).kept_issue_indexes == [0]
    assert restored.latest_report(project_id).kept_commitment_ids == ['NC01']
    await workflow.repair_from_verification(
        project_id, based_on_report=confirmed.review_token, review_issue_indexes=[1],
    )
    _, issues, brief = workflow.rewriter.repair.call_args.args
    assert {scene_id for scene_id, _ in issues} == {'S02'}
    assert '明确错误' not in str(issues) + brief
    assert '承诺甲待确认' not in str(issues) + brief


async def test_human_can_reverse_keep_and_cannot_accept_stale_report(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    token = report.review_token
    await workflow.confirm_verification_review(project_id, token, [0], [])
    restored = await workflow.confirm_verification_review(project_id, token, [], [])
    assert restored.overall_status == 'fail'
    assert len(restored.blocking_issues) == 1
    report.issues.reverse()
    workflow._remember_report(project_id, 1, report)
    with pytest.raises(ValueError, match='检查结果已更新'):
        await workflow.confirm_verification_review(project_id, token, [0], [])


def test_model_cannot_mark_its_own_errors_as_human_approved():
    from app.schemas import Scene, StoryState
    from app.workflow.verifier import Verifier

    state = StoryState(scenes=[Scene(id='S01', summary='测试', text='测试')])
    report = VerifyReport.model_validate({
        'issues': [{'severity': 'error', 'issue_type': 'fact_conflict', 'scene_id': 'S01', 'description': '错误'}],
        'kept_issue_indexes': [0], 'kept_commitment_ids': ['NC01'],
    })
    report = Verifier.sanitize(state, report)
    report.recompute_score()
    assert report.kept_issue_indexes == []
    assert report.kept_commitment_ids == []
    assert report.overall_status == 'fail'
