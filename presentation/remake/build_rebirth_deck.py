"""Build the 10+2 evidence-led rebirth demo deck from frozen real outputs."""
from pathlib import Path
import json, re, shutil
from decklib import Deck,NAVY,CREAM,WHITE,INK,MUTED,RED,GOLD,GREEN,LINE

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent
REPO=ROOT.parents[1]
CASE=ROOT/'rebirth_system_16k';E=CASE/'evidence';A=CASE/'assets'
d=Deck(main_slide_count=10);t=d.text;r=d.rect;a=d.arrow

plans=json.loads((E/'plans.json').read_text())
apply=json.loads((E/'option_d_apply.json').read_text())
target=json.loads((E/'option_d_target.json').read_text())
baseline=(E/'baseline_first_response.md').read_text()
calls=[json.loads(line) for line in (E/'calls.jsonl').read_text().splitlines()]

def option(mid,label):
    p=next(x for x in plans if x['culture_mechanism_id']==mid)
    return next(x for x in p['options'] if x['option_label']==label)

def page(title,chapter,source='',dark=False,appendix=False):
    d.slide('',chapter,source,dark,appendix);d.pages[-1]['title']=title
    t(title,.68,.93,12,.96,32,WHITE if dark else INK,True)

def card(x,y,w,h,tag,title,body,accent=GREEN):
    r(x,y,w,h,WHITE,LINE,True);t(tag,x+.22,y+.20,w-.44,.32,13,accent,True)
    t(title,x+.22,y+.76,w-.44,.72,22,INK,True);t(body,x+.22,y+1.64,w-.44,h-1.82,17,INK)

# 1
d.slide('','短剧出海 · 剧本本地化','本页为目标用户与任务定义；案例与比较见后页',dark=True);d.pages[-1]['title']='StoryBridge：换设定时，别让后面的戏断掉'
t('StoryBridge',.72,1.02,8.7,.82,42,'#E8C78F',True)
t('把一次文化改编，\n变成一条可检查的因果链。',.72,2.12,8.8,1.55,38,WHITE,True)
t('给短剧出海编剧：选改法、看牵连、逐场审稿',.76,4.35,8.8,.48,23,'#E8C78F',True)
r(9.82,1.20,2.80,5.18,'#203E4E',None,True)
t('真实任务',10.08,1.55,2.30,.34,15,'#E8C78F',True)
t('高考',10.08,2.25,2.25,.48,28,WHITE,True);t('＋',10.08,2.92,2.25,.46,23,'#AFC3C9',True)
t('易分系统',10.08,3.45,2.28,.50,27,WHITE,True)
t('一起改成\n美国观众能懂的\n教育数据黑箱',10.08,4.40,2.25,1.35,19,'#D3DFE3')
d.notes(32,'大家好，我们做的是 StoryBridge，一个给短剧出海编剧用的改编助手。这次不讲抽象能力，直接看一部十二场重生短剧。任务不只是把高考换个名字，还要把背后的换分系统、日志、庭审证据和结尾一起换到新的文化背景。StoryBridge 的作用是把改法、影响范围和逐场结果摊开，让编剧能够审。')

# 2
page('她把朋友的笔，递给了偷分的人。','原故事 · 十二场重生悬疑','虚构短剧《她换走了我的高考》；“易分系统”为虚构设定')
t('前世，沈曼借笔偷走林知夏的 669；重生后，林知夏递出了周雨的笔。',.74,1.96,11.85,.64,23,INK,True)
for x,name,before,after,color in [(.76,'林知夏','669','669',GREEN),(4.52,'沈曼','487','330',RED),(8.28,'周雨','330','487',GOLD)]:
    r(x,2.92,3.50,2.36,WHITE,LINE,True);t(name,x+.22,3.16,3.04,.38,22,color,True)
    t(before,x+.22,3.90,1.05,.54,28,INK,True,align='center');a(x+1.35,4.12,x+2.05,4.12,color);t(after,x+2.15,3.90,1.05,.54,28,color,True,align='center')
t('“你明明只有 330！”',.78,5.72,5.34,.58,30,RED,True)
t('“成绩刚出，你怎么知道我原来的分数？”',6.13,5.78,6.15,.48,23,INK,True)
t('关键：林知夏保住自己；沈曼换错对象；周雨暂时得到 487。',.78,6.47,11.5,.40,19,GREEN,True)
d.notes(34,'原故事的钩子很简单。前世，沈曼借走林知夏的笔，通过易分系统把自己的四百八十七换成六百六十九。重生后，林知夏把周雨落下的笔递给她。结果林知夏仍是六百六十九，沈曼从四百八十七掉到三百三，周雨从三百三变成四百八十七。沈曼抢过手机脱口而出：你明明只有三百三。她也因此暴露了自己事先知道分数。')

