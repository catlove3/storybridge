"""Audience-first product pitch. Model outputs are quoted, never rewritten as evidence."""
from pathlib import Path
import shutil,json
from decklib import Deck,NAVY,CREAM,WHITE,INK,MUTED,RED,GOLD,GREEN,LINE

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'StoryBridge_智理杯_5分钟展示.pptx'
MARKET_URL='https://sensortower.com/blog/state-of-short-drama-apps-2026-report'
d=Deck(main_slide_count=8);t=d.text;r=d.rect;a=d.arrow

def page(title,chapter,source='',dark=False,appendix=False):
 d.slide('',chapter,source,dark,appendix)
 d.pages[-1]['title']=title
 t(title,.68,.93,12,.96,33,WHITE if dark else INK,True)

def card(x,y,w,h,tag,title,body,accent=GREEN):
 r(x,y,w,h,WHITE,LINE,True)
 t(tag,x+.23,y+.22,w-.46,.35,13,accent,True)
 t(title,x+.23,y+.85,w-.46,.85,24,INK,True)
 t(body,x+.23,y+1.87,w-.46,h-2.03,19,INK)

# 1 — Say who this is for and what it does before introducing the fictional story.
d.slide('','短剧出海 · 剧本本地化','数据：Sensor Tower《State of Short Drama Apps 2026》，2026 年 6 月',dark=True)
d.pages[-1]['title']='StoryBridge：给短剧出海编剧的改编助手'
t('StoryBridge',.72,1.00,8.8,.80,44,'#E8C78F',True)
t('让故事换个文化，\n依然讲得通。',.72,2.24,8.8,1.75,40,WHITE,True)
t('给短剧出海编剧的改编助手',.77,4.51,8.7,.5,24,'#E8C78F',True)
t('输入中文原稿与目标市场，\n得到海外改稿，以及相关场景的修改对照。',.77,5.34,8.7,1.09,23,'#D3DFE3')
r(10.02,1.36,2.60,4.98,'#203E4E',None,True)
t('为什么现在做',10.24,1.64,2.16,.38,15,'#E8C78F',True)
t('7.5 亿',10.24,2.47,2.17,.64,31,WHITE,True)
t('美元 / 约',10.24,3.13,2.16,.38,16,'#D3DFE3')
t('2026 年第一季度\n全球短剧 App\n内购收入',10.24,3.81,2.16,1.10,17,WHITE)
t('本地翻拍，\n需要故事也能\n融入目标文化。',10.24,5.06,2.16,1.0,16,'#D3DFE3')
d.current.shapes[2].click_action.hyperlink.address=MARKET_URL
d.notes(35,'大家好，我们做的是 StoryBridge，一个给短剧出海编剧用的改编助手。海外市场已经有人愿意为短剧付费：Sensor Tower 估算，今年第一季度，全球短剧 App 内购收入约七点五亿美元。我们聚焦一个具体任务：制作方拿来一部中文短剧，要把它拍成美国故事。编剧换掉一个文化设定，人物的经历、手里的证据、最后的反转，可能全都要跟着改。StoryBridge 帮他把这些牵连找出来，再逐场审改。')

# 2 — A complete, simple original story, with named people and an ending.
page('她的名字，别人的成绩。','原稿 · 中国家庭短剧','以下案例《不是我的成绩》为虚构；人物、学校、赛事与俱乐部均为虚构')
t('小宁想学画画。父亲只认名校。小岚是帮她查清真相的朋友。',.74,2.03,11.9,.52,23,INK)
card(.71,2.92,3.84,3.56,'起因 · 第 1–2 场','她没考试，却有了高分','小宁摔伤住院，错过高考。\n父亲向中介交钱。\n成绩单上出现了她的名字。')
card(4.75,2.92,3.84,3.56,'反转 · 第 3–5 场','照片里的人不是她','小岚带来考场座位表。\n对照照片和住院记录，\n父女确认有人替考。',RED)
card(8.79,2.92,3.84,3.56,'结尾 · 第 6–7 场','用自己的画重新申请','父女主动说明真相，\n放弃假成绩。\n父亲终于认真看她的画。')
d.notes(40,'先用半分钟把原故事讲清楚。女孩小宁喜欢画画，父亲却觉得只有名校才有未来。小宁受伤住院，错过高考。中介说，人不用到，成绩能安排，父亲以为有特殊补考机会，就交了钱。后来她真的收到高分，可照片里的人是谁？朋友小岚带来考场座位表，与照片和住院记录一对，父女才确认有人替考。最后，他们放弃假成绩，主动说明真相。小宁用自己的画重新申请，父亲也终于愿意看她的作品。')

