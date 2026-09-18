"""Build a plain-language presentation using the user's 12-scene bribery story."""
from pathlib import Path
import hashlib
import json
import shutil
import decklib
from decklib import Deck, NAVY, WHITE, INK, MUTED, RED, GOLD, GREEN, LINE

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
CASE = ROOT / 'clear_story_20260917'
CASE.mkdir(exist_ok=True)
decklib.ROOT = CASE
d = Deck(main_slide_count=12)
t, r, a = d.text, d.rect, d.arrow

def page(title, chapter, source='依据用户提供的十二场剧本整理；故事与机构均为虚构', appendix=False):
    d.slide(title, chapter, source, appendix=appendix)

def box(x, y, w, h, label, title, body, color=GREEN):
    r(x,y,w,h,WHITE,LINE,True)
    t(label,x+.22,y+.18,w-.44,.32,13,color,True)
    t(title,x+.22,y+.75,w-.44,.86,24,INK,True)
    t(body,x+.22,y+1.78,w-.44,h-1.88,20,INK)

def banner(text, y=6.28, color=GREEN):
    r(.72,y,11.90,.57,'#E7F0EC',None,True)
    t(text,.91,y+.11,11.52,.38,18,color,True,align='center')

# 1: State the product's job in ordinary language.
d.slide('','给短剧编剧的改编助手','用《她换走了我的高考》说明：先读懂故事，再改给海外观众看',dark=True)
d.pages[-1]['title']='StoryBridge：换了故事背景，后面的剧情也要说得通'
t('StoryBridge',.75,1.02,11.80,.72,40,'#E8C78F',True)
t('换了故事背景，\n后面的剧情也要说得通。',.75,2.16,11.8,1.65,40,WHITE,True)
t('例如：把“高考被换分”改成“奖学金被冒领”，\n女主怎样发现、怎样举报、怎样夺回机会，都要跟着改。',.79,4.38,11.70,1.10,24,'#D3DFE3')
t('先用两分钟看懂原故事，再看产品怎么帮忙。',.79,6.08,11.7,.45,21,'#E8C78F',True)
d.notes(18,'StoryBridge 是给短剧编剧用的改编助手。用一句话说，它帮助编剧在换故事背景时，把后面的情节一起改通。今天先讲清这部剧发生了什么，再用一个具体例子说明产品怎么帮忙。')

# 2: Introduce characters before events and scores.
page('先认识人物：一个被偷走成绩的女孩，和害她的父女','原故事 · 谁和谁有冲突')
box(.72,2.05,3.80,3.77,'女主角','林知夏','成绩优秀，高考考了 669 分。\n成绩被偷后，她要找证据，\n夺回自己的上学机会。',GREEN)
box(4.78,2.05,3.80,3.77,'同学 / 偷分者','沈曼','自己考了 487 分。\n靠父亲把成绩换成 669，\n还想让林知夏永远闭嘴。',RED)
box(8.84,2.05,3.80,3.77,'沈曼的父亲','沈董','花 300 万买通内部人员，\n调换两人的成绩，\n又用钱和威胁阻止追查。',RED)
t('帮助女主的人：周雨陪同、报警；老陈老师申请复核；技术员老宋提供日志。',.80,6.20,11.75,.70,20,INK)
d.notes(23,'先记住三个人。林知夏是女主，真实成绩六百六十九。沈曼是她的同学，真实成绩四百八十七。沈曼的父亲花三百万，买通内部人员调换成绩。朋友周雨、班主任老陈和技术员老宋，则分别在陪同报警、申请复核和提供证据上帮助女主。')

# 3: Explain the first life with explicit score labels.
page('第一次人生：669 分被偷走，她还被推下天台','原故事 · 第 1—3 场：受害')
t('沈董买通统分人员，把两个人的成绩对调。',.78,1.98,11.65,.52,25,INK,True)
for y,name,before,after,color in [(2.82,'林知夏','真实成绩 669','公布成绩 487',GREEN),(3.89,'沈曼','真实成绩 487','公布成绩 669',RED)]:
    r(.78,y,11.75,.82,WHITE,LINE,True)
    t(name,1.00,y+.20,1.70,.45,24,color,True)
    t(before,3.00,y+.20,3.0,.45,24,INK,True)
    a(6.18,y+.40,7.38,y+.40,color)
    t(after,8.00,y+.20,3.8,.45,24,color,True)