# 3
page('这次要换的，不只是考试名称。','改编任务 · 教育体系＋换分系统','项目真实方案摘录；最终采用两个 C 方案的组合，不采用“录取资格交换”支线')
card(.72,2.03,3.72,3.90,'原稿机制','高考＋易分系统','一次统考决定录取；\n借笔识别两个人；\n后台留下交换日志。',RED)
card(4.80,2.03,3.72,3.90,'StoryBridge · C','APC 学术能力认证','虚构教育数据联盟\n汇总考试与项目记录，\n生成 Academic Proficiency Index。',GREEN)
card(8.88,2.03,3.72,3.90,'StoryBridge · C','EduSwap 黑箱模块','植入教育数据后台；\n笔杆生物识别条绑定身份；\n离线日志记录错误目标。',GOLD)
t('保留剧情功能：借笔触发 · 换错周雨 · 330/487 反转 · 日志取证 · 系统仍在',.78,6.35,11.6,.46,20,INK,True)
d.notes(32,'制作方的要求是美国背景、英语成稿，而且系统也要换。StoryBridge 分别给教育机制和统分系统提出方案。我们最后采用 C 的组合：教育背景变成虚构的 APC 学术能力认证体系；易分系统变成植入教育数据联盟后台的 EduSwap 黑箱模块。借笔仍是锚点，但动作被解释成笔杆生物识别条绑定身份。前程卡、仪式和百日用笔都没有加入。')

# 4
page('Baseline 也拿到完整材料。','公平对照 · 同模型一次全文改编','模型均为 deepseek-v4-flash；流程调用预算不同，不是等计算量实验')
r(.74,2.00,11.86,.73,'#E9F0EC',None,True);t('共同输入：完整十二场原稿＋全部约束＋同一 APC / EduSwap 组合方案',.97,2.22,11.36,.36,19,GREEN,True)
for x,label,title,body,color in [(.75,'StoryBridge','多阶段、可查看','解析 → 3 个机制方案 → 批量改写 → 两轮检查修复 → 英语全文',GREEN),(6.90,'普通 AI Baseline','生成即交付','一次直接改全文；没有依赖追踪、跨场校验或定点回修',RED)]:
    r(x,3.10,5.70,2.95,WHITE,LINE,True);t(label,x+.25,3.35,5.18,.34,15,color,True);t(title,x+.25,4.00,5.18,.48,25,INK,True);t(body,x+.25,4.82,5.14,.82,18,INK)
t('长篇改编里，“写完了”远远不等于“接对了”。',.80,6.42,11.6,.42,22,RED,True,align='center')
d.notes(28,'对照要公平。Baseline 拿到完整十二场原稿、全部约束和同一个 APC、EduSwap 组合方案，使用同一个模型，一次直接写完。首份响应完整返回，就原样冻结。StoryBridge 是多阶段流程，调用预算显著更高，所以这不是等算力比赛。我们只比较这一次真实稿件怎么处理关键因果。')

# 5
page('这一次，StoryBridge 把 S10 的数字接对了。','真实改稿对照 · 法庭场景','最终英语稿原句；中文为忠实摘译，完整出处见隐藏第 11 页')
for x,name,color in [(.74,'StoryBridge · S10',GREEN),(6.91,'普通 AI 直出稿 · S10',RED)]:
    r(x,2.01,5.69,4.42,WHITE,LINE,True);t(name,x+.25,2.28,5.17,.40,22,color,True)
t('“You saw 330.\nYour first reaction was\nto call Lin Zhixia … Why?”',1.00,3.12,5.10,1.72,25,INK,True)
t('沈曼新分数是 330。',1.00,5.35,5.10,.40,20,GREEN,True)
t('“When you saw your score\nwas 487, why did you call\nLydia Chen …?”',7.17,3.12,5.10,1.72,25,INK,True)
t('核心证据链断裂：把周雨的 487 写给了沈曼。',7.17,5.28,5.10,.68,18,RED,True)
t('两边都完整覆盖 S01–S12；本页只说明本次关键数字衔接，不代表总体胜率。',.80,6.61,11.7,.34,17,MUTED,align='center')
d.notes(36,'看一个最关键的真实差别。StoryBridge 在第十场法庭上写：你看到三百三以后，第一反应为什么是打给林知夏？这与第六场沈曼的新分数一致。Baseline 却写成：你看到四百八十七以后为什么打给 Lydia？四百八十七其实是周雨换后的分数。两边都写完了十二场；这里只说明本次 StoryBridge 把后续证据接对了，不推导通用胜率。')

