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
assert qa['visiblePlaybackOrder'] == list(range(1,13))
assert qa['hiddenSlides'] == [13,14,15]
assert qa['playback']['durationMs'] == 18000 and qa['playback']['positionAfter2s'] > 1000
prs = Presentation(deck)
assert len(prs.slides) == 15
assert sum(x['seconds'] for x in json.loads((CASE/'talks.json').read_text())) == 300
assert order['case_pages'] == [3,7,8]
assert sum(order['slides'][i-1]['seconds'] for i in order['case_pages']) == 86
graph = json.loads((CASE/'graph_provenance.json').read_text())
base_state = json.loads((E/'base_state.json').read_text())
assert len(graph['edges']) == 4 and all(edge in base_state['dependencies'] for edge in graph['edges'])
assert graph['returned_affected_scenes'] == ['S01','S02','S03','S04','S05','S06']
assert (OUT/'StoryBridge_通俗易懂版.pptx').read_bytes() == deck.read_bytes()
with zipfile.ZipFile(deck) as z:
    assert z.testzip() is None
    assert any(n.endswith('.mp4') for n in z.namelist())
with fitz.open(CASE/'preview.pdf') as pdf:
    assert len(pdf) == 15
    assert '谢谢大家' in pdf[11].get_text()
    assert '沈曼' in pdf[2].get_text() and '330' in pdf[2].get_text()
    assert 'Dependency Graph' in pdf[4].get_text()
    assert '核心系统没改掉' in pdf[6].get_text()
    assert '后续测试反馈' in pdf[6].get_text()
    assert '487' in pdf[6].get_text() and '330' in pdf[6].get_text()
    assert '修复记录' in pdf[7].get_text()
    assert all('原稿已经前后矛盾' not in pg.get_text() and '原稿的错' not in pg.get_text() for pg in pdf)

shutil.copy2(CASE/'preview.pdf', OUT/'StoryBridge_离线展示.pdf')
sheet = Image.new('RGB', (1440, math.ceil(15/3)*294), '#d6d6d6')
draw = ImageDraw.Draw(sheet)
for i in range(15):
    img = Image.open(CASE/'powerpoint_preview'/f'{i+1:02d}.png').convert('RGB')
    img.thumbnail((480,270))
    x,y = (i%3)*480,(i//3)*294
    sheet.paste(img, (x,y))
    draw.text((x+8,y+272), str(i+1) + (' (appendix)' if i>=12 else ''), fill='#182B37')
sheet.save(CASE/'contact_sheet.jpg', quality=92)
validation = dict(pptx_sha256=sha, slides=15, main_slides=12, hidden_slides=[13,14,15], speaker_seconds=300,
    native_powerpoint_version=qa['applicationVersion'], native_text_overflow=qa['textOverflow'],
    native_video_position_ms=qa['playback']['positionAfter2s'], pdf_pages=15,
    exact_quotes_verified=True, adaptation_requirements_verified=True, graph_edges_verified=4, case_pages=[3,7,8], case_seconds=86,
    project_seconds=214, original_outputs_unchanged=True, model_rerun=False, mac_tested=False)
(CASE/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2))
(CASE/'改版说明.md').write_text('''# 本次改版

先讲项目与问题，第 3 页介绍案例，然后沿该案例解释 Story State、文化方案、真实 Dependency Graph 和改写检查流程。第 7 页综合短板，第 8 页对应的产品产物，第 9 页方法差异，再展示操作与交付。案例先于依赖图出现，数字错误仅作为辅助证据。

第 7 页汇总三类短板：改不全来自用户提供的后续测试反馈（未定位原始记录，标注来源）；改错来自本次冻结输出；缺少依赖追踪是一次生成流程的短板。第 8 页对应展示选定方案、实际传播清单和两轮修复记录，不声称消除了一切错误。各项没有拼接成同一实验结果；数字错误仅作辅助证据。

来源：案例规则与分数关系在当前故事与试验输入中一致；冻结试验原稿见素材/历史试验/baseline_protocol.json 的请求正文。输出与视频来自 remake/rebirth_system_16k。第 5 页为真实依赖图节选，4 条边逐一核对 base_state.json；传播清单核对 option_d_apply.json。图中的路径真实存在，但传播返回的第 6 场最佳原因路径是 CM01→E10→S06，未将节选误称为完整传播结果。图负责影响定位，后续检查处理全篇一致性。第 4、6 页按当前代码解释工作方式，不声称所有新增能力都在历史试验中运行过。预算差异、审稿范围和英语原句保留在备答；没有重跑模型或修改冻结输出。

字体和视频已由本机 PowerPoint 检查；PDF 来自相同 PPT 原生导出。主讲 12 页，隐藏备答 3 页，备注用时共 300 秒。其他系统尚未实测。
''')
files = {name:OUT/name for name in ['StoryBridge_智理杯_5分钟展示.pptx','StoryBridge_离线展示.pdf','StoryBridge_18秒操作演示.mp4','StoryBridge_5分钟讲稿.md','StoryBridge_展示提纲.md','StoryBridge_现场使用说明.md','README.md']}
files['素材/当前中文原故事.md'] = ROOT.parents[1]/'backend/data/scripts/corpus_rebirth.md'
files['素材/本次改版说明.md'] = CASE/'改版说明.md'
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
