"""Project-led main presentation: nine product pages, three case pages."""

def build_main(d, assets, out, page, card, takeaway):
    import json
    from decklib import WHITE, INK, MUTED, RED, GOLD, GREEN, LINE, NAVY
    t, r, a = d.text, d.rect, d.arrow
    evidence_dir = assets.parent/'evidence'
    state = json.loads((evidence_dir/'base_state.json').read_text())
    applied = json.loads((evidence_dir/'option_d_apply.json').read_text())
    graph_edges = [('CM01','E09','motivates'), ('E09','E11','causes'), ('E09','S05','appears_in'), ('E11','S06','appears_in')]
    selected_edges = []
    for source, target, relation in graph_edges:
        edge = next(e for e in state['dependencies'] if (e['source_id'],e['target_id'],e['relation']) == (source,target,relation))
        assert edge['evidence'] and edge['confidence'] > 0
        selected_edges.append(edge)
    propagation = next(x['propagation'] for x in applied['applied'] if x['plan_culture_mechanism_id']=='CM01')
    assert [s['scene_id'] for s in propagation['affected_scenes']] == ['S01','S02','S03','S04','S05','S06']
    import decklib
    (decklib.ROOT/'graph_provenance.json').write_text(json.dumps({
        'source':'rebirth_system_16k/evidence/base_state.json', 'slide':5,
        'nodes':['CM01','E09','E11','S05','S06'], 'edges':selected_edges,
        'propagation_source':'rebirth_system_16k/evidence/option_d_apply.json',
        'returned_affected_scenes':[s['scene_id'] for s in propagation['affected_scenes']],
        'displayed_path':['CM01','E09','E11','S06'],
        'displayed_path_note':'An actual graph route; the propagation output selects its own strongest reason_path per scene.',
        'scene_6_returned_reason_path':next(s['reason_path'] for s in propagation['affected_scenes'] if s['scene_id']=='S06'),
    },ensure_ascii=False,indent=2))

    # 1 — Project positioning.
    d.slide('', '跨文化故事改编智能体', '面向短剧编剧与出海制作团队', dark=True)
    d.pages[-1]['title'] = 'StoryBridge：让短剧换个文化背景，剧情依然接得上'
    t('StoryBridge', .8, 1.02, 11.7, .70, 40, '#E8C78F', True)
    t('换个文化背景，\n剧情依然要接得上。', .8, 2.25, 11.7, 1.65, 42, WHITE, True)
    t('选择改编方案  ·  追踪连带改动  ·  检查并修复', .84, 4.62, 11.6, .60, 26, '#E8C78F', True)
    t('把完整剧本，变成可审、可改、可交接的出海项目。', .84, 5.60, 11.6, .55, 24, '#D3DFE3')
    d.notes(18, '我们做的是 StoryBridge，面向短剧编剧和出海制作团队的跨文化故事改编智能体。核心价值是：选择改编方案，追踪连带改动，检查并修复，让完整剧本的改编过程可审、可改、可交接。')

    # 2 — The user's problem, before any example.
    page('短剧出海，难在换了背景之后怎么办', '项目解决的问题')
    card(.74, 2.08, 3.77, 3.86, '文化理解', '观众能看懂吗？', '考试、家庭、身份，\n换到另一种文化里，\n冲突还成立吗？', GOLD)
    card(4.79, 2.08, 3.77, 3.86, '前后关联', '后文跟着改了吗？', '前面改了一个设定，\n后面的动机、证据、\n结局也可能要变。', RED)
    card(8.84, 2.08, 3.77, 3.86, '成稿审查', '改完怎么核对？', '名字、数字、伏笔，\n分散在不同场景里。\n读着顺，也可能错。', GREEN)
    takeaway('我们的目标：让文化改编有方案，让连带变化有检查。')
    d.notes(22, '短剧出海有三个难点。第一，原来的制度和人物动机，换个文化背景还成立吗？第二，前面一改，后面哪些戏要跟着动？第三，全文看起来很顺，人物、数字和伏笔却可能对不上。StoryBridge 围绕这三个问题设计流程。')

    # 7 — Case page 1/3: everything necessary to follow the evidence.
    page('用这个案例，看 StoryBridge 怎样改编', '案例起点 · 先看懂人物和换分结果', '改编任务：完整十二场短剧 → 美国背景、英语稿；保留分数反转。故事设定为虚构')
    r(.76, 2.04, 5.28, 3.91, WHITE, LINE, True)
    t('规则', 1.01, 2.29, 4.78, .39, 18, RED, True)
    t('沈曼借谁的笔，\n就和笔的原主人交换成绩。', 1.01, 2.92, 4.78, 1.08, 24, INK, True)
    t('女主重生回到考试前，\n用朋友周雨的笔设局。\n沈曼因此换错了人。', 1.01, 4.36, 4.78, 1.40, 23, INK)
    t('人物', 6.46, 2.13, 2.45, .38, 17, MUTED, True)
    t('原本 → 出分后', 9.35, 2.13, 3.15, .38, 17, MUTED, True)
    for y, name, role, score, color in [(2.83, '林知夏', '女主', '669 → 669', GREEN), (3.85, '沈曼', '偷分者', '487 → 330', RED), (4.87, '周雨', '女主的朋友', '330 → 487', GOLD)]:
        r(6.29, y, 6.28, .84, WHITE, LINE, True)
        t(name+' · '+role, 6.46, y+.23, 2.99, .4, 18, color, True)
        t(score, 9.50, y+.20, 2.83, .47, 25, color, True)
    takeaway('要保留的反转：她想偷女主的机会，却因借错笔害了自己。')
    d.notes(30, '接下来沿这个案例看产品怎么工作。沈曼借谁的笔，就和笔的原主人交换成绩。女主重生回到考试前，递给她朋友周雨的笔。结果女主仍是六百六十九，沈曼变成三百三十，周雨变成四百八十七。任务是换成美国背景和英语稿，同时保留这组结果。先看 StoryBridge 怎么理解并处理这个故事。')

    # 4 — Actual structured state and plan selection.
    page('把这个故事拆成 Story State，再选改法', '案例中的方法 1 · 故事状态 = 可追踪的故事档案')
    r(.76, 2.02, 5.35, 3.96, WHITE, LINE, True)
    t('本案例的故事状态（节选）', 1.00, 2.30, 4.87, .47, 23, GREEN, True)
    for y, label, content in [(3.03,'文化设定 · CM01','高考'), (3.97,'事件 E09 / 场景 S05','沈曼借到周雨的笔'), (4.91,'事件 E11 / 场景 S06','周雨查到 487')]:
        t(label, 1.00, y, 4.87, .4, 20, GREEN, True)
        t(content, 1.00, y+.42, 4.87, .40, 21, INK)
    a(6.22, 3.98, 6.77, 3.98, GOLD)
    t('选择“高考”的改编方案', 7.06, 2.22, 5.19, .51, 24, INK, True)
    for y, label, title, body in [(3.05,'A','保留解释','保留设定，补足理解背景'), (4.02,'B','功能替换','换一种设定，保留剧情作用'), (4.99,'C','情节重构','重新设计相关情节')]:
        r(6.97,y,5.59,.80,'#E7F0EC' if label=='C' else WHITE,GREEN if label=='C' else LINE,True)
        t(label,7.15,y+.19,.43,.45,24,GOLD,True)
        t(title,7.77,y+.13,4.50,.38,21,INK,True)
        t(body,7.77,y+.48,4.50,.29,16,MUTED)
    takeaway('本次选 C：高考 → 虚构的学术能力认证体系；接着追踪哪些场景要改。')
    d.notes(24, '系统先把这个故事拆成有编号的档案。高考是 CM01，沈曼借到周雨的笔是事件 E09，周雨查到四百八十七是 E11，各自对应具体场景。再为高考提供三类改法。这次选择重构为虚构的学术能力认证体系。接下来，从高考这个节点追踪影响。')

    # 5 — All four edges below are verified against the frozen actual graph.
    page('Dependency Graph：这次改动会牵动哪几场？', '案例中的方法 2 · 从高考节点追踪借笔与查分', '真实依赖图节选 · CM 为文化设定，E 为事件，S 为场景')
    t('例如：换掉“高考”背景，为什么借笔和查分都需要检查？', .82, 1.95, 11.70, .55, 23, INK, True)
    def node(x,y,w,label,title,color):
        r(x,y,w,1.05,WHITE,color,True)
        t(label,x+.18,y+.14,w-.36,.30,15,color,True)
        t(title,x+.18,y+.51,w-.36,.44,24,INK,True,align='center')
    node(.78,2.97,2.60,'改动起点 · CM01','高考背景',GREEN)
    node(4.47,2.97,3.10,'事件 · E09','再次借笔',GOLD)
    node(9.40,2.97,3.12,'场景 · S05','第 5 场：借笔',GREEN)
    node(4.47,4.93,3.10,'事件 · E11','周雨查到 487',GOLD)
    node(9.40,4.93,3.12,'场景 · S06','第 6 场：查分',GREEN)
    a(3.42,3.51,4.38,3.51,GREEN)
    t('推动',3.45,3.01,.89,.32,17,GREEN,True,align='center')
    for y in [3.51,5.47]:
        a(7.65,y,9.30,y,GREEN)
        t('发生于',7.68,y-.50,1.56,.33,17,GREEN,True,align='center')
    a(6.02,4.10,6.02,4.84,GOLD)
    t('导致分数变化',6.21,4.30,2.92,.34,18,GOLD,True)
    t('每条边记录\n关系类型＋原文依据',.88,4.74,3.34,.88,21,INK)
    takeaway('本次 CM01 实际返回第 1—6 场；每场附影响路径、原文依据和置信度。')
    d.notes(24, '这是真实依赖图的节选。高考设定推动借笔事件，借笔发生在第五场，又导致周雨分数变化，结果出现在第六场。每条边记录关系类型和原文依据。系统沿边追踪，本次从高考节点返回第一到第六场，并给出每场的原因路径。这就把改动范围变成了可检查的数据。')

    # 6 — The graph's output becomes concrete rewrite and review inputs.
    page('找到借笔和查分场景后，带着约束逐场改', '案例中的方法 3 · 改写输入 → 全篇检查 → 按场修复')
    columns=[(.76,'输入改写器','原场景＋改编约束','借笔原文＋新教育背景\n相邻场摘要＋人物资料\n保留换错人的分数反转',GREEN),
             (4.80,'检查改稿','规则＋模型审稿','检查高考旧称谓是否残留\n核对人物、分数与因果\n输出问题与场景编号',GOLD),
             (8.84,'回到问题场景','定点修复，再次检查','按场景编号定位问题\n生成修复计划并改写\n复核结果交给编剧确认',GREEN)]
    for x,label,title,body,color in columns:
        r(x,2.27,3.74,3.60,WHITE,LINE,True)
        t(label,x+.22,2.55,3.30,.34,16,color,True)
        t(title,x+.22,3.18,3.30,.96,24,INK,True)
        t(body,x+.22,4.34,3.30,1.27,19,INK)
    a(4.53,3.95,4.73,3.95,GOLD)
    a(8.57,3.95,8.77,3.95,GOLD)
    takeaway('依赖图负责定位；检查器结合全篇内容，继续核对事实和因果。')
    d.notes(27, '找到场景后，改写器拿到借笔原文、新教育背景、相邻场摘要、人物资料，以及必须保留的换错人反转。改完，代码检查是否还残留高考旧称谓，模型结合全篇核对人物、分数和因果。发现的问题绑定场景编号，继续修复和复核。下面从改编完整性、结果正确性和依赖追踪三个方面，看这套流程的价值。')

    # Compare observed outputs and the defined one-shot workflow separately.
    page('Baseline 的短板：改不全、改错、缺少依赖追踪', '综合对照 · 看核心改编是否真正落实', '核心机制未替换：后续测试反馈；数字错误：本次输出；依赖追踪：流程对照')
    card(.74, 2.08, 3.77, 3.86, '改不全 · 后续测试反馈', '核心系统没改掉', '要求替换换分系统，\n输出仍保留旧机制。\n核心要求没落实。', RED)
    card(4.79, 2.08, 3.77, 3.86, '改错 · 本次实际输出', '人物结果写串了', '沈曼换后应为 330，\n庭审却写成 487。\n台词顺，事实对不上。', RED)
    card(8.84, 2.08, 3.77, 3.86, '漏依赖风险 · 流程短板', '连带改动缺少追踪', '一次生成就结束，\n没有独立的影响清单，\n漏改需要编剧自行排查。', GOLD)
    takeaway('全文写出来了，核心有没有改、后文有没有跟上，仍然要靠人追问。', RED)
    d.notes(24, '把测试观察和流程对照放在一起，Baseline 暴露出三类短板。改不全：后续测试反馈中，要求换掉的核心系统仍然保留。改错：本次成稿把沈曼的结果写成别人的分数。再看流程，它没有独立的依赖追踪和影响清单，连带漏改需要编剧自行排查。全文写出来，不等于改编做完。')

    page('StoryBridge 把三类风险，变成可检查的交付项', '项目优势 · 方案有对象，改动有路径，问题能回修')
    t('编剧关心什么', .98, 2.05, 2.80, .38, 17, MUTED, True)
    t('StoryBridge 提供什么', 3.87, 2.05, 4.06, .38, 17, GREEN, True)
    t('本案例的实际产物', 8.55, 2.05, 3.67, .38, 17, MUTED, True)
    rows=[('核心改了什么？','文化节点＋选定改编方案','高考 → 学术认证\n换分 → 数据模块'),
          ('哪些后文要跟着改？','依赖图＋场景清单＋原因路径','高考节点 → 第 1—6 场\n每场附原文依据'),
          ('发现问题怎么继续？','检查报告＋按场修复记录','本例有 2 轮修复记录\n包含庭审场景')]
    for i,(question,method,result) in enumerate(rows):
        y=2.73+i*1.04
        r(.77,y,11.81,.88,WHITE,LINE,True)
        t(question,.98,y+.24,2.82,.43,20,INK,True)
        t(method,3.87,y+.24,4.43,.43,20,GREEN,True)
        t(result,8.55,y+.13,3.75,.66,18,INK)
    takeaway('Baseline 交出成稿；StoryBridge 还交出改编依据、影响路径和修复记录。')
    d.notes(32, 'StoryBridge 的价值，是把刚才三类风险变成编剧能检查的东西。核心改什么，有文化节点和选定方案，这次就是学术认证和数据换分模块。牵动哪里，有依赖图、场景清单和原文依据。出了问题，有检查报告和按场修复记录，这次包括庭审场景。这些都是实际产物。Baseline 交出成稿以后，方案有没有落实、后文有没有漏改，还得编剧自己追；我们的工作台把这些依据一起交出来。')

    # 3 — Baseline is a defined workflow, not every general-purpose model.
    page('Baseline 写完就交；我们把审稿接进流程', '方法差异 · 本次对照采用同一模型')
    t('Baseline = 同一模型拿完整材料，一次生成全文。', .81, 1.94, 11.7, .55, 23, INK)
    r(.79, 2.76, 11.75, 1.10, '#F6E7E3', None, True)
    t('Baseline', 1.03, 3.08, 2.08, .43, 24, RED, True)
    t('完整输入  →  一次写全文  →  直接交付', 3.33, 3.08, 8.86, .46, 26, INK, True)
    t('没有后续检查，写错的内容也会一起交出去。', 3.35, 4.02, 8.88, .46, 23, RED, True)
    r(.79, 4.95, 11.75, .96, '#E7F0EC', None, True)
    t('StoryBridge', 1.03, 5.23, 2.27, .42, 22, GREEN, True)
    t('故事状态 → 依赖图 → 逐场改写 → 检查修复', 3.33, 5.23, 8.86, .43, 23, GREEN, True)
    takeaway('“生成结束”不能当成“改编完成”。')
    d.notes(25, '回到项目价值。同一个模型，Baseline 拿完整材料一次写完就交，改没改全、哪些场景受影响，没有单独的工作步骤和记录。StoryBridge 把故事状态、依赖图、逐场改写、检查修复接成流程。刚才沿着借笔和查分看到的，就是这条处理链怎样运作，以及最终输出在哪一处做得更好。')

    # 10 — Product demonstration, not another retelling of the plot.
    page('把方法做进工作台：选、查、改都能操作', '18 秒真实产品演示', '操作演示 · 已省略生成等待')
    d.movie(out/'StoryBridge_18秒操作演示.mp4', assets/'system_video_poster.png', .74, 1.90, 8.98, 5.05125)
    for y, n, title, sub in [(2.23, '01', '选方案', '决定怎么改'), (3.79, '02', '看影响', '找到关联场景'), (5.35, '03', '审改稿', '核对前后文字')]:
        t(n, 10.07, y, .58, .42, 22, GOLD, True)
        t(title, 10.73, y, 2.05, .43, 24, GREEN, True)
        t(sub, 10.07, y+.68, 2.71, .43, 19, INK)
    d.notes(30, '这十八秒展示的是实际工作台。看三个动作：选择方案、查看影响、对照改稿。方法已经落成可以操作的产品。【播放十八秒。】编剧能沿着方案和关联场景，找到要核对的具体文字。')

    # 11 — Deliverables are more important than a generic capability slogan.
    page('交给编剧的，是一套能继续工作的改编成果', '项目交付价值')
    card(.74, 2.08, 3.77, 3.86, '可阅读', '目标语言剧本', '按场景组织成稿，\n保留原文与改稿对照，\n方便逐场审阅。')
    card(4.79, 2.08, 3.77, 3.86, '可解释', '改编依据', '选了哪种方案，\n影响了哪些场景，\n都能回头查。')
    card(8.84, 2.08, 3.77, 3.86, '可继续', '检查与修改记录', '问题落到具体场景，\n保留版本和修改记录，\n方便继续审稿、修稿。')
    takeaway('一次生成交出一份文本；StoryBridge 提供继续审、继续改的工作台。')
    d.notes(28, '最终交给编剧的有三部分。第一，按场景组织的目标语言稿和改前改后对照。第二，改编方案与影响范围，能解释为什么这么改。第三，检查结果、版本和修改记录，方便继续审稿和修稿。从选方案到交接成果，StoryBridge 提供的是完整工作台。')

    # 12 — Return to the project, not a final line from the example.
    d.slide('', '主讲结束', '跨文化故事改编智能体', dark=True)
    d.pages[-1]['title'] = 'StoryBridge：让改编有依据，让剧情接得上'
    t('StoryBridge', .78, 1.19, 11.78, .68, 36, '#E8C78F', True, align='center')
    t('让改编有依据，\n让剧情接得上。', .78, 2.62, 11.78, 1.57, 40, WHITE, True, align='center')
    t('选方案  →  追踪影响  →  检查修复', .78, 4.73, 11.78, .57, 27, '#D3DFE3', align='center')
    t('谢谢大家', .78, 5.89, 11.78, .56, 28, '#E8C78F', True, align='center')
    d.notes(16, 'StoryBridge 把文化改编、影响追踪和检查修复接成一个产品。核心改法有对象，连带场景有路径，后续修稿有依据。让改编有依据，让剧情接得上。谢谢大家。')