# 6
page('从换设定，到法庭证据，改动接上了。','核心亮点 · Dependency graph＋验证闭环','本轮真实流程：初始传播定位前段，验证阶段继续修复 S09–S11')
steps=[(.76,'01  选定机制','APC＋EduSwap','教育体系与黑箱模块\n同时替换',NAVY),(4.70,'02  图谱传播','S01 → S06','借笔、出分、重生、\n换错对象与数字反转',GOLD),(8.64,'03  验证闭环','S09 → S11','日志、法庭 330、\n清算与恢复卷面分',GREEN)]
for x,tag,title,body,color in steps:
    r(x,2.18,3.54,3.18,WHITE,LINE,True);t(tag,x+.24,2.46,3.05,.30,14,color,True);t(title,x+.24,3.17,3.05,.54,28,INK,True);t(body,x+.24,4.04,3.05,.90,18,INK)
a(4.30,3.78,4.64,3.78,GOLD);a(8.24,3.78,8.58,3.78,GREEN)
r(.78,5.83,11.77,.68,'#E7F0EC',None,True)
t('最终检查：669 不变  ·  330 / 487 对调  ·  S10 追问 330  ·  EduSwap 贯穿结尾',1.00,6.03,11.30,.31,18,GREEN,True,align='center')
d.notes(36,'这就是 StoryBridge 的核心价值。先选 APC 和 EduSwap 两个机制，再由 dependency graph 定位第一到第六场的连带变化；之后验证环继续检查日志、法庭和清算，把第九到第十一场补齐。最终林知夏六百六十九不变，三百三与四百八十七对调，第十场法庭也准确追问三百三。不是改完一个名词就结束，而是把后续证据一起接上。')

# 7
page('改完之后，系统真的换了。','完整故事 · APC＋EduSwap','StoryBridge 最终英语稿的中文梗概；完整十二场原文在素材包')
card(.72,2.02,3.74,3.96,'S01–S05','借笔绑定错误身份','APC 认证考试前，\n沈曼借到周雨的笔。\n笔杆生物识别条把\n周雨标成了目标。')
card(4.80,2.02,3.74,3.96,'S06–S07','330 与 487 对调','林知夏仍是 669；\n周雨从 330 变 487；\n沈曼从 487 变 330，\n并当场说漏嘴。',RED)
card(8.88,2.02,3.74,3.96,'S08–S12','EduSwap 留下日志','Old Song 保存离线日志；\n法庭追问 330；\n周雨恢复卷面分，\n黑箱模块来源仍不明。',GREEN)
t('换掉的是文化与技术外壳；留下的是“偷别人命运，反而暴露自己”的反转。',.80,6.38,11.70,.45,21,INK,True,align='center')
d.notes(34,'改完后的故事可以这样讲。APC 认证考试前，沈曼借到的其实是周雨的笔，笔杆的生物识别条把周雨标成目标。出分后林知夏仍是六百六十九，周雨从三百三变成四百八十七，沈曼从四百八十七掉到三百三。EduSwap 的离线日志记录了 borrower、lent-from 和 wrong target。法庭用三百三追问沈曼，最后周雨恢复卷面分，而黑箱模块的来源仍然没有查清。')

# 8
d.slide('','18 秒真实产品操作 · 选系统 → 看影响 → 审数字','真实 React 界面读取本次冻结结果；模型等待已省略；视频无音轨');d.pages[-1]['title']='18 秒看一次真实审稿过程'
d.movie(OUT/'StoryBridge_18秒操作演示.mp4',A/'system_video_poster.png',1.09,.67,11.15,6.271875)
d.notes(36,'下面看十八秒真实操作。请留意四步：先看 EduSwap 方案，再看影响路径，然后核对第六场的三组分数，最后检查第十场法庭是否同步成三百三。【点击视频，播放十八秒。】这里读取的是本次真实模型结果，省略了生成等待，没有改动模型文字。')

