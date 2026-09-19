"""Plain-language deck; preserve the story and quote frozen outputs honestly."""
from pathlib import Path
import hashlib
import json
import shutil
import decklib
from decklib import Deck, WHITE, INK, MUTED, RED, GOLD, GREEN, LINE

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
CASE = ROOT / 'readable_20260917'
EVIDENCE = ROOT / 'rebirth_system_16k/evidence'
ASSETS = ROOT / 'rebirth_system_16k/assets'
CASE.mkdir(exist_ok=True)
decklib.ROOT = CASE
d = Deck(main_slide_count=13)
t, r, a = d.text, d.rect, d.arrow

def page(title, chapter, source='StoryBridge · 短剧出海改编助手', appendix=False):
    d.slide(title, chapter, source, appendix=appendix)

def card(x, y, w, h, label, title, body, color=GREEN):
    r(x, y, w, h, WHITE, LINE, True)
    t(label, x+.24, y+.22, w-.48, .34, 15, color, True)
    t(title, x+.24, y+.85, w-.48, .92, 27, INK, True)
    t(body, x+.24, y+1.95, w-.48, h-2.05, 22, INK)

def takeaway(text, color=GREEN):
    r(.72, 6.22, 11.90, .63, '#E7F0EC', None, True)
    t(text, .94, 6.37, 11.46, .38, 20, color, True, align='center')

# Main story: nine project pages, three supporting case pages.
from build_project_main import build_main
build_main(d, ASSETS, OUT, page, card, takeaway)

page('备答：两份稿的英语原句', '引用核对', '第 10 场 · 庭审台词原文', appendix=True)
q = json.loads((EVIDENCE/'quote_provenance.json').read_text())
target = json.loads((EVIDENCE/'option_d_target.json').read_text())
baseline = (EVIDENCE/'baseline_first_response.md').read_text()
# Assess both outputs against the explicit adaptation requirements.
protocol = json.loads((EVIDENCE/'baseline_protocol.json').read_text())['request']['user_prompt']
assert '周雨原 330、换后 487，沈曼原 487、换后 330' in protocol
assert q['storybridge_quote']['text'] in next(s['text'] for s in target['scenes'] if s['id']=='S10')
assert q['baseline_quote']['text'] in baseline
for x, label, quote, color in [(.76, 'StoryBridge · 第 10 场', q['storybridge_quote']['text'], GREEN), (6.89, '一次全文改编 · 第 10 场', q['baseline_quote']['text'], RED)]:
    r(x, 2.1, 5.70, 3.80, WHITE, LINE, True)
    t(label, x+.25, 2.39, 5.20, .47, 22, color, True)
    t(quote, x+.25, 3.23, 5.20, 2.29, 25, INK)
takeaway('核对依据：两份稿的第 6 场都写沈曼 330；第 10 场也应对应这个数字。')
d.notes(0, '这两段是早期冻结输出原句，用于支持主讲第八页“改错”一栏。改编要求为沈曼换后 330、周雨换后 487。主讲第一栏“核心系统未改掉”来自用户补充的后续测试反馈，未定位原始记录；第三栏是一次生成流程缺少依赖追踪带来的风险。三栏并非同一次输出的三项实测缺陷，也不要与第 4—7 页的近期真实项目混为同一轮运行。')

page('备答：比较方法与审稿范围', '案例说明', '完整记录随交付包提供', appendix=True)
items = [
    ('相同输入', '同一模型、完整十二场剧本、相同约束和选定改编方案。'),
    ('不同流程', '一次全文生成，与多阶段改写、检查、修复比较；预算不同。'),
    ('关系图缺口', '初始关系图未找出换分模块的后续场景；后续仍需检查。'),
    ('结论范围', '只核对这个案例；内部检查未全部通过，也没有统计胜率。'),
]
for i, (label, body) in enumerate(items):
    y = 2.04+i*1.04
    r(.77, y, 11.8, .86, WHITE, LINE, True)
    t(label, .98, y+.24, 2.1, .4, 21, GREEN, True)
    t(body, 3.22, y+.24, 9.04, .43, 21, INK)
d.notes(0, '早期对照模型为 deepseek-v4-flash，调用预算不同。第 4—7 页使用近期完成项目的真实保存结果，并明确标注为内部证据排版、非访客 UI。第 6 页从 method_evidence.json 逐条读取原因路径：CM01 返回 S01、S02、S04—S08 共七个场景，每项包含影响类型和原文证据。第 7 页读取同项目的 verification_reports 与 revisions：十二个场景和七项承诺均已检查，阻塞错误为零，仍有一项旧因果依赖边需要人工确认；右侧仅展示最后五轮修复记录。第 8 页的早期 Baseline 问题来自另一组冻结材料，不能声称与近期项目是同一轮输出。')

page('视频备用：这里引用的是沈曼的 330 分', '真实产品截图', '视频播放失败时跳到本页，结束后回到第 13 页', appendix=True)
d.picture(ASSETS/'system_s10.png', .74, 1.94, 11.86, 4.48)
takeaway('法庭原句：You saw 330.（你看到的是 330 分。）')
d.notes(0, '截图来自原有产品录像。指出法庭文字里的 You saw 330，与前面查分场景一致。讲完回到第十三页结束。')

