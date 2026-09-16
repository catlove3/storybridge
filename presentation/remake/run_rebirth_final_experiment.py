"""Fresh StoryBridge vs one-shot run on the final 12-scene rebirth source."""
from __future__ import annotations
import asyncio, hashlib, json, os, re, sys, time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]
CASE=HERE/'rebirth_final_20260917'; E=CASE/'evidence'; RUNTIME=CASE/'runtime'
SOURCE=REPO/'backend/data/scripts/corpus_rebirth.md'
sys.path.insert(0,str(REPO/'backend'))
for k,v in [('DATABASE_FILE','storybridge.sqlite3'),('PROJECTS_DIR','projects'),('RUN_LOG_DIR','run_logs'),('JOBS_FILE','jobs.json')]:
    os.environ[f'STORYBRIDGE_{k}']=str(RUNTIME/v)

from app.config import get_config
from app.llm import build_router
from app.llm.base import LLMRequest
from app.schemas import AdaptationPlan,StoryState
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile
from app.workflow.engine import AdaptationSelection,StoryBridgeWorkflow

REQ="""把完整十二场重生悬疑短剧改编为美国背景和英语成稿。

硬性要求：
- 保持 S01-S12 与原顺序，不合并、不拆分。
- 保留核心爽剧结果：林知夏 669 不变；周雨原 330、换后 487；沈曼原 487、换后 330。周雨与林知夏结盟，周雨最终保住 487。
- S07 必须保留沈曼抢过周雨手机，看见 487 后脱口而出“你明明只有330”，以及周雨追问“成绩刚出，你怎么知道我原来的分数”。
- 换分系统是无法由现实技术解释的超自然规则，不设置系统工作人员、技术员、黑客、服务器或后台日志，不加入“前程卡”、仪式、百日用笔等新规则。
- 系统边界保持清楚：借笔人的成绩与笔原主人的最终公布成绩对调；系统只认笔的原主人；成绩公布后交换锁定，无法撤回。
- 只有林知夏记得前世。沈曼不得承认或记得前世谋杀；她在本世只承认企图偷走 669，并在天台现实地威胁、袭击林知夏。
- 庭审不得把前世或超自然系统当成可验证案件。现实定罪只依据本世的死亡威胁、直播/录像、现场证据和实际推人行为；330/487 只用于解释动机与说漏嘴。
- 清算克制、现实，不写三天破产、股价连跌等夸张连锁。结尾以轻微超自然迹象保留悬念，不大段解释系统。
- 教育、学校和司法机构均使用虚构名称；美国背景对目标观众清楚可信。
- 台词简短、动作可拍，类型为 rebirth suspense revenge vertical drama。
"""