# 3 — Make the adaptation assignment explicit, including the reason behind the changes.
page('现在，制作方要把它拍成美国故事。','改编任务 · 中文原稿 → 美国背景','本案例的创作选择；不把虚构骗局当作真实招生制度说明')
t('把骗局改成：伪造赛艇运动员履历，企图获得名校体育招募机会。',.74,2.01,11.9,.83,25,INK,True)
t('小宁从未练过赛艇——中介却把她包装成了船队队员。',.75,2.93,11.9,.46,21,RED,True)
for x,txt,color in [(.89,'需要跟着换的',MUTED),(4.30,'中国版原稿',INK),(8.44,'美国版改稿',GREEN)]:
 t(txt,x,3.78,3.80,.37,15,color,True)
rows=[('父亲买的“机会”','高考分数','体育招募资格'),('中介给的假材料','成绩单、考场照片','赛艇履历、船队合影'),('朋友拿来的真证据','考场座位表','队员名单、座位安排')]
for i,(label,before,after) in enumerate(rows):
 y=4.42+i*.63;r(.74,y,11.87,.53,WHITE)
 t(label,.9,y+.10,3.08,.37,18,MUTED)
 t(before,4.30,y+.10,3.48,.37,19,INK)
 a(7.71,y+.28,8.11,y+.28)
 t(after,8.44,y+.10,3.96,.37,19,GREEN,True)
t('要留下的：父亲的名校执念，和女儿“我要靠自己”的反抗。',.77,6.49,11.83,.39,20,INK,True)
d.notes(35,'制作方提出的新要求是：把高考替考，换成伪造赛艇运动员履历。赛艇就是多人同船划桨的运动。小宁从没练过，却被中介包装成运动员，想借体育招募进入名校。这样，父亲花钱买未来、女儿要靠自己的冲突还能留下。但成绩单要换成赛艇材料，朋友为什么有证据、拿什么揭穿，也得一起改。观众要能顺着线索看懂这个新骗局。这就是一个设定牵动整条剧情的地方。')

# 4 — The first actual naive baseline, full source and shared creative brief.
page('第二场就说破了，第五场还揭穿什么？','实测对照 · 直接交给 AI 全文改编','最终英语稿的中文摘译 · 同一模型；两者都改对赛艇线索，本页讨论这次输出的悬念节奏')
r(.73,1.99,11.87,.75,'#E9F0EC',None,True)
t('Baseline：完整原稿 + 全部改编要求 + 同一方案，一次性交给 AI 改完整篇。',.96,2.21,11.42,.40,19,GREEN,True)
for x,name,subtitle,color in [(.74,'朴素全文改编','第 2 场 · 女儿已经直接说出',RED),(6.91,'StoryBridge','第 2 场 · 女儿先提出疑点',GREEN)]:
 r(x,3.09,5.69,3.71,WHITE,LINE,True)
 t(name,x+.25,3.32,5.16,.49,25,color,True)
 t(subtitle,x+.25,4.03,5.16,.37,16,MUTED)
t('“别人的身体，\n贴上我的脸？”',1.0,4.66,5.13,1.04,29,RED,True)
t('“可那两天\n我一直在医院。”',7.17,4.66,5.13,1.04,29,GREEN,True)
t('换脸手法已经点破。',1.0,6.08,5.13,.43,21,RED)
t('到第 5 场，再拿原始名单揭穿。',7.17,6.08,5.13,.43,20,GREEN)
d.notes(45,'最直接的办法，当然是把所有东西都给 AI。我们确实这样跑了一次：完整七场原稿、全部美国改编要求，连同一个赛艇方案，都交给同一个模型，让它直接写完。它也改对了队员名单，但出现了一个值得编剧注意的问题。左边是第二场，女儿已经说：别人的身体，贴上我的脸？换脸已经明说，第五场再拿证据揭穿，惊讶就少了一层。右边是 StoryBridge 同次案例的结果：第二场只说，我那两天在医院。先留疑点，朋友再给线索，最后拿原件确认。这里展示的是这次实际稿件的差别，不是说普通 AI 一定写不好。两边引文都是最终英语稿的中文摘译。')