t('她申请复核，却收到“成绩无误”。\n沈曼在天台亲口承认换分；她转身要举报，被沈曼推了下去。',.85,5.12,11.60,.98,23,INK)
banner('她失去的不只是分数，还有证明真相的机会。',color=RED)
d.notes(27,'第一次人生里，林知夏查到四百八十七，沈曼却拿着她的六百六十九成了榜首。老师申请复核，结果仍是成绩无误。沈曼后来在天台亲口说出父亲买通人员换分的事实。林知夏想去举报，却被推下天台，外界还以为她是自杀。')

# 4: Define rebirth instead of assuming genre knowledge.
page('重生以后：她回到高考前，决定把犯罪过程录下来','原故事 · 第 4—7 场：准备反击')
t('“重生”＝她死后回到了高考第一天，仍然记得上一次发生的事。',.80,1.97,11.70,.65,22,INK,True)
box(.74,2.92,3.77,2.99,'第一步','正常考试，公开估分','她当众说出估分 669，\n让老师和同学知道\n487 分有多反常。')
box(4.79,2.92,3.77,2.99,'第二步','再次复核，留下记录','换分果然再次发生。\n她保留申诉和驳回记录，\n继续寻找直接证据。')
box(8.84,2.92,3.77,2.99,'第三步','拒绝收买，安排保护','沈董拿 200 万让她闭嘴。\n她拒绝，并让周雨\n随时知道自己在哪里。')
banner('这一次，她的目标是：活下来，让证据留下来。')
d.notes(27,'重生的意思是，她死后回到了高考第一天，而且记得上一次发生的事。这一次，她仍然正常考试，公开估分，再次申请复核并留下记录。沈董拿两百万收买她，她拒绝了。她还让周雨知道自己的行踪，为再次面对沈曼做准备。')

# 5: Distinguish evidence of violence from evidence of score tampering.
page('她怎样证明真相？天台录像＋成绩修改日志','原故事 · 第 8—9 场：取得证据')
box(.74,2.10,5.75,3.92,'证据一 · 天台','录下承认换分和袭击','林知夏带运动相机、录音笔赴约。\n沈曼亲口说出买通人员和压下复核，\n随后威胁、动手。\n周雨事先报警，警察到场。',GREEN)
box(6.82,2.10,5.75,3.92,'证据二 · 统分系统','查到成绩被改的记录','被沈家开除的技术员老宋交出备份。\n日志写明：6 月 24 日凌晨 2:17，\n两名考生的成绩字段被人工对调。\n操作账号关联沈家的技术外包公司。',GOLD)
banner('录像记录当晚发生了什么；日志为追查换分提供具体线索。')
d.notes(31,'这次天台见面，她带着相机和录音笔，周雨事先报警。沈曼承认换分和干预复核，并在当晚再次威胁、动手。女主躲开了，警方到场。随后技术员老宋交出备份，记录了成绩何时被改、用了哪个账号。两种证据各有作用：一个记录天台事件，一个帮助追查成绩被改的过程。')

# 6: Close the plot before switching to the product.
page('结局：换分被查实，她拿回 669 分和录取机会','原故事 · 第 10—12 场：真相公开')
box(.74,2.06,3.77,3.65,'调查','警方和教育部门介入','天台录像引发关注。\n警方调查袭击与换分，\n教育部门重新核查成绩。')
box(4.79,2.06,3.77,3.65,'清算','沈家承担后果','原稿写道：沈曼被捕，\n父亲被采取强制措施，\n沈氏集团最终破产。',RED)
box(8.84,2.06,3.77,3.65,'新生活','录取通知书寄到家','官方确认她的真实成绩：\n669 分。\n她终于拿回求学机会。')
t('“这一次，每一分都是我自己挣的。”',.85,6.05,11.60,.65,29,GREEN,True,align='center')
d.notes(22,'后面的结局就容易理解了。警方和教育部门介入，确认成绩被调换。原稿中，沈曼被捕，父亲被采取强制措施，沈家也付出代价。林知夏恢复六百六十九分，收到了录取通知书。这部剧的主线就是：女孩被偷走未来，重来一次后靠证据夺回来。')

