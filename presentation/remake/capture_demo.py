"""Record real browser interactions against the running, unmodified app."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets';ASSETS.mkdir(exist_ok=True)
RAW=ROOT/'recordings';RAW.mkdir(exist_ok=True)
replay=json.loads((ROOT/'replay.json').read_text())

def position(page,loc,offset=30):
 loc.evaluate('(e,off)=>window.scrollTo({top:e.getBoundingClientRect().top+window.scrollY-off,behavior:"instant"})',offset)
 page.wait_for_timeout(200)

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1280,'height':720},device_scale_factor=1,record_video_dir=str(RAW),record_video_size={'width':1280,'height':720})
 page=context.new_page();start=time.monotonic();segments=[]
 page.goto('http://127.0.0.1:5174/?project='+replay['before_project'],wait_until='networkidle')
 card=page.locator('.option-card').filter(has_text='用美国大学体育招募')
 card.wait_for(timeout=20000)
 position(page,card,25)
 page.screenshot(path=str(ASSETS/'plan.png'))
 t=time.monotonic()-start
 page.wait_for_timeout(1000)
 button=card.get_by_role('button')
 button.scroll_into_view_if_needed()
 button.hover();page.wait_for_timeout(450);button.click()
 page.locator('.graph-section').wait_for(timeout=15000)
 page.wait_for_timeout(850)
 segments.append({'name':'选择赛艇改编方案','start':t,'end':time.monotonic()-start})
 graph=page.locator('.graph-section');position(page,graph,12)
 graph.screenshot(path=str(ASSETS/'graph_full.png'))
 t=time.monotonic()-start
 canvas=page.locator('.story-graph__canvas');canvas.hover()
 page.wait_for_timeout(1100)
 page.locator('.graph-nodes g').filter(has_text='S03').evaluate('(e)=>e.scrollIntoView({block:"center",behavior:"smooth"})')
 page.wait_for_timeout(2100)
 segments.append({'name':'沿依赖找到第三场','start':t,'end':time.monotonic()-start})
 page.screenshot(path=str(ASSETS/'graph_screen.png'))
 impact=page.locator('.affected-scenes article').filter(has_text='S03')
 impact.screenshot(path=str(ASSETS/'s03_impact.png'))
 page.goto('http://127.0.0.1:5174/?project='+replay['after_project'],wait_until='networkidle')
 diff=page.locator('.diff-card').filter(has_text='S03')
 diff.wait_for(timeout=20000)
 # Normal browser zoom for presentation readability; never replace UI content.
 page.evaluate('document.body.style.zoom="1.7"')
 diff.evaluate('(e)=>e.scrollIntoView({block:"center",behavior:"instant"})')
 page.wait_for_timeout(200)
 diff.screenshot(path=str(ASSETS/'s03_diff.png'))
 t=time.monotonic()-start
 page.mouse.move(350,310);page.wait_for_timeout(800);page.mouse.move(925,350,steps=20)
 diff.locator('.before-after > div').last.locator('p').evaluate('''(e)=>{
  const phrase='真实队员名单和座位安排表';const text=e.firstChild;const i=text.textContent.indexOf(phrase);
  if(i>=0){const r=document.createRange();r.setStart(text,i);r.setEnd(text,i+phrase.length);const s=window.getSelection();s.removeAllRanges();s.addRange(r);}
 }''')
 page.wait_for_timeout(3200)
 segments.append({'name':'朋友与证据一起改','start':t,'end':time.monotonic()-start})
 page.screenshot(path=str(ASSETS/'diff_screen.png'))
 payoff=page.locator('#final-script .script-scenes article').filter(has_text='S07')
 page.evaluate('window.getSelection().removeAllRanges()')
 payoff.evaluate('(e)=>e.scrollIntoView({block:"center",behavior:"instant"})')
 t=time.monotonic()-start;page.wait_for_timeout(2800)
 segments.append({'name':'留下父女和解的结尾','start':t,'end':time.monotonic()-start})
 page.screenshot(path=str(ASSETS/'ending_screen.png'))
 raw_path=page.video.path();context.close();browser.close()
 (ROOT/'recording_manifest.json').write_text(json.dumps({'raw_video':str(raw_path),'segments':segments,'description':'Live interactions with the real React app. Saved real workflow results; generation wait omitted. No fabricated interface or model text.'},ensure_ascii=False,indent=2))
 print(json.dumps(segments,ensure_ascii=False))
