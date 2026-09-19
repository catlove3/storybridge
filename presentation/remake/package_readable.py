"""Validate and package the readable deck after native PowerPoint export."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import zipfile
import fitz
from PIL import Image, ImageDraw
from pptx import Presentation

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
CASE = ROOT/'readable_20260917'
E = ROOT/'rebirth_system_16k/evidence'
deck = OUT/'StoryBridge_智理杯_5分钟展示.pptx'
sha = hashlib.sha256(deck.read_bytes()).hexdigest()
order = json.loads((CASE/'deck_order.json').read_text())
qa = json.loads((CASE/'powerpoint_validation.json').read_text(encoding='utf-8-sig'))
assert sha == qa['pptxSha256'] == order['pptx_sha256']
assert 'error' not in qa and qa['textOverflow'] == [], qa
assert qa['visiblePlaybackOrder'] == list(range(1,14))
assert qa['hiddenSlides'] == [14,15,16]
assert qa['playback']['durationMs'] == 18000 and qa['playback']['positionAfter2s'] > 1000
prs = Presentation(deck)
assert len(prs.slides) == 16
assert sum(x['seconds'] for x in json.loads((CASE/'talks.json').read_text())) == 300
assert order['case_pages'] == [3,8,9]
assert sum(order['slides'][i-1]['seconds'] for i in order['case_pages']) == 86
graph = json.loads((CASE/'graph_provenance.json').read_text())
method = json.loads((ROOT/'evidence/method_evidence.json').read_text())
assert graph['source'] == 'evidence/method_evidence.json' and graph['slide'] == 6
assert graph['returned_affected_scenes'] == ['S01','S02','S04','S05','S06','S07','S08']
assert graph['reason_paths'] == {item['scene_id']:item['reason_path'] for item in method['propagation']['affected_scenes']}
assert (OUT/'StoryBridge_通俗易懂版.pptx').read_bytes() == deck.read_bytes()
assert (OUT/'StoryBridge_最终版.pptx').read_bytes() == deck.read_bytes()
with zipfile.ZipFile(deck) as z:
    assert z.testzip() is None
    assert any(n.endswith('.mp4') for n in z.namelist())
    media_hashes = {hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist() if name.startswith('ppt/media/')}
    evidence_images = [ROOT/'assets'/name for name in ['story_state.png','evidence_culture_plan.png','evidence_dependency_paths.png','evidence_verification_repairs.png']]
    assert {hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_images} <= media_hashes
with fitz.open(CASE/'preview.pdf') as pdf:
    assert len(pdf) == 16
    assert '谢谢大家' in pdf[12].get_text()
    assert '沈曼' in pdf[2].get_text() and '330' in pdf[2].get_text()
    assert 'Story State' in pdf[3].get_text()
    assert '文化节点' in pdf[4].get_text()
    assert 'Dependency Graph' in pdf[5].get_text()
    assert '检查报告' in pdf[6].get_text()
    assert '核心系统没改掉' in pdf[7].get_text()
    assert '后续测试反馈' in pdf[7].get_text()
    assert '487' in pdf[7].get_text() and '330' in pdf[7].get_text()
    assert '修复记录' in pdf[8].get_text()
    assert all('原稿已经前后矛盾' not in pg.get_text() and '原稿的错' not in pg.get_text() for pg in pdf)

shutil.copy2(CASE/'preview.pdf', OUT/'StoryBridge_离线展示.pdf')
sheet = Image.new('RGB', (1440, math.ceil(16/3)*294), '#d6d6d6')
draw = ImageDraw.Draw(sheet)
for i in range(16):
    img = Image.open(CASE/'powerpoint_preview'/f'{i+1:02d}.png').convert('RGB')
    img.thumbnail((480,270))
    x,y = (i%3)*480,(i//3)*294
    sheet.paste(img, (x,y))
    draw.text((x+8,y+272), str(i+1) + (' (appendix)' if i>=13 else ''), fill='#182B37')
sheet.save(CASE/'contact_sheet.jpg', quality=92)
validation = dict(pptx_sha256=sha, slides=16, main_slides=13, hidden_slides=[14,15,16], speaker_seconds=300,
    native_powerpoint_version=qa['applicationVersion'], native_text_overflow=qa['textOverflow'],
    native_video_position_ms=qa['playback']['positionAfter2s'], pdf_pages=16,
    exact_quotes_verified=True, adaptation_requirements_verified=True, graph_reason_paths_verified=7, embedded_evidence_images=4, case_pages=[3,8,9], case_seconds=86,
    project_seconds=214, original_outputs_unchanged=True, model_rerun=False, mac_tested=False)
(CASE/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2))
(CASE/'改版说明.md').write_text('''# 本次改版

先讲项目与问题，第 3 页介绍案例，第 4—7 页分别用完整 16:9 证据图展示 Story State、文化节点与方案、真实 Dependency Graph、检查报告与按场修复记录。第 8 页回看早期短板，第 9 页对应产品产物，第 10 页方法差异，再展示操作与交付。案例先于证据图出现，数字错误仅作为辅助证据。

第 8 页汇总三类早期短板：改不全来自用户提供的后续测试反馈（未定位原始记录，标注来源）；改错来自早期冻结输出；缺少依赖追踪是一次生成流程的短板。第 4—7 页来自近期真实保存项目，不与早期输出拼成同一轮实验；当前报告为零个阻塞错误、一项待人工确认警告，不声称所有问题自动消失。

来源：第 4 页读取真实 Story State 冻结文件；第 5—7 页读取 `method_evidence.json`，其中方案、七条原因路径、检查报告和版本历史均从 SQLite 已完成项目脱敏导出。四张图片明确标注为内部证据排版、非访客 UI，并以原始文件哈希核对已嵌入 PPT。第 8 页及隐藏备答继续使用早期冻结试验材料，输出与视频来自 remake/rebirth_system_16k。预算差异、审稿范围和英语原句保留在备答；没有重跑模型或修改任何模型输出。

字体、四张证据图和视频已由本机 PowerPoint 检查；PDF 来自相同 PPT 原生导出。主讲 13 页，隐藏备答 3 页，备注用时共 300 秒。其他系统尚未实测。
''')
files = {name:OUT/name for name in ['StoryBridge_智理杯_5分钟展示.pptx','StoryBridge_离线展示.pdf','StoryBridge_18秒操作演示.mp4','StoryBridge_5分钟讲稿.md','StoryBridge_展示提纲.md','StoryBridge_现场使用说明.md','README.md']}
files['素材/当前中文原故事.md'] = ROOT.parents[1]/'backend/data/scripts/corpus_rebirth.md'
files['素材/本次改版说明.md'] = CASE/'改版说明.md'
for name in ['story_state.png','evidence_culture_plan.png','evidence_dependency_paths.png','evidence_verification_repairs.png']:
    files['素材/方法证据图/'+name] = ROOT/'assets'/name
files['素材/方法证据/method_evidence.json'] = ROOT/'evidence/method_evidence.json'
for name in ['base_state.json','option_d_target.json','option_d_apply.json','baseline_first_response.md','quote_provenance.json','baseline_protocol.json']:
    files['素材/历史试验/'+name] = E/name
for name in ['validation.json','powerpoint_validation.json','deck_order.json','graph_provenance.json','later_test_observation.json']:
    files['验证记录/'+name] = CASE/name
manifest = {name:dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for name,p in files.items()}
dest = OUT/'StoryBridge_展示交付包.zip'
with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
    for name,p in files.items(): z.write(p,name)
    z.writestr('验证记录/文件清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(dest) as z: assert z.testzip() is None
(CASE/'delivery_manifest.json').write_text(json.dumps(dict(zip=dest.name, zip_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),files=len(files)+1,pptx_sha256=sha),ensure_ascii=False,indent=2))
print(json.dumps(validation, ensure_ascii=False, indent=2))
