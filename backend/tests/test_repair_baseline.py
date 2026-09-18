import json

import pytest

from app.schemas import VerifyReport
from app.schemas.repair import RepairBaseline
from app.workflow.engine import StoryBridgeWorkflow
from app.workflow.verifier import Verifier
from tests.test_review_choices import reviewed_workflow


def plan_payload():
    return {
        'baseline': {
            'facts': [{
                'timeline': '重生后', 'subject': '角色甲', 'attribute': '积分',
                'phase': '交换后锁定', 'value': '72',
                'basis': '用户指定甲原有19分，交换乙的72分',
            }],
            'rules': ['交换双方积分，公布后不可再次交换'],
        },
        'scene_repairs': [
            {'scene_id': 'S01', 'instruction': '公布甲的最终积分为72'},
            {'scene_id': 'S08', 'instruction': '结尾保持甲的最终积分为72'},
        ],
        'unresolved_questions': [],
    }


async def test_shared_baseline_expands_related_scenes_and_survives_restart(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    plan = plan_payload()
    mock_client.set_response('plan_repair', plan)
    # Exercise the actual scene rewriter, not the review test's stub.
    from app.workflow.rewriter import SceneRewriter
    workflow.rewriter = SceneRewriter(mock_client)
    await workflow.repair_from_verification(
        project_id, based_on_report=report.review_token,
        repair_suggestion='甲原有19分，交换乙的72分，最终甲72分。',
    )
    assert len(mock_client.calls['plan_repair']) == 1
    assert len(mock_client.calls['rewrite_scene']) == 2
    for call in mock_client.calls['rewrite_scene']:
        assert '交换后锁定' in call.user_prompt and '72' in call.user_prompt
    saved = workflow.require_state(project_id)
    assert saved.repair_baseline.model_dump() == plan['baseline']
    assert workflow.store.list_revisions(project_id)[-1].changed_scene_ids == ['S01', 'S08']
    assert workflow.verifier.verify.call_args.args[0].repair_baseline == saved.repair_baseline
    restarted = StoryBridgeWorkflow(workflow.store, mock_client)
    restored = restarted.require_state(project_id)
    assert Verifier(mock_client)._digest(restored)['repair_baseline'] == plan['baseline']
    # A subsequent round sees the existing baseline plus explicit new feedback.
    workflow._remember_report(project_id, saved.version, report)
    await workflow.repair_from_verification(
        project_id, based_on_report=report.review_token, repair_suggestion='保留积分，补充交换动机',
    )
    context = json.loads(mock_client.calls['plan_repair'][-1].user_prompt)
    assert context['current_story']['repair_baseline'] == plan['baseline']
    assert '补充交换动机' in context['adaptation_and_user_instructions']
    assert context['source_script'] == 'script'


async def test_ambiguous_plan_preserves_version_and_does_not_rewrite(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    before = workflow.require_state(project_id).model_dump()
    plan = plan_payload()
    plan['unresolved_questions'] = ['谁是交换规则的接收者？']
    mock_client.set_response('plan_repair', plan)
    with pytest.raises(ValueError, match='谁是交换规则的接收者'):
        await workflow.repair_from_verification(project_id, based_on_report=report.review_token)
    workflow.rewriter.repair.assert_not_called()
    workflow.verifier.verify.assert_not_called()
    assert workflow.require_state(project_id).model_dump() == before


async def test_kept_decisions_reach_planner_as_constraints(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    await workflow.confirm_verification_review(project_id, report.review_token, [1], ['NC01'])
    await workflow.repair_from_verification(project_id, based_on_report=report.review_token)
    context = json.loads(mock_client.calls['plan_repair'][0].user_prompt)
    assert len(context['user_kept_items']) == 2
    assert '当前正文无需因此修改' in context['user_kept_items'][0]
    assert '待确认甲' in context['user_kept_items'][0]
    assert '更新该承诺的旧描述' in context['user_kept_items'][1]
    assert 'NC01' in context['user_kept_items'][1]
    assert context['selected_issues'] == [['S01', '明确错误']]


async def test_repair_plan_synchronizes_events_commitments_and_dependency_evidence(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    plan = plan_payload()
    plan.update({
        'event_updates': [{
            'event_id': 'E01', 'description': '父亲因职业保障反对婚事',
            'scene_ids': ['S02'],
        }],
        'commitment_updates': [{
            'commitment_id': 'NC01', 'description': '职业保障冲突最终得到回应',
            'established_at_scene_id': 'S02', 'payoff_scene_id': 'S08',
            'must_preserve': True,
        }],
        'dependency_evidence_updates': [{
            'source_id': 'CM01', 'target_id': 'E01', 'relation': 'motivates',
            'evidence': '家人质疑新职业缺乏长期保障', 'confidence': 0.9,
        }],
    })
    mock_client.set_response('plan_repair', plan)

    await workflow.repair_from_verification(
        project_id, based_on_report=report.review_token,
    )

    state = workflow.require_state(project_id)
    assert state.events[0].description == '父亲因职业保障反对婚事'
    assert state.commitments[0].description == '职业保障冲突最终得到回应'
    dependency = next(
        item for item in state.dependencies
        if item.source_id == 'CM01' and item.target_id == 'E01'
    )
    assert dependency.evidence == '家人质疑新职业缺乏长期保障'


@pytest.mark.parametrize('invalid', ['unknown_scene', 'duplicate_fact'])
async def test_invalid_plan_retries_before_scene_writes(tmp_path, mock_client, invalid):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    bad = plan_payload()
    if invalid == 'unknown_scene':
        bad['scene_repairs'][0]['scene_id'] = 'S99'
    else:
        bad['baseline']['facts'].append({**bad['baseline']['facts'][0], 'value': '19'})
    mock_client.set_response('plan_repair', [bad, plan_payload()])
    await workflow.repair_from_verification(project_id, based_on_report=report.review_token)
    assert len(mock_client.calls['plan_repair']) == 2
    assert workflow.rewriter.repair.call_count == 1
    assert workflow.require_state(project_id).repair_baseline == RepairBaseline.model_validate(plan_payload()['baseline'])


async def test_recheck_receives_persisted_baseline(tmp_path, mock_client):
    workflow, project_id, report = await reviewed_workflow(tmp_path, mock_client)
    mock_client.set_response('plan_repair', plan_payload())
    await workflow.repair_from_verification(project_id, based_on_report=report.review_token)
    restarted = StoryBridgeWorkflow(workflow.store, mock_client)
    mock_client.set_response('verify_consistency', VerifyReport().model_dump(mode='json'))
    await restarted.verify(project_id)
    prompt = mock_client.calls['verify_consistency'][-1].user_prompt
    assert '交换后锁定' in prompt and '角色甲' in prompt