# 7: A single clearly labeled editorial example, not a fabricated experiment.
page('改给海外观众看：先选一个容易理解的争夺对象','产品怎么帮忙 · 以“奖学金评审”作示例','以下为人工讲解示例，尚未在本版原稿上运行模型；不代表真实实验输出')
box(.76,2.12,5.68,3.89,'原故事','争的是高考成绩','林知夏考了 669 分，\n却被公布为 487 分。\n她的分数被同学偷走，\n大学录取机会也受到影响。',GREEN)
box(6.91,2.12,5.68,3.89,'一种可选改法','争的是全额奖学金','改为某所虚构大学的奖学金评审。\n女主本来入选，却被同学冒名顶替。\n对家境困难的她来说，\n失去资助就可能无法入学。',GOLD)
a(6.49,4.10,6.85,4.10,GOLD)
banner('要保留的冲突很明确：她靠努力挣来的上学机会，被有钱同学偷走了。')
d.notes(28,'现在再讲改编。我们举一个人工讲解的例子：如果制作方选择海外背景，可以把争夺对象改成一所虚构大学的全额奖学金。女主本来入选，却被冒名顶替；没有资助，她就可能无法入学。观众仍然能理解她失去了什么、为什么要反抗。这只是待编剧选择的示例，没有冒充模型生成结果。')

# 8: Concrete, readable before/after lines in Chinese.
page('看一场就明白：查分页面，要改成什么？','具体怎么改 · 第 2 场前后对照','人工讲解示例；为方便阅读使用中文，正式目标语言稿需另行生成')
box(.76,2.07,5.68,3.90,'原稿 · 第 2 场','查分发现异常','她反复刷新查分页面：487。\n“我估了六百六十九，怎么会这样？”\n老师替她申请成绩复核。\n沈曼却凭 669 分登上榜首。',GREEN)
box(6.91,2.07,5.68,3.90,'示例改法 · 同一场','查看名单发现资格被偷','她反复刷新奖学金名单：没有自己。\n“入选确认信上明明是我的名字。”\n老师替她申请核查评审结果。\n官网公布的获奖者却是沈曼。',GOLD)
banner('失去的东西改了，发现异常的方式、申诉理由和对手获利的方式也要改。')
d.notes(28,'看第二场就明白了。原稿是女主刷新查分页面，发现只有四百八十七，老师申请成绩复核。示例里则是女主在奖学金名单上找不到自己，但手里有入选确认信，老师因此申请核查评审结果。沈曼占据的也从榜首变成了奖学金名额。这些具体动作都要跟着改。')

# 9: Replace abstract graph vocabulary with what needs changing and why.
page('前面换了“奖学金”，后面这四处也要一起改','为什么需要工具 · 避免改到后面又写回高考','人工整理的剧情关联示例；不是系统自动识别结果或已完成的改稿')
rows=[
 ('第 2、6 场','查分与复核','查看获奖名单，申请核查评审结果'),
 ('第 7、8 场','收买与天台自白','承认买通评审管理人员，替换获奖姓名'),
 ('第 9 场','老宋提供统分日志','提供奖学金名册的修改记录'),
 ('第 11、12 场','恢复分数，收到录取通知','撤销冒领名额，恢复资助并确认入学'),
]
t('原来写什么',3.05,2.01,3.15,.35,15,MUTED,True)
t('选了新设定后，要改成什么',7.27,2.01,5.0,.35,15,MUTED,True)
for i,(scene,old,new) in enumerate(rows):
    y=2.64+i*.78
    r(.78,y,11.77,.63,WHITE,LINE,True)
    t(scene,.97,y+.13,1.86,.38,17,GREEN,True)
    t(old,3.05,y+.13,3.78,.38,18,INK)
    a(6.58,y+.32,7.02,y+.32,GOLD)
    t(new,7.27,y+.13,5.0,.38,17,INK,True)
banner('工具的作用：把这些需要一起修改的场景找出来，交给编剧逐场确认。')
d.notes(27,'如果只改第二场，后面就会出问题。第七、八场的收买和自白，要对应奖学金；第九场老宋交出的，就不能仍然是统分日志；结尾也要恢复资助。这就是页面上这些箭头的含义：前面的设定改了，哪些后文必须一起改，编剧需要看得见。')

# 10: Product workflow without a mismatched prerecorded demo.
page('编剧使用 StoryBridge，只需要按这三步看','产品怎么用 · 输入故事 → 选择改法 → 检查结果','依据现有产品工作流整理；本页为操作说明，非本案例的运行截图')
box(.74,2.10,3.77,3.77,'01 · 输入','放入完整剧本','粘贴这 12 场故事，\n选择面向哪里、用什么语言。\n注明必须保留的情节，\n例如：重生、天台反击。')
box(4.79,2.10,3.77,3.77,'02 · 选择','决定采用哪种改法','看系统给出的改编建议。\n例如保留高考并解释，\n或换成奖学金争夺。\n由编剧选择合适的方案。')
box(8.84,2.10,3.77,3.77,'03 · 检查','逐场看改前和改后','查看哪些场景受到影响，\n对照原文和改稿，\n处理检查发现的问题，\n再生成目标语言剧本。')
banner('交到编剧手里的，是改稿、修改理由，以及需要继续检查的地方。')
d.notes(24,'产品使用过程分三步。第一，输入完整剧本、目标市场和语言，说明必须保留的情节。第二，查看建议并选一种改法。第三，看受影响的场景，对照修改前后的文字，处理检查发现的问题，再生成目标语言稿。编剧能够看到改了什么，以及为什么需要改。')

