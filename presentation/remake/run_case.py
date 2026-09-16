"""Real paired case for the revised pitch. Every output is preserved unedited."""
from __future__ import annotations
import asyncio, hashlib, json, os, sys, time
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'backend'))
for name,rel in [('DATABASE_FILE','runtime/storybridge.sqlite3'),('PROJECTS_DIR','runtime/projects'),('RUN_LOG_DIR','runtime/run_logs'),('JOBS_FILE','runtime/jobs.json')]:
 os.environ['STORYBRIDGE_'+name]=str(ROOT/rel)
from app.config import get_config
from app.llm import build_router
from app.baselines.runner import BaselineRunner
from app.privacy import project_data_context
from app.storage import MarketProfile
from app.workflow.engine import build_default_workflow

BRIEF='''把这部短剧搬到美国背景，把高考替考骗局改编为中介伪造赛艇运动员履历、企图借体育招募进入名校的骗局。小宁从未练过赛艇。人物、学校、赛事、俱乐部均为虚构。保留父亲的名校执念、小宁对画画的热爱、朋友先埋线索后带来原始材料、再次索费、主动揭穿、放弃假资格，以及最后凭自己画作申请的父女和解。新骗局的材料和证据必须与赛艇履历对应；不要编造万能的官方查询网站，也不要让一张证书自动保证录取。人物的身份和经历可以随新骗局调整。用能拍出来的动作和简短对白写故事，保留七场顺序。'''

def dump(name,data):
 (ROOT/'evidence').mkdir(parents=True,exist_ok=True)
 (ROOT/'evidence'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
class Recorder:
 def __init__(self,inner):self.inner=inner;self.group='storybridge'
 def profile_for_step(self,step):return self.inner.profile_for_step(step)
 async def complete(self,request):
  start=time.monotonic();response=await self.inner.complete(request)
  row={'group':self.group,'request':asdict(request),'response':asdict(response),'seconds':round(time.monotonic()-start,3)}
  with (ROOT/'evidence/calls.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  print(self.group,request.step,round(time.monotonic()-start,1),flush=True)
  return response
async def main():
 config=get_config()
 for step in config.llm.step_routes:config.llm.step_routes[step]=config.llm.default_profile
 client=Recorder(build_router());wf=build_default_workflow(client);runner=BaselineRunner(wf,client)
 source=(ROOT/'source.md').read_text()
 profile=MarketProfile(market='United States',audience='18–35',format='Short drama',genre='Family suspense',source_language='zh-CN',target_language='English',target_locale='en-US',style_guide=BRIEF)
 dump('protocol.json',{'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'brief':BRIEF,'model':config.llm.profile_for_step('rewrite_scene').model,'comparison':'One paired illustrative case: direct translation, strong whole-script adaptation, StoryBridge. Not a benchmark superiority claim.','scope':'No output edits. Same selected creative plan also supplied to strong baseline.'})
 project=await wf.create_project('不是我的成绩 · 高考替考 → 赛艇履历造假',source,profile)
 dump('project.json',project.model_dump(mode='json'));print('PROJECT',project.id,flush=True)
 state=await wf.analyze(project.id);dump('state_v1.json',state.model_dump(mode='json'))
 # Change the overall admissions mechanism, not only the late reveal "替考".
 # A narrow selection is archived separately as setup, never passed off as success.
 ranked=sorted(state.culture_mechanisms,key=lambda m:('高考' in m.name,len(m.scene_ids),'替考' in m.name),reverse=True)
 cm=ranked[0]
 plan=await wf.plan(project.id,cm.id);dump('plan.json',plan.model_dump(mode='json'))
 opts=[o for o in plan.options if o.option_label!='A' and '赛艇' in o.replacement_definition]
 if not opts:raise RuntimeError('No rowing adaptation: inspect the real plan rather than fabricating one.')
 opt=max(opts,key=lambda o:('赛艇' in o.title,o.option_label=='C'))
 propagation=wf.propagate(project.id,cm.id);dump('propagation.json',propagation.model_dump(mode='json'))
 paired=profile.model_copy(update={'style_guide':BRIEF+'\n选定的同一改编方案：'+json.dumps(opt.model_dump(mode='json'),ensure_ascii=False)})
 dump('paired_brief.json',paired.model_dump(mode='json'));print('PLAN',cm.id,opt.title,flush=True)
 for group,method,p in [('translate',runner.run_baseline_translate,profile),('strong',runner.run_baseline_strong_prompt,paired)]:
  client.group=group
  with project_data_context(project.id,project.data_policy):target=await method(source,p,[s.id for s in state.scenes])
  dump(group+'.json',target.model_dump(mode='json'))
 client.group='storybridge'
 result=await wf.apply_adaptation(project.id,cm.id,opt.option_label,based_on_version=state.version)
 dump('apply.json',result.model_dump(mode='json'));dump('state_v2.json',wf.require_state(project.id).model_dump(mode='json'))
 target=await wf.render_target_script(project.id);dump('storybridge.json',target.model_dump(mode='json'))
 dump('done.json',{'project_id':project.id,'mechanism_id':cm.id,'option':opt.model_dump(mode='json'),'status':result.report.overall_status,'rewritten_scenes':result.applied.rewritten_scene_ids,'repair_rounds':result.repair_rounds,'repaired_scenes':result.repaired_scene_ids})
 print('DONE',result.report.overall_status,flush=True)
if __name__=='__main__':asyncio.run(main())