# 5 — A branched dependency graph, with every edge checked against the saved state.
page('Dependency graph：改一处，牵动哪些戏？','核心亮点 · 依赖图','左：实际节点与关系重排，标签节缩；右：真实产品界面局部。金色表示本次影响关系。')
for x,w,label in [(.76,1.83,'设定与人物'),(3.12,2.60,'剧情事件'),(6.90,2.38,'受影响的场景'),(9.76,2.86,'真实产品界面')]:
 t(label,x,2.00,w,.32,14,MUTED,True)
graph_nodes={
 'CM01':dict(x=.76,y=2.77,w=1.74,h=.84,label='高考',kind='focus'),
 'C02':dict(x=.76,y=4.18,w=1.74,h=.74,label='父亲',kind='context'),
 'C01':dict(x=.76,y=5.37,w=1.74,h=.74,label='小宁',kind='context'),
 'E02':dict(x=3.12,y=2.43,w=2.61,h=.64,label='住院，错过考试',kind='event'),
 'E03':dict(x=3.12,y=3.22,w=2.61,h=.64,label='父亲向中介交钱',kind='event'),
 'E04':dict(x=3.12,y=4.01,w=2.61,h=.64,label='收到假成绩单',kind='event'),
 'E05':dict(x=3.12,y=4.80,w=2.61,h=.64,label='女儿质疑并留证',kind='event'),
 'E06':dict(x=3.12,y=5.59,w=2.61,h=.64,label='朋友留下座位表',kind='event'),
 'S01':dict(x=6.90,y=2.62,w=2.38,h=.90,label='第一场\n她没去的考试',kind='scene'),
 'S02':dict(x=6.90,y=4.03,w=2.38,h=.90,label='第二场\n不属于她的成绩',kind='scene'),
 'S03':dict(x=6.90,y=5.42,w=2.38,h=.97,label='第三场\n朋友留下的线索',kind='destination'),
}
state=json.loads((ROOT/'evidence/state_v1.json').read_text())
deps={(e['source_id'],e['target_id']):e for e in state['dependencies']}
path=['CM01','E02','E03','E04','E05','E06','S03']
path_edges=list(zip(path,path[1:]))
branches=[('E02','S01'),('E03','S01'),('E04','S02'),('E05','S02')]
context_edges=[('C02','S01'),('C02','S02'),('C01','S01'),('C01','S02'),('C01','S03')]
for src,dst in context_edges+branches+path_edges:
 assert (src,dst) in deps,(src,dst)
 left,right=graph_nodes[src],graph_nodes[dst]
 if src.startswith('E') and dst.startswith('E'):
  a(left['x']+left['w']/2,left['y']+left['h'],right['x']+right['w']/2,right['y'],GOLD)
 else:
  a(left['x']+left['w'],left['y']+left['h']/2,right['x'],right['y']+right['h']/2,'#D4D8D4' if (src,dst) in context_edges else GOLD)
for node_id,n in graph_nodes.items():
 x,y,w,h=n['x'],n['y'],n['w'],n['h'];kind=n['kind']
 fill=RED if kind=='focus' else GREEN if kind=='destination' else '#FBF0D7' if kind in ('event','scene') else WHITE
 stroke=RED if kind=='focus' else GREEN if kind=='destination' else GOLD if kind in ('event','scene') else LINE
 r(x,y,w,h,fill,stroke,True)
 text_color=WHITE if kind in ('focus','destination') else INK
 t(node_id,x+.12,y+.05,w-.24,.18,9,'#F6DFD4' if kind=='focus' else '#D9ECE4' if kind=='destination' else MUTED,True)
 t(n['label'],x+.12,y+.26,w-.24,h-.27,17 if kind in ('scene','destination') else 18,text_color,True)