# 9
page('AI 会写错一个数字；产品价值就在这里。','真实局限 · 也是 StoryBridge 的机会','本轮真实结果：完整输入 baseline 在 S10 将沈曼的 330 写成了周雨的 487')
card(.76,2.05,3.55,3.72,'普通 AI 直出','场次齐，不代表剧情对','十二场看似完整，\n核心庭审证据却断了：\n330 写成 487。',RED)
card(4.89,2.05,3.55,3.72,'长文本模型','上下文有硬上限','请求设为 16384，\n服务端仍在 8192 截断；\n需要按场景分块。',GOLD)
card(9.02,2.05,3.55,3.72,'StoryBridge','把风险变成检查项','图谱定位牵连，\n验证继续追后文，\n编剧最后确认。',GREEN)
t('我们不卖“一键完美”；我们让长篇改编里的漏改，变得看得见、追得上、改得回。',.82,6.29,11.66,.52,21,GREEN,True,align='center')
d.notes(22,'局限并不是产品没接上，而是通用大模型确实会在长文本里写错一个关键数字。这次 baseline 把沈曼的三百三写成了周雨的四百八十七；同时服务端仍有八千 token 的输出上限。StoryBridge 的价值，就是把这些风险变成可查看的路径和检查项，再让编剧做最后确认。')

# 10
d.slide('','主讲结束','后续为 2 页隐藏备答 · 欢迎交流',dark=True);d.pages[-1]['title']='谢谢大家'
t('StoryBridge',.70,1.36,11.93,.60,31,'#E8C78F',True,align='center');t('谢谢大家',.70,2.50,11.93,1.20,67,WHITE,True,align='center')
r(6.23,4.20,.88,.045,GOLD);t('让改编的每一次牵动，都有迹可循。',.70,4.72,11.93,.56,29,'#E8C78F',True,align='center')
t('“你明明只有 330。”',.70,5.85,11.93,.46,23,'#D3DFE3',align='center')
d.notes(10,'这次 StoryBridge 把一次文化设定替换，接成了从借笔、出分到日志、庭审和结尾的完整因果链。对编剧来说，能看见为什么改、改动牵到哪里，并把关键数字一路核对到底，才是真正可用的创作工具。StoryBridge，让改编的每一次牵动，都有迹可循。谢谢大家。')

# 11 hidden
page('备答：第十场英语原句与完整判断。','完整对照摘录','模型原文逐字摘录；StoryBridge：option_d_target.json；baseline：baseline_first_response.md',appendix=True)
r(.74,2.02,5.70,3.85,WHITE,LINE,True);r(6.90,2.02,5.70,3.85,WHITE,LINE,True)
t('StoryBridge',.98,2.28,5.18,.40,23,GREEN,True);t('“You saw 330. Your first reaction was to call Lin Zhixia — not to file a data audit with the Alliance. Why?”',.98,3.08,5.17,1.82,23,INK)
t('S06：沈曼页面为 330。',.98,5.22,5.15,.34,18,GREEN,True)
t('完整输入 Baseline',7.15,2.28,5.18,.40,23,RED,True);t('“When you saw your score was 487, why did you call Lydia Chen instead of filing an audit request?”',7.15,3.08,5.17,1.82,23,INK)
t('S06：487 属于周雨。',7.15,5.22,5.15,.34,18,RED,True)
t('编辑判断：法庭问题应引用沈曼自己看到的 330。Baseline 改了人物英文名，不影响该数字错误的判定。',.82,6.21,11.68,.64,18,INK)
d.notes(0,'隐藏备答。两段均来自首次冻结的完整英语稿。StoryBridge 的第十场与第六场一致；baseline 在第十场误用了周雨换后的四百八十七。这个判断只依赖同稿时间线，不依赖主观文风偏好。')

# 12 hidden
page('视频备用：法庭场景已经同步为 330。','静态备用页 · 真实产品截图','视频播放失败时跳到本页；截图来自实际 StoryBridge UI',appendix=True)
d.picture(A/'system_s10.png',.72,1.91,11.88,4.68);t('The Trial：You saw 330.  ·  S06：Shen Man posts 330.',.82,6.65,11.68,.28,18,GREEN,True,align='center')
d.notes(0,'视频无法播放时，输入 12 回车跳到本页，说明法庭场景引用了沈曼的新分数三百三；讲完输入 10 回车回到谢谢大家。PDF 第八页是视频封面，也可单独打开 MP4。')

assert sum(x['seconds'] for x in d.talks)==300
deck=OUT/'StoryBridge_智理杯_5分钟展示.pptx';d.save(deck);shutil.copyfile(deck,ROOT/'presentation.pptx')

