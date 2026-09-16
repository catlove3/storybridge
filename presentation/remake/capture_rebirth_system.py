"""Record the real UI reading the frozen APC/EduSwap StoryBridge result."""
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
CASE=ROOT/'rebirth_system_16k'
EVIDENCE=CASE/'evidence'
ASSETS=CASE/'assets';ASSETS.mkdir(parents=True,exist_ok=True)
RECORDINGS=CASE/'recordings';RECORDINGS.mkdir(parents=True,exist_ok=True)
base=json.loads((EVIDENCE/'project.json').read_text())['id']
after=json.loads((EVIDENCE/'option_d_project.json').read_text())['id']

def set_progress(page,owner,project_id,selected,labels,view):
    payload={'projectId':project_id,'selected':selected,'labels':labels,'task':None,'view':view}
    page.evaluate("([k,v])=>localStorage.setItem(k,JSON.stringify(v))",[f'storybridge.v2.{owner}.active',payload])

def center(page,locator):
    locator.evaluate('(e)=>e.scrollIntoView({block:"center",behavior:"instant"})')
    page.wait_for_timeout(250)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1280,'height':720},device_scale_factor=1,record_video_dir=str(RECORDINGS),record_video_size={'width':1280,'height':720})
    page=context.new_page();page.goto('http://127.0.0.1:5175',wait_until='networkidle')
    owner=page.evaluate("async()=>{const r=await fetch('/api/session',{method:'POST'});return (await r.json()).visitor_id}")
    set_progress(page,owner,base,['CM01','CM10'],{'CM01':'C','CM10':'C'},'choose');page.reload(wait_until='networkidle')
    start=time.monotonic();segments=[]

    card=page.locator('.option-card').filter(has_text='EduSwap').last
    card.wait_for(timeout=20000);center(page,card);page.wait_for_timeout(800)
    page.screenshot(path=str(ASSETS/'system_plan.png'))
    t=time.monotonic()-start;card.locator('details').click();page.wait_for_timeout(1800)
    segments.append({'name':'查看 EduSwap 系统方案','start':t,'end':time.monotonic()-start})

    outer=page.locator('.plans > details');center(page,outer);outer.locator('summary').click();page.wait_for_timeout(1800)
    relation=outer.locator('.relation-list').first;center(page,relation)
    page.screenshot(path=str(ASSETS/'system_graph.png'))
    t=time.monotonic()-start;page.wait_for_timeout(2200)
    segments.append({'name':'查看依赖图与影响范围','start':t,'end':time.monotonic()-start})

    set_progress(page,owner,after,['CM01','CM10'],{'CM01':'C','CM10':'C'},'result');page.reload(wait_until='networkidle')
    scene6=page.locator('.results .script-scenes article').filter(has_text='Replay · Score Release')
    scene6.wait_for(timeout=20000);center(page,scene6);page.wait_for_timeout(700)
    page.screenshot(path=str(ASSETS/'system_s06.png'))
    t=time.monotonic()-start;page.wait_for_timeout(2600)
    segments.append({'name':'核对三人分数反转','start':t,'end':time.monotonic()-start})

    scene10=page.locator('.results .script-scenes article').filter(has_text='The Trial')
    center(page,scene10);page.wait_for_timeout(600)
    page.screenshot(path=str(ASSETS/'system_s10.png'))
    t=time.monotonic()-start;page.wait_for_timeout(2200)
    segments.append({'name':'核对法庭场景的 330','start':t,'end':time.monotonic()-start})
    raw=page.video.path();context.close();browser.close()

(CASE/'recording_manifest.json').write_text(json.dumps({'raw_video':str(raw),'segments':segments,'description':'Real React UI reading frozen StoryBridge APC/EduSwap outputs. Model waiting omitted; no generated text altered.'},ensure_ascii=False,indent=2))
print(json.dumps({'owner':owner,'base':base,'after':after,'segments':segments},ensure_ascii=False))