d.picture(ROOT/'assets/graph_screen.png',9.75,2.46,2.87,1.62)
t('真实截图（局部）',9.79,4.18,2.80,.30,12,MUTED)
r(9.80,4.75,.14,.14,RED);t('改动起点',10.06,4.67,2.51,.35,15,INK)
r(9.80,5.24,.14,.14,GOLD);t('受影响的关系',10.06,5.16,2.51,.35,15,INK)
r(9.80,5.73,.14,.14,GREEN);t('定位到的第三场',10.06,5.65,2.51,.35,15,GREEN,True)
t('第三场没有写“高考”，却连在这条影响路径上。',.79,6.59,11.80,.39,22,GREEN,True)
(ROOT/'evidence/slide_graph.json').write_text(json.dumps({'scope':'Actual induced dependency subgraph for the first three scenes, relaid out for slide readability. Text labels are shortened. Not a screenshot.','nodes':graph_nodes,'highlighted_path':path,'edges':[deps[e] for e in context_edges+branches+path_edges],'ui_screenshot':'assets/graph_screen.png'},ensure_ascii=False,indent=2))
d.notes(40,'这就是 dependency graph，依赖图。红色是我们选中的高考；中间是与它相关的剧情事件；右边是这些事件所在的场景。沿着金色关系往下看：错过考试，父亲找中介，收到假成绩单，女儿质疑并留证，接着朋友带来了座位表。这条线最后连到了第三场。第三场虽然没有高考这个词，朋友为什么有材料、拿什么当证据，都受这个设定影响。灰色线保留人物与场景的关系。左图依据项目真实关系放大重排，右上角是实际产品界面。编剧能据此找修改范围，再逐场检查伏笔与揭穿是否接得上。')

# 6 — The audience should be able to retell the adapted story.
page('改完之后，观众能跟着线索看懂反转。','改写结果 · 美国版故事','StoryBridge 真实中文结构稿的节选压缩；完整中文稿与最终英语稿均在交付包')
card(.72,2.13,3.84,3.87,'第 2 场 · 起疑','没划过船，却有记录','中介发来参赛确认函\n和模糊的船队合影。\n\n“可那两天\n我一直在医院。”')
card(4.76,2.13,3.84,3.87,'第 3 场 · 线索','朋友认出了那个座位','小岚帮俱乐部整理过材料，\n留有真实队员名单。\n\n“我记得这个位置\n坐的不是你。”')
card(8.80,2.13,3.84,3.87,'第 5 场 · 揭穿','照片换脸，名单没她','原始名单对上船队照片，\n再核对住院时间。\n\n父女终于确认：\n这是一段伪造的履历。',RED)
t('“你给我买的未来，连里面的人都不是我。”',.78,6.36,11.85,.52,27,RED,True)
d.notes(35,'于是，美国版的故事可以这样接起来。第二场，没练过赛艇的小宁收到参赛确认函和模糊合影，她只觉得不对。第三场，帮俱乐部整理过材料的朋友，认出了照片里的座位，答应带来原件。第五场，真实名单上没有小宁，参赛日期又对上住院时间，换脸造假的手法才被完整揭开。她对父亲说，你给我买的未来，连里面的人都不是我。骗局的道具和揭穿方式换了，这句话里的委屈和反抗，还能落在观众心里。')

# 7 — Keep the real recording legible, with a visible page number outside the movie.
d.slide('','18 秒真实产品操作 · 选改法 → 看牵连 → 审改稿','实际产品读取本次真实生成结果；模型生成等待已省略。视频无音轨。')
d.pages[-1]['title']='18 秒看一次实际改编操作'
d.movie(ROOT.parent/'StoryBridge_18秒操作演示.mp4',ROOT/'assets/video_poster.png',1.09,.67,11.15,6.271875)
d.notes(45,'下面看十八秒实际操作。请留意三个动作：选赛艇方案，看第三场为什么受影响，再对照它改前改后的文字。【点击视频。播放期间只提示：选改法——看牵连——审改稿。18 秒后继续。】刚才朋友的经历、手里的名单都一起改了，结尾仍然是女儿靠自己的画申请。这是现有产品读取本次真实结果的操作回放，省略了模型生成等待。编剧可以打开具体场景，决定这次改得对不对。')

