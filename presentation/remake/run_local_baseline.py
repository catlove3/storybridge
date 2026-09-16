"""Component ablation: lexical scope + the same real scene rewriter.

This is explicitly a constructed local-edit baseline, not a claim that strong
whole-script prompting has the same limitation. Global verification is omitted.
"""
import asyncio,json
from run_case import ROOT,Recorder,dump,get_config,build_router,build_default_workflow
from app.schemas import StoryState,AdaptationPlan,PropagationResult,AffectedScene,ImpactKind
from app.privacy import project_data_context
from app.storage import ProjectMeta

async def main():
 config=get_config()
 for step in config.llm.step_routes:config.llm.step_routes[step]=config.llm.default_profile
 client=Recorder(build_router());client.group='local_ablation';wf=build_default_workflow(client)
 state=StoryState.model_validate_json((ROOT/'evidence/state_v1.json').read_text())
 plan=AdaptationPlan.model_validate_json((ROOT/'evidence/plan.json').read_text())
 project=ProjectMeta.model_validate_json((ROOT/'evidence/project.json').read_text())
 option=next(o for o in plan.options if o.option_label!='A' and '赛艇' in o.replacement_definition)
 ids=[s.id for s in state.scenes if '高考' in s.text]
 propagation=PropagationResult(changed_node_id=plan.culture_mechanism_id,affected_scenes=[AffectedScene(scene_id=s,impact_kinds=[ImpactKind.DIRECT_REFERENCE],reason_path=[plan.culture_mechanism_id,s],evidence='Literal keyword 高考 occurs in source scene text.') for s in ids],summary='Constructed lexical local-edit ablation; no dependency propagation or global verifier.')
 dump('local_protocol.json',{'keywords':['高考'],'selected_scenes':ids,'same_model':True,'same_parsed_state':True,'same_option':option.model_dump(mode='json'),'same_scene_rewriter':True,'global_verification':False,'limitation':'Not the strong-prompt baseline; isolates the practical limitation of only editing explicit mentions.'})
 with project_data_context(project.id,project.data_policy):
  applied=await wf.rewriter.apply(state,plan.culture_mechanism_id,option,propagation)
  dump('local_state.json',state.model_dump(mode='json'))
  target=await wf.renderer.render(state)
 dump('local.json',target.model_dump(mode='json'));dump('local_applied.json',applied.model_dump(mode='json'))
 print('LOCAL DONE',ids,flush=True)
asyncio.run(main())