def dump(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise RuntimeError(f'refusing to overwrite {path}')
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
def load(path): return json.loads(path.read_text(encoding='utf-8'))

class Recorder:
    def __init__(self,inner,group): self.inner,self.group=inner,group
    def profile_for_step(self,step): return self.inner.profile_for_step(step)
    async def complete(self,request):
        t=time.monotonic()
        try: response=await self.inner.complete(request)
        except Exception as exc:
            E.mkdir(parents=True,exist_ok=True)
            with (E/'failures.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'group':self.group,'step':request.step,'error':repr(exc)},ensure_ascii=False)+'\n')
            raise
        row={'time':datetime.now(timezone.utc).isoformat(),'group':self.group,'request':asdict(request),'response':asdict(response),'seconds':round(time.monotonic()-t,3)}
        E.mkdir(parents=True,exist_ok=True)
        with (E/'calls.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(self.group,request.step,f"{row['seconds']:.1f}s",response.finish_reason,response.completion_tokens,flush=True)
        return response

def profile():
    return MarketProfile(market='United States',audience='18-35 vertical-drama viewers',format='12-scene vertical short drama',genre='Rebirth suspense revenge drama',source_language='zh-CN',target_language='English',target_locale='en-US',style_guide=REQ,terminology_map={'林知夏':'Lin Zhixia','沈曼':'Shen Man','周雨':'Zhou Yu'})

def workflow(group):
    cfg=get_config(); cfg.llm.profiles[cfg.llm.default_profile].max_tokens=16384
    for step in cfg.llm.step_routes: cfg.llm.step_routes[step]=cfg.llm.default_profile
    client=Recorder(build_router(),group)
    wf=StoryBridgeWorkflow(SQLiteProjectStore(RUNTIME/'storybridge.sqlite3',RUNTIME/'projects'),client)
    if group=='prepare': wf.parser.chunk_threshold_chars=2000; wf.parser.chunk_chars=1400
    return wf

async def prepare():
    source=SOURCE.read_text(encoding='utf-8'); CASE.mkdir(parents=True,exist_ok=True)
    (CASE/'source.md').write_text(source,encoding='utf-8'); (CASE/'requirements.md').write_text(REQ,encoding='utf-8')
    wf=workflow('prepare'); project=await wf.create_project('重生爽剧最终复跑',source,profile()); state=await wf.analyze(project.id)
    ids=[s.id for s in state.scenes]; expected=[f'S{i:02d}' for i in range(1,13)]
    if ids!=expected: dump(E/'invalid_parse.json',state.model_dump(mode='json')); raise RuntimeError((ids,expected))
    mechanisms=[m.model_dump(mode='json') for m in state.culture_mechanisms]
    relevant=[]
    for m in state.culture_mechanisms:
        text=' '.join([m.name,m.description,*m.surface_text])
        if any(k in text for k in ('高考','考试','录取','换分','系统')): relevant.append(m)
    relevant=sorted(relevant,key=lambda m:(m.narrative_importance=='high',len(m.scene_ids)),reverse=True)[:3]
    plans=[]
    for m in relevant: plans.append((await wf.plan(project.id,m.id)).model_dump(mode='json'))
    dump(E/'project.json',project.model_dump(mode='json')); dump(E/'base_state.json',state.model_dump(mode='json')); dump(E/'mechanisms.json',mechanisms); dump(E/'plans.json',plans)
    dump(E/'protocol.json',{'created_at':datetime.now(timezone.utc).isoformat(),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'model':get_config().llm.profile_for_step('rewrite_scene').model,'max_tokens':16384,'requirements':REQ})
    print('PREPARED',project.id,[(m.id,m.name,m.scene_ids) for m in relevant],flush=True)

async def apply():
    selection=load(E/'selection.json'); base=StoryState.model_validate(load(E/'base_state.json')); plans=[AdaptationPlan.model_validate(x) for x in load(E/'plans.json')]
    wf=workflow('storybridge'); project=await wf.create_project('重生爽剧最终复跑·选定方案',(CASE/'source.md').read_text(),profile()); wf.store.save_state(project.id,base.model_copy(deep=True),kind='initial_parse',description='fresh parse clone')
    current=wf.require_state(project.id)
    for p in plans: p.based_on_version=current.version; wf.store.save_plan(project.id,p)
    sels=[AdaptationSelection(culture_mechanism_id=x['culture_mechanism_id'],option_label=x['option_label']) for x in selection]
    result=await wf.apply_adaptations(project.id,sels,based_on_version=current.version); target=await wf.render_target_script(project.id)
    dump(E/'storybridge_apply.json',result.model_dump(mode='json')); dump(E/'storybridge_state.json',wf.require_state(project.id).model_dump(mode='json')); dump(E/'storybridge_target.json',target.model_dump(mode='json'))
    print('STORYBRIDGE COMPLETE',result.report.overall_status,result.repaired_scene_ids,flush=True)

async def baseline():
    selection=load(E/'selection.json'); plans=load(E/'plans.json'); options=[]
    for s in selection:
        p=next(x for x in plans if x['culture_mechanism_id']==s['culture_mechanism_id']); options.append(next(x for x in p['options'] if x['option_label']==s['option_label']))
    req=LLMRequest(step='baseline_naive_full',system_prompt='You are a professional screenwriter.',user_prompt='Directly adapt the complete source into one complete American-English screenplay. Follow every requirement and the selected StoryBridge options. Return S01-S12 exactly once and in order. Do not merge or omit scenes.\n\n[COMPLETE SOURCE]\n'+(CASE/'source.md').read_text()+'\n\n[COMPLETE REQUIREMENTS]\n'+REQ+'\n\n[SELECTED OPTIONS]\n'+json.dumps(options,ensure_ascii=False,indent=2),json_mode=False)
    dump(E/'baseline_protocol.json',{'model':get_config().llm.profile_for_step('baseline_naive_full').model,'max_tokens':16384,'policy':'Freeze first complete response; retry only for technical failure or incomplete S01-S12.','request':asdict(req)})
    response=await workflow('baseline').rewriter.client.complete(req); dump(E/'baseline_response.json',asdict(response)); (E/'baseline_response.md').write_text(response.text,encoding='utf-8')
    heads=re.findall(r'(?im)^\s*(?:#{1,4}\s*)?(?:\*{1,2})?\[?(S\d{2})\b',response.text); expected=[f'S{i:02d}' for i in range(1,13)]
    dump(E/'baseline_validation.json',{'finish_reason':response.finish_reason,'headings':heads,'expected':expected,'complete':response.finish_reason!='length' and heads==expected})
    if response.finish_reason=='length' or heads!=expected: raise RuntimeError('baseline incomplete')
    print('BASELINE COMPLETE',response.finish_reason,response.completion_tokens,flush=True)

async def baseline_minimal():
    req=LLMRequest(
        step='baseline_naive_full',
        system_prompt='You are a professional screenwriter.',
        user_prompt='Adapt the following complete Chinese short drama into an American-set English vertical drama. Return the complete adapted screenplay with S01-S12 in order.\n\n'+(CASE/'source.md').read_text(),
        json_mode=False,
    )
    dump(E/'baseline_minimal_protocol.json',{'model':get_config().llm.profile_for_step('baseline_naive_full').model,'max_tokens':16384,'policy':'One call; no content requirements or StoryBridge option supplied.','request':asdict(req)})
    response=await workflow('baseline_minimal').rewriter.client.complete(req)
    dump(E/'baseline_minimal_response.json',asdict(response)); (E/'baseline_minimal_response.md').write_text(response.text,encoding='utf-8')
    heads=re.findall(r'(?im)^\s*(?:#{1,4}\s*)?(?:\*{1,2})?\[?(S\d{2})\b',response.text); expected=[f'S{i:02d}' for i in range(1,13)]
    dump(E/'baseline_minimal_validation.json',{'finish_reason':response.finish_reason,'headings':heads,'expected':expected,'complete':response.finish_reason!='length' and heads==expected})
    print('MINIMAL BASELINE COMPLETE',response.finish_reason,response.completion_tokens,heads,flush=True)

async def main():
    if sys.argv[1]=='prepare': await prepare()
    elif sys.argv[1]=='apply': await apply()
    elif sys.argv[1]=='baseline': await baseline()
    elif sys.argv[1]=='baseline-minimal': await baseline_minimal()
    else: raise SystemExit('prepare|apply|baseline|baseline-minimal')
if __name__=='__main__': asyncio.run(main())