# 11: Review questions tied to this specific story, without legal assertions.
page('改稿完成后，仍然要回答这三个具体问题','怎样判断有没有改通 · 人工审稿')
checks=[
 ('人物动机','女主失去什么？为什么非追回来不可？','从“分数”换成“奖学金”后，要把无法入学的处境讲清。'),
 ('证据来源','是谁改了记录？老宋为什么能拿到备份？','前面出现的人员和机构，要与后面的自白、日志对应。'),
 ('结局衔接','最后恢复的，还是前面被偷走的东西吗？','若争的是资助，结尾就要恢复资助，并交代能否入学。'),
]
for i,(tag,question,detail) in enumerate(checks):
    y=2.00+i*1.32
    r(.76,y,11.82,1.10,WHITE,LINE,True)
    t(tag,.98,y+.22,1.80,.42,20,GREEN,True)
    t(question,3.02,y+.14,9.25,.42,23,INK,True)
    t(detail,3.02,y+.65,9.25,.32,17,MUTED)
t('原稿中“一周内查清并破产”等情节，也需要编剧在成稿时重新审视。',.83,6.21,11.68,.52,19,MUTED)
d.notes(27,'怎么判断改通了？问三个问题。女主为什么一定要追回机会？后面用到的证据，从哪里来？结尾恢复的，还是前面被偷走的东西吗？工具可以辅助检查，但编剧仍要审阅。原稿中一周内查清并走到破产等较快的情节，在正式成稿时也需要再推敲。')

# 12: A plain-language close.
d.slide('','主讲结束','后附 3 页十二场剧情速查；主讲备注建议用时共 5 分钟',dark=True)
d.pages[-1]['title']='谢谢大家：帮编剧把整部故事一起改通'
t('StoryBridge',.75,1.27,11.83,.67,34,'#E8C78F',True,align='center')
t('帮编剧把整部故事一起改通。',.75,2.67,11.83,.80,36,WHITE,True,align='center')
t('知道改了哪里，也知道后面还有哪里要改。',.75,4.15,11.83,.56,26,'#D3DFE3',align='center')
t('谢谢大家',.75,5.54,11.83,.74,35,'#E8C78F',True,align='center')
d.notes(18,'这就是 StoryBridge 想帮编剧做的事。读懂原故事，选择适合目标观众的改法，把后面受影响的场景一起检查清楚，让整部故事仍然说得通。谢谢大家。')

# Appendix: all 12 original scenes, readable without the speech.
summaries=[
 ('01','前世 · 估分','林知夏考完觉得很稳，估分至少 660；沈曼凑过来看她的准考证。'),
 ('02','前世 · 出分','林知夏只查到 487，复核仍称成绩无误；沈曼却以 669 成为榜首。'),
 ('03','前世 · 天台','沈曼承认父亲花 300 万买通人员换分；林知夏要举报，被推下天台。'),
 ('04','重生 · 回到考前','林知夏回到高考第一天，记得前世，决定这次保留证据、躲开袭击。'),
 ('05','重生 · 再次考试','她正常考试，公开估分 669，拒借准考证，并让周雨掌握自己的行踪。'),
 ('06','重演 · 再次出分','她再次被公布为 487，沈曼仍是 669；她留下复核申请和驳回记录。'),
 ('07','收买与威胁','沈董拿 200 万要求她闭嘴；她拒绝后，母亲失业，沈曼再次约她上天台。'),
 ('08','天台 · 录下袭击','她带相机和录音笔，周雨提前报警；沈曼自白并动手，她躲开，警方到场。'),
 ('09','深夜 · 技术员来访','老宋交出日志备份，记录两人成绩被人工对调的时间和操作账号。'),
 ('10','曝光与立案','天台视频引发关注；警方调查沈家父女，教育部门进驻复查。'),
 ('11','清算','官方确认女主真实成绩 669；原稿写沈曼被捕、父亲受查、沈氏破产。'),
 ('12','尾声','录取通知书寄到家，老师和朋友陪在身边；林知夏把准考证留在书桌下。'),
]
for j in range(3):
    page(f'十二场速查：第 {j*4+1}—{j*4+4} 场','备答 · 按原稿顺序复述',appendix=True)
    for i,(n,title,body) in enumerate(summaries[j*4:j*4+4]):
        y=2.00+i*1.13
        r(.77,y,11.80,.95,WHITE,LINE,True)
        t(n,1.00,y+.22,.70,.48,25,GREEN,True)
        t(title,1.98,y+.14,9.95,.36,20,INK,True)
        t(body,1.98,y+.57,9.95,.31,16,INK)
    d.notes(0,'备答速查：按用户提供的原始剧本逐场概述，不添加借笔换分、超自然换分系统或新的分数关系。')

