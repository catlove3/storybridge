"""Package only the current presentation and its reviewable supporting evidence."""
import hashlib,json,shutil,zipfile
from pathlib import Path
import fitz

R=Path(__file__).resolve().parent;P=R.parent
deck=P/'StoryBridge_智理杯_5分钟展示.pptx'
sha=hashlib.sha256(deck.read_bytes()).hexdigest()
qa=json.loads((R/'powerpoint_validation.json').read_text(encoding='utf-8-sig'))
artifact=json.loads((R/'artifact_validation.json').read_text())
browser=json.loads((R/'browser_validation.json').read_text())
order=json.loads((R/'deck_order.json').read_text())
assert sha==qa['pptxSha256']==artifact['pptx_sha256']
assert sha==order['pptx_sha256']==browser['pptx_sha256']
assert qa['slides']==order['total_slides'] and qa['hiddenSlides']==order['hidden_slides']
assert qa['visiblePlaybackOrder']==list(range(1,order['main_slides']+1))
assert not qa['textOverflow'] and not browser['overflow']
assert qa['playback']['positionAfter2s']>1000 and qa['playback']['durationMs']==18000
assert 'playbackError' not in qa
with fitz.open(R/'preview.pdf') as doc:
 assert len(doc)==order['total_slides']
 assert '谢谢大家' in doc[order['thanks_slide']-1].get_text()
 assert '中文摘译' in doc[order['role_pages']['comparison']-1].get_text()
shutil.copyfile(R/'preview.pdf',P/'StoryBridge_离线展示.pdf')

files={}
for name in ['StoryBridge_智理杯_5分钟展示.pptx','StoryBridge_离线展示.pdf','StoryBridge_18秒操作演示.mp4','StoryBridge_5分钟讲稿.md','StoryBridge_展示提纲.md','StoryBridge_现场使用说明.md','StoryBridge_产品海报.png','StoryBridge_产品海报_A3.pdf','README.md']:
 files[name]=P/name
for name in ['实验说明.md','完整故事与改稿.md','poster_prompt.md','source.md']:
 files['备答材料/'+name]=R/name
for name in ['state_v1.json','state_v2.json','storybridge.json','naive_full.md','naive_prompt.md','naive_protocol.json','naive_response.json','paired_brief.json','propagation.json','quote_provenance.json','slide_graph.json','apply.json','done.json']:
 files['备答材料/evidence/'+name]=R/'evidence'/name
for name in ['artifact_validation.json','powerpoint_validation.json','browser_validation.json','video_validation.txt','recording_manifest.json','deck_order.json','navigation_sync.json']:
 files['验证记录/'+name]=R/name
for name in ['s03_diff.png','s03_impact.png','graph_screen.png']:
 files['备答材料/真实产品截图/'+name]=R/'assets'/name

# Keep current comparison calls exactly as logged, without config or credentials.
rows=[line for line in (R/'evidence/calls.jsonl').read_text().splitlines() if json.loads(line)['group'] in ('storybridge','naive_full')]
calls='\n'.join(rows)+'\n'
manifest={name:{'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size} for name,path in files.items()}
manifest['备答材料/evidence/current_calls.jsonl']={'sha256':hashlib.sha256(calls.encode()).hexdigest(),'bytes':len(calls.encode())}
dest=P/'StoryBridge_展示交付包.zip'
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
 for name,path in files.items():z.write(path,name)
 z.writestr('备答材料/evidence/current_calls.jsonl',calls)
 z.writestr('验证记录/文件清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(dest) as z:assert z.testzip() is None
(R/'delivery_manifest.json').write_text(json.dumps({'zip':dest.name,'files':manifest,'pptx_sha256':sha,'windows_native_passed':True,'mac_native_tested':False,'pdf_pages':order['total_slides'],'total_files':len(manifest)+1},ensure_ascii=False,indent=2))
print(json.dumps({'pptx':deck.name,'pdf_pages':order['total_slides'],'main_slides':order['main_slides'],'hidden_slides':order['hidden_slides'],'zip_files':len(manifest)+1,'zip_mb':round(dest.stat().st_size/1024/1024,2),'windows_video_playback_ms':qa['playback']['positionAfter2s'],'mac_native_tested':False},ensure_ascii=False))