assert sum(x['seconds'] for x in d.talks) == 300
deck = OUT/'StoryBridge_智理杯_5分钟展示.pptx'
d.save(deck)
shutil.copy2(deck, OUT/'StoryBridge_通俗易懂版.pptx')
shutil.copy2(deck, OUT/'StoryBridge_最终版.pptx')
shutil.copy2(deck, ROOT/'presentation.pptx')
rows = [dict(page=i, title=p['title'], hidden=p['appendix'], seconds=n['seconds']) for i, (p, n) in enumerate(zip(d.pages, d.talks), 1)]
manifest = dict(pptx_sha256=hashlib.sha256(deck.read_bytes()).hexdigest(), main_slides=13, total_slides=16, hidden_slides=[14,15,16], thanks_slide=13, video_slide=11, speaker_notes_seconds=300, slides=rows)
manifest.update(case_pages=[3,8,9], case_seconds=86, project_seconds=214, story_state_slide=4, culture_plan_slide=5, graph_slide=6, verification_slide=7, comparison_slide=9)
(CASE/'deck_order.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
elapsed = 0
md = ['# StoryBridge · 5 分钟讲稿', '', '13 页主讲：第 3 页案例，第 4—7 页用四张真实证据图讲 Story State、方案、依赖路径与检查修复，第 8 页回看早期短板，第 9—10 页总结产品优势与方法差异。另有 3 页隐藏备答；300 秒包含 18 秒视频。', '']
for i, talk in enumerate(d.talks, 1):
    end = elapsed + talk['seconds']
    md += [f'## {i}. {talk["title"]}', '', '隐藏备答。' if talk['appendix'] else f'{elapsed//60}:{elapsed%60:02d}–{end//60}:{end%60:02d}', '', talk['text'], '']
    elapsed = end
(OUT/'StoryBridge_5分钟讲稿.md').write_text('\n'.join(md))
(OUT/'StoryBridge_展示提纲.md').write_text('# StoryBridge · 展示提纲\n\n'+ '\n'.join(f'{x["page"]}. {x["title"]}'+('（隐藏备答）' if x['hidden'] else '') for x in rows)+'\n')
(OUT/'README.md').write_text('''# StoryBridge · 通俗易懂版

打开 `StoryBridge_最终版.pptx` 或 `StoryBridge_智理杯_5分钟展示.pptx`，两份内容一致。13 页主讲＋3 页隐藏备答；讲稿建议 5 分钟，包含第 11 页的 18 秒视频。

按案例贯穿方法：项目与问题 → 案例 → Story State → 文化节点与方案 → Dependency Graph → 检查与按场修复 → 早期测试短板 → 对应的产品优势 → 操作与交付。第 4—7 页分别使用真实保存结果生成的四张 16:9 证据图，并明确标注为内部证据排版、非访客 UI。第 8 页汇总“改不全、改错、缺少依赖追踪”；三栏分别来自后续测试反馈、早期冻结输出与流程对照，不能与第 4—7 页视为同一轮运行。本次没有重跑模型。

修改前文件在 `remake/readable_20260917/before/`。重建：`python3.12 presentation/remake/build_readable_deck.py`；重新导出与验证：运行同目录下 `verify_readable.ps1`，再运行 `package_readable.py`。不要用历史生成器覆盖本稿。

四张方法证据图位于 `remake/assets/story_state.png`、`evidence_culture_plan.png`、`evidence_dependency_paths.png`、`evidence_verification_repairs.png`。冻结数据与重建脚本见 `remake/evidence/method_evidence.json`、`export_method_evidence.py` 和 `render_method_evidence.mjs`。
''')
(OUT/'StoryBridge_现场使用说明.md').write_text('''# 现场使用说明

使用 `StoryBridge_最终版.pptx` 或比赛展示版（内容相同）。13 页主讲，第 13 页结束；第 14—16 页隐藏备答。备注与讲稿合计 300 秒，包含视频，实际语速需排练。

第 11 页点击播放 18 秒视频。不能播放时，打开同目录独立 MP4，或跳到第 16 页截图。PDF 含全部 16 页；第 11 页只有视频封面。

第 1—2 页项目与问题，第 3 页案例，第 4—7 页依次展示 Story State、文化节点与方案、依赖路径、检查与按场修复。第 8 页用早期测试归纳“改不全、改错、缺少依赖追踪”，第 9 页用实际产物说明如何应对，第 10 页总结流程优势。第 11 页操作演示，第 12 页交付价值，第 13 页收尾。

依赖图读法：CM 是文化设定，E 是事件，S 是场景。第 6 页左侧每一行是一条真实原因路径，右侧是对应场景与原文证据；本次 CM01 返回 S01、S02、S04—S08 共七个场景。第 7 页的检查报告继续核对全篇，所以修复范围可以超过某一个文化节点的传播结果。

对照重点是核心设定是否改全、结果是否正确、依赖是否可追踪。第 8 页第一栏来自用户提供的后续测试反馈，原始记录未定位；第二栏为早期冻结输出中 330/487 的错误；第三栏是一次生成流程的依赖追踪缺口，不宣称已在同一输出中证明所有漏改。第 4—7 页则来自近期完成项目，显示真实方案、七个传播场景、检查结果和最后五轮修复记录。问到出处时，应明确区分两组材料。

英语原句在第 14 页；试验方法、预算差异和关系图缺口在第 15 页。验证结果见 remake/readable_20260917/validation.json；其他系统上的显示效果未实测。
''')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