assert sum(x['seconds'] for x in d.talks)==300
deck=OUT/'StoryBridge_智理杯_5分钟展示.pptx'
d.save(deck)
shutil.copy2(deck,ROOT/'presentation.pptx')
shutil.copy2(deck,OUT/'StoryBridge_通俗易懂版.pptx')
rows=[]
for i,(p,talk) in enumerate(zip(d.pages,d.talks),1):
    rows.append({'page':i,'title':p['title'],'hidden':p['appendix'],'seconds':talk['seconds']})
manifest={'pptx_sha256':hashlib.sha256(deck.read_bytes()).hexdigest(),'main_slides':12,'total_slides':15,'thanks_slide':12,'video_slide':None,'hidden_slides':[13,14,15],'speaker_notes_seconds':300,'slides':rows,'source':'User-provided 12-scene bribery/score-tampering story','adaptation_example':'Human-written scholarship example, not a model run'}
(CASE/'deck_order.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
md=['# StoryBridge · 5 分钟讲稿','','本版以用户提供的“买通人员换分”十二场剧本为准。12 页主讲＋3 页隐藏备答；总计 300 秒。','']
elapsed=0
for i,talk in enumerate(d.talks,1):
    end=elapsed+talk['seconds']
    md += [f'## {i}. {talk["title"]}','','隐藏备答。' if talk['appendix'] else f'{elapsed//60}:{elapsed%60:02d}–{end//60}:{end%60:02d}','',talk['text'],'']
    elapsed=end
(OUT/'StoryBridge_5分钟讲稿.md').write_text('\n'.join(md))
(OUT/'StoryBridge_展示提纲.md').write_text('# 当前展示提纲\n\n'+ '\n'.join(f'{x["page"]}. {x["title"]}'+('（隐藏备答）' if x['hidden'] else '') for x in rows)+'\n')
(OUT/'README.md').write_text('''# StoryBridge 通俗易懂版

打开 `StoryBridge_智理杯_5分钟展示.pptx` 或 `StoryBridge_通俗易懂版.pptx`，两份内容一致。

12 页主讲、3 页隐藏备答，备注和讲稿共 5 分钟。先介绍人物、分数和两次人生，再用奖学金示例解释产品。

以用户最新提供的“沈董买通统分人员”原稿为准。旧稿中的借笔、330 分、EduSwap 和对应视频不适用于本版，已从展示中移除。第 7—9 页为明确标注的人工讲解示例，没有在该原稿上重新运行模型，不作为实验比较结果。

修改前的 PPT 和配套文件保存在 `remake/clear_story_20260917/before/`。重建命令：`python3.12 presentation/remake/build_clear_deck.py`。重建后需重新导出 PDF 和交付包；不使用历史导航同步脚本覆盖本稿。
''')
(OUT/'StoryBridge_现场使用说明.md').write_text('''# 现场使用说明

主文件：StoryBridge_智理杯_5分钟展示.pptx。12 页主讲，13—15 页为隐藏剧情速查。第 12 页结束。

主讲备注合计 300 秒。PDF 含全部 15 页，不包含视频。本版不播放旧版 18 秒操作视频，因为其借笔换分剧情与当前原稿不符。

第 1—6 页让没读过剧本的人看懂故事；第 7—9 页用人工编写的奖学金示例解释如何改；第 10—11 页介绍操作与人工检查；第 12 页结束。请将示例介绍为“可以这样改”，不要说成系统已经生成或通过了本轮测试。

改版不修改原始模型输出与历史实验记录。最新排版验证见 remake/clear_story_20260917/validation.json。
''')
(CASE/'剧情速查.md').write_text('# 《她换走了我的高考》剧情速查\n\n依据用户本次十二场原稿整理。\n\n'+'\n\n'.join(f'## 第 {n} 场 · {title}\n\n{body}' for n,title,body in summaries)+'\n')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