md=['# StoryBridge · 5 分钟讲稿','','10 页主讲，2 页隐藏备答。第 8 页含 18 秒视频；建议总时长 300 秒，包含视频。',''];elapsed=0
for i,talk in enumerate(d.talks,1):
    md += [f'## {i}. {talk["title"]}','']
    end=elapsed+talk['seconds']
    md += [('隐藏备答，不计入主讲时间。' if talk['appendix'] else f'{elapsed//60}:{elapsed%60:02d}–{end//60}:{end%60:02d}'),' ',talk['text'],'']
    elapsed=end
(OUT/'StoryBridge_5分钟讲稿.md').write_text('\n'.join(md),encoding='utf-8')

outline=['# StoryBridge · 展示提纲','','10 页主讲 + 2 页隐藏备答。','']+[f'{i}. {p["title"]}'+('（隐藏备答）' if p['appendix'] else '') for i,p in enumerate(d.pages,1)]
(OUT/'StoryBridge_展示提纲.md').write_text('\n'.join(outline)+'\n',encoding='utf-8')

stats={}
for group in sorted({row['group'] for row in calls}):
    rows=[row for row in calls if row['group']==group]
    stats[group]={'calls':len(rows),'prompt_tokens':sum(row['response'].get('prompt_tokens') or 0 for row in rows),'completion_tokens':sum(row['response'].get('completion_tokens') or 0 for row in rows),'seconds':round(sum(row['seconds'] for row in rows),1)}
provenance={'storybridge_quote':{'file':'evidence/option_d_target.json','scene':'S10','text':'You saw 330. Your first reaction was to call Lin Zhixia — not to file a data audit with the Alliance. Why?'},'baseline_quote':{'file':'evidence/baseline_first_response.md','scene':'S10','text':'When you saw your score was 487, why did you call Lydia Chen instead of filing an audit request?'},'graph':{'file':'evidence/option_d_apply.json','actual_initial_propagation':{'CM01':['S01','S02','S03','S04','S05','S06'],'CM10':[]},'slide_annotation':'Dashed S10 gap is explicitly human review, not an automatic edge.'},'call_stats':stats}
(E/'quote_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')

report='''# 本次展示的实验说明

## 输入与选择

完整十二场原稿、用户确认的 669/487/330 关系、美国市场、英语输出和全部剧情约束同时提供给 StoryBridge 与 baseline。StoryBridge 先真实生成教育体系、换分机制和统分系统各自的 A/B/C 方案。全 B 出现 ScholarTrack、ScoreSync、NAAP 混用；全 C 把分数交换改成录取资格交换，破坏原反转。最终采用项目实际提出的 CM01-C（APC）与 CM10-C（EduSwap），不采用 CM02-C。

## 真实结果

StoryBridge 与 baseline 都完整覆盖 S01–S12。StoryBridge 在 S10 正确引用沈曼的新分数 330；baseline 在 S10 写成 487，误用了周雨换后的分数。StoryBridge 内部检查最终仍为 fail：两条是对“换笔/借周雨的笔”的明显语义误报；一条指出 S04 的“推”与 S08 的“扑”没有逐字回收，属于真实但很小的动作措辞风险。模型输出未人工修改。

## 图谱边界

初始传播中 CM01 覆盖 S01–S06，CM10 返回 No downstream scenes。后续验证/修复才处理 S09–S11。PPT 第 6 页把 S10 画成虚线人工复核缺口，不冒充系统自动依赖边。

## 模型与预算

模型为 deepseek-v4-flash。StoryBridge 是多阶段调用，baseline 为一次全文调用，不是等计算预算。运行时 max_tokens 已设为 16384，但服务端整篇解析连续返回 finish_reason=length、completion_tokens=8192；正式解析使用项目已有的场景边界分块。第一次 baseline 验证器未识别粗体 Markdown 标题，响应本身以 stop 结束且完整含 S01–S12，因此只修正本地验证记录，没有补跑模型。

## 结论边界

单个虚构案例，没有盲评、重复采样或统计胜率。可以说明本次 StoryBridge 提供了方案、路径和逐场审查，并在 S10 数字衔接上优于本次 baseline；不能推导普通 AI 总体更差，也不能声称全自动通过。
'''
(CASE/'实验说明.md').write_text(report,encoding='utf-8')

story=['# 完整故事与改稿','','## 中文 demo 原稿','',(REPO/'backend/data/scripts/corpus_rebirth.md').read_text(encoding='utf-8'),'','## StoryBridge 最终英语稿（原样）','']
for s in target['scenes']: story += [f'### {s["id"]} {s["title"]}','',s['text'],'']
story += ['## Baseline 首份完整响应（原样）','',baseline]
(CASE/'完整故事与改稿.md').write_text('\n'.join(story),encoding='utf-8')
print(deck)