# 8 — A dedicated, unmistakable thank-you slide; Q&A follows it.
d.slide('','主讲结束','后续为隐藏备答页 · 欢迎交流',dark=True)
d.pages[-1]['title']='谢谢大家'
t('StoryBridge',.70,1.33,11.93,.65,32,'#E8C78F',True,align='center')
t('谢谢大家',.70,2.51,11.93,1.32,68,WHITE,True,align='center')
r(6.24,4.28,.85,.045,GOLD)
t('让故事换个文化，依然讲得通。',.70,4.83,11.93,.67,30,'#E8C78F',True,align='center')
t('“这一次，上面的名字和作品，都是我的。”',.70,5.95,11.93,.49,22,'#D3DFE3',align='center')
d.notes(25,'故事的最后，小宁放弃假履历，用自己的画申请艺术课程。她说，这一次，名字和作品，都是我的。父亲终于认真看完了她的画册。我们希望帮编剧留下的，就是这样的时刻：文化设定换了，人物的选择仍然打动人。StoryBridge，让故事换个文化，依然讲得通。谢谢大家。')

# 9 — Protocol: no restricted-scene strawman; no model-quality win manufactured.
page('备答：我们确实把所有改编信息交给了 AI。','Baseline 口径','首次完整响应原样保存；原始请求、模型响应和调用用量均可核对',appendix=True)
for y,label,body in [(2.06,'同一输入','完整七场原稿、美国目标市场、英语输出要求、剧情保留要求、同一赛艇方案。'),(3.16,'朴素改编','系统提示“你是一名编剧”；一次生成完整英语剧本，允许附改编说明。'),(4.26,'同一模型','deepseek-v4-flash；StoryBridge 使用多阶段流程，两者调用预算不同。'),(5.36,'本次观察','两者都更新了赛艇线索；朴素稿提前点破换脸。项目另提供依赖路径与逐场差异。')]:
 t(label,.82,y,2.01,.5,23,GREEN,True);t(body,3.11,y,9.37,.82,21,INK)
t('单个虚构案例，无盲评或统计胜率；不能据此断言普通 AI 一定更差。',.82,6.57,11.6,.36,18,MUTED)
d.notes(0,'使用 run_naive_baseline.py 运行，naive_protocol.json 在调用前写入，首次完整返回即采纳。没有限制它只能改含关键词的场景，没有禁止解释，也没有为了得到差稿反复抽样。此前局部关键词对照已退出展示；此前强提示词全文对照也正确更新了朋友与证据。我们主张可查看的改编流程，不宣称依赖图已经被本实验证明能稳定提高成稿质量。')

# 10 — Exact originals for the interpretation on slide 4.
page('备答：第二场的英语原句。','引文与判断依据','naive_full.md / S02 与 storybridge.json / S02；中文仅为忠实摘译',appendix=True)
r(.74,2.00,5.69,3.90,WHITE,LINE,True);r(6.91,2.00,5.69,3.90,WHITE,LINE,True)
t('朴素全文改编',.99,2.23,5.18,.46,24,RED,True)
t('“Sees what? A photo of someone else’s body with my face on it?”',.99,3.17,5.16,1.51,25,INK)
t('第 2 场已经明确说出拼脸。',.99,5.13,5.16,.43,20,RED)
t('StoryBridge',7.16,2.23,5.18,.46,24,GREEN,True)
t('“But I was in the hospital those two days.”',7.16,3.17,5.16,1.51,25,INK)
t('“a blurry crew photo”',7.16,4.51,5.16,.55,22,MUTED)
t('第 5 场才明确写出换脸手法。',7.16,5.13,5.16,.43,20,GREEN)
t('我们的判断：提前交代手法，会削弱后续“拿原件揭穿”的新信息量。\n这是对本次稿件的编辑判断；并未证明所有读者都更偏好右侧。',.82,6.11,11.73,.78,18,INK)
d.notes(0,'朴素稿的第 2 场还把身体、姿态、光线不匹配写进舞台动作，第 3 场的队员名单与第 5 场原件均已出现，不能说它漏改了朋友或证据。第 4 页中文为节译：保留“别人的身体”和“我的脸”，省略疑问的引导词。StoryBridge 最终英语稿的 S02 是模糊船队照片与住院疑点，明确 Photoshopping 出现在 S05。这是关于悬念次序的编辑观察，不是自动指标。')

