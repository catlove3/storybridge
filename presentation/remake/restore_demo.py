"""Restore actual API outputs for UI playback, with an explicit replay prefix."""
import json,time
from run_case import ROOT,get_config
from app.sqlite_storage import SQLiteProjectStore
from app.storage import ProjectMeta
from app.schemas import StoryState,AdaptationPlan
from app.jobs import Job,SQLiteJobPersistence

c=get_config();store=SQLiteProjectStore(c.storage.database_file,c.storage.projects_dir)
p=ROOT/'evidence'
project=ProjectMeta.model_validate_json((p/'project.json').read_text())
state=StoryState.model_validate_json((p/'state_v1.json').read_text())
plan=AdaptationPlan.model_validate_json((p/'plan.json').read_text())
replay_file=ROOT/'replay.json'
before=store.load_meta(json.loads(replay_file.read_text())['before_project']) if replay_file.exists() else None
if before is None:
 before=store.create_project('演示回放 · 选择赛艇改编方案',project.script_text,project.market)
 store.save_state(before.id,state,kind='initial_parse',description='Replay of the unedited saved real parse; no new inference.')
 store.save_plan(before.id,plan)
persist=SQLiteJobPersistence(c.storage.database_file);jobs=[Job.model_validate(x) for x in persist.load()]
now=time.time()
for pid,kind,payload in [(before.id,'plan',plan.model_dump(mode='json')),(project.id,'plan',plan.model_dump(mode='json')),(project.id,'apply',json.loads((p/'apply.json').read_text()))]:
 key=f'replay-{pid}-{kind}'
 jobs.append(Job(id=key,project_id=pid,kind=kind,status='done',created_at=now,finished_at=now,result=payload,progress=1))
persist.save(jobs)
(ROOT/'replay.json').write_text(json.dumps({'before_project':before.id,'after_project':project.id,'description':'Actual saved workflow results restored in real app; before clone retains identical state and plan.'},ensure_ascii=False,indent=2))
print(before.id,project.id)