# 11 — Real graph, limits of the actual run, and what remains to validate.
page('备答：图能解释改动，成稿仍要由人审。','真实图谱与当前边界','本次运行最终内部检查状态为 fail；没有宣称全自动通过',appendix=True)
d.picture(ROOT/'assets/s03_impact.png',.77,2.06,6.73,3.12)
t('图里查到什么',8.01,2.14,4.46,.49,23,GREEN,True)
t('第三场的真实影响路径\n与原文依据。\n\n初次传播覆盖 S01–S03，\n后续复核又修了后段场景。',8.01,2.95,4.46,2.20,20,INK)
t('现在还缺什么',.83,5.79,3.0,.49,23,RED,True)
t('全稿人工审阅、更多类型剧本的盲评。\n检查报告与旧结构描述有冲突，不能当作质量全部过关。',4.01,5.79,8.36,.96,20,INK)
d.notes(0,'CM01 → E02 → E03 → E04 → E05 → E06 → S03 为实际保存路径。图并没有单独证明悬念一定会更好，因此主讲把它定位成编剧能逐场检查的依据。最终检查返回 fail，部分问题来自旧结构描述与新正文不一致，仍有人工审稿任务，不能将 fail 一概当作无须处理的误报。首次仅选择末场替考机制的窄范围运行另存归档，未作本次主案例。')

# 12 — Static fallback, reachable directly if the local video player fails.
page('视频备用：朋友的经历和证据，一起更新。','真实产品截图 · 可脱网展示','视频播放失败时直接跳到第 12 页；按第 7 页要点讲解',appendix=True)
d.picture(ROOT/'assets/s03_diff.png',.72,1.94,11.89,4.49)
t('考场座位表  →  真实队员名单。朋友能拿到证据的经历，也跟着改了。',.80,6.59,11.73,.38,20,GREEN,True)
d.notes(0,'截图来自实际项目的 S03 前后对照。放映状态按 12 回车可直接跳到本页；然后按 8 回车回到谢谢大家。PDF 的第 7 页是视频封面，播放备用独立 MP4 或直接讲本页静态截图。')

assert sum(x['seconds'] for x in d.talks)==300
d.save(OUT);shutil.copyfile(OUT,ROOT/'presentation.pptx')
md=['# StoryBridge · 5 分钟讲稿','','8 页主讲，4 页隐藏备答。第 7 页含 18 秒实录，主讲时间含视频共 300 秒；这是排练建议，不是已测定的现场语速。','']
elapsed=0
for i,talk in enumerate(d.talks,1):
 md += [f'## {i}. {talk["title"]}','']
 end=elapsed+talk['seconds']
 if not talk['appendix']:md += [f'{elapsed//60}:{elapsed%60:02d}–{end//60}:{end%60:02d}','']
 md += [talk['text'],''];elapsed=end
md += ['## 主讲提词卡','','谁用 → 原故事 → 制作方要改什么 → 整篇给 AI 的真实结果 → 依赖图 → 改后故事 → 18 秒操作 → 谢谢大家。','','第 4 页不能再说“AI 漏改了考场座位表”；真实全文 baseline 已更新赛艇线索。第 4 页讨论的是它在第二场提前点破换脸。','','一人主讲，其他人协助翻页、设备与答辩。用提词卡排练，展示时对着 PPT 讲；技术细节留到隐藏备答。']
(ROOT.parent/'StoryBridge_5分钟讲稿.md').write_text('\n'.join(md))
outline=['# StoryBridge · 展示提纲','','主线：短剧出海编剧收到美国翻拍任务；更换文化设定会牵动后面的证据与反转。产品亮点是可查看的依赖图与逐场改稿。','']
for i,p in enumerate(d.pages,1):
 outline += [f'{i}. {p["title"]}'+('（谢谢大家后的隐藏备答）' if p['appendix'] else '')]
(ROOT.parent/'StoryBridge_展示提纲.md').write_text('\n'.join(outline)+'\n')
print(OUT)
