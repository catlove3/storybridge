"""Project-led main presentation: nine product pages, three case pages."""

def build_main(d, assets, out, page, card, takeaway):
    import json
    from pathlib import Path
    from decklib import WHITE, INK, MUTED, RED, GOLD, GREEN, LINE, NAVY
    t, r, a = d.text, d.rect, d.arrow
    method_assets = Path(__file__).resolve().parent/'assets'
    method_evidence_path = Path(__file__).resolve().parent/'evidence/method_evidence.json'
    method_evidence = json.loads(method_evidence_path.read_text())
    assert method_evidence['selected_option']['option_label'] == 'B'
    assert [s['scene_id'] for s in method_evidence['propagation']['affected_scenes']] == ['S01','S02','S04','S05','S06','S07','S08']
    assert method_evidence['verification']['scenes_checked'] == method_evidence['verification']['scenes_total'] == 12
    assert method_evidence['verification']['commitments_verified'] == method_evidence['verification']['commitments_total'] == 7
    for filename in ['story_state.png','evidence_culture_plan.png','evidence_dependency_paths.png','evidence_verification_repairs.png']:
        assert (method_assets/filename).is_file(), filename
    import decklib
    (decklib.ROOT/'graph_provenance.json').write_text(json.dumps({
        'source':'evidence/method_evidence.json', 'slide':6,
        'changed_node_id':method_evidence['propagation']['changed_node_id'],
        'returned_affected_scenes':[s['scene_id'] for s in method_evidence['propagation']['affected_scenes']],
        'reason_paths':{s['scene_id']:s['reason_path'] for s in method_evidence['propagation']['affected_scenes']},
        'evidence':{s['scene_id']:s['evidence'] for s in method_evidence['propagation']['affected_scenes']},
        'displayed_image':'assets/evidence_dependency_paths.png',
        'displayed_image_note':'A presentation layout of the saved propagation result; explicitly labelled as non-visitor UI.',
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

    def evidence_page(title, chapter, filename, seconds, notes):
        # Keep searchable slide metadata underneath the full-bleed evidence image.
        page(title, chapter, '真实保存结果 · 内部证据排版，非访客 UI')
        d.picture(method_assets/filename, 0, 0, 13.333333, 7.5)
        d.notes(seconds, notes)

    # 4–7 — Four real evidence images replace the earlier abstract diagrams.
    evidence_page(
        'Story State：系统怎样理解完整故事',
        '案例中的方法 1 · 结构化故事状态',
        'story_state.png', 18,
        '模型没有直接把一篇全文丢给改写器。系统先保存结构化 Story State。图中是真实结果的节选：人物、核心规则、关键场景链、文化机制和叙事承诺都有稳定 ID；完整状态还保存一百二十三条依赖关系。后续每一步都引用这些对象。'
    )
    evidence_page(
        '文化节点：先明确改什么、为什么改',
        '案例中的方法 2 · 文化节点与改编方案',
        'evidence_culture_plan.png', 19,
        '这里把高考识别为高摩擦、高重要度的 CM01，并保留原文词、关联场景和叙事功能。右边是真实生成的 A、B、C 三种方案；本次选择 B，把高考替换为 SAT、ACT 与美国大学申请体系，同时记录为什么选、需要保留哪些剧情功能。'
    )
    evidence_page(
        'Dependency Graph：哪些场景必须跟着改',
        '案例中的方法 3 · 依赖传播与原因路径',
        'evidence_dependency_paths.png', 20,
        '选择方案后，代码从 CM01 沿依赖边传播。本次真实返回七个场景：第一、第二、第四到第八场。左边保存每条路径，右边列出场景、影响类型和原文依据。它不仅说需要改，还能回答为什么这个场景被列入。'
    )
    evidence_page(
        '检查报告：问题落到场景，修复留下记录',
        '案例中的方法 4 · 全篇检查与按场修复',
        'evidence_verification_repairs.png', 18,
        '改写后再检查全篇。这份最新报告检查十二个场景和七项叙事承诺，没有阻塞错误，保留一项需要人工确认的旧依赖边。右边是最后五轮真实修复记录：每轮改了哪些场景、为什么改，都进入版本历史，而不是被下一次生成覆盖。'
    )

    # Compare observed outputs and the defined one-shot workflow separately.
    page('早期测试暴露：改不全、改错、缺少依赖追踪', '历史证据 · 为什么需要可检查流程', '核心机制未替换：后续测试反馈；数字错误：早期冻结输出；依赖追踪：流程对照')
    card(.74, 2.08, 3.77, 3.86, '改不全 · 后续测试反馈', '核心系统没改掉', '要求替换换分系统，\n输出仍保留旧机制。\n核心要求没落实。', RED)
    card(4.79, 2.08, 3.77, 3.86, '改错 · 早期冻结输出', '人物结果写串了', '沈曼换后应为 330，\n庭审却写成 487。\n台词顺，事实对不上。', RED)
    card(8.84, 2.08, 3.77, 3.86, '漏依赖风险 · 流程短板', '连带改动缺少追踪', '一次生成就结束，\n没有独立的影响清单，\n漏改需要编剧自行排查。', GOLD)
    takeaway('全文写出来了，核心有没有改、后文有没有跟上，仍然要靠人追问。', RED)
    d.notes(24, '回看早期测试和流程对照，Baseline 暴露出三类短板。改不全：后续测试反馈中，要求换掉的核心系统仍然保留。改错：早期冻结成稿把沈曼的结果写成别人的分数。再看流程，它没有独立的依赖追踪和影响清单，连带漏改需要编剧自行排查。全文写出来，不等于改编做完。')

    page('StoryBridge 把三类风险，变成可检查的交付项', '项目优势 · 方案有对象，改动有路径，问题能回修')
    t('编剧关心什么', .98, 2.05, 2.80, .38, 17, MUTED, True)
    t('StoryBridge 提供什么', 3.87, 2.05, 4.06, .38, 17, GREEN, True)
    t('本案例的实际产物', 8.55, 2.05, 3.67, .38, 17, MUTED, True)
    rows=[('核心改了什么？','文化节点＋选定改编方案','高考 → SAT/ACT\n与大学申请体系'),
          ('哪些后文要跟着改？','依赖图＋场景清单＋原因路径','CM01 → 7 个场景\n每场附原文依据'),
          ('发现问题怎么继续？','检查报告＋按场修复记录','12/12 场景、7/7 承诺\n错误 0，待确认 1')]
    for i,(question,method,result) in enumerate(rows):
        y=2.73+i*1.04
        r(.77,y,11.81,.88,WHITE,LINE,True)
        t(question,.98,y+.24,2.82,.43,20,INK,True)
        t(method,3.87,y+.24,4.43,.43,20,GREEN,True)
        t(result,8.55,y+.13,3.75,.66,18,INK)
    takeaway('Baseline 交出成稿；StoryBridge 还交出改编依据、影响路径和修复记录。')
    d.notes(32, 'StoryBridge 的价值，是把刚才三类风险变成编剧能检查的东西。核心改什么，有文化节点和选定方案，这次把高考换成 SAT、ACT 与大学申请体系。牵动哪里，有依赖图、七个场景和逐条原文依据。出了问题，有检查报告和按场修复记录；最新结果检查十二个场景和七项承诺，错误为零，并保留一项待人工确认。Baseline 交出成稿以后，这些仍要编剧自己追；我们的工作台把依据一起交出来。')

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

    # 11 — Product demonstration, not another retelling of the plot.
    page('把方法做进工作台：选、查、改都能操作', '18 秒真实产品演示', '操作演示 · 已省略生成等待')
    d.movie(out/'StoryBridge_18秒操作演示.mp4', assets/'system_video_poster.png', .74, 1.90, 8.98, 5.05125)
    for y, n, title, sub in [(2.23, '01', '选方案', '决定怎么改'), (3.79, '02', '看影响', '找到关联场景'), (5.35, '03', '审改稿', '核对前后文字')]:
        t(n, 10.07, y, .58, .42, 22, GOLD, True)
        t(title, 10.73, y, 2.05, .43, 24, GREEN, True)
        t(sub, 10.07, y+.68, 2.71, .43, 19, INK)
    d.notes(30, '这十八秒展示的是实际工作台。看三个动作：选择方案、查看影响、对照改稿。方法已经落成可以操作的产品。【播放十八秒。】编剧能沿着方案和关联场景，找到要核对的具体文字。')

    # 12 — Deliverables are more important than a generic capability slogan.
    page('交给编剧的，是一套能继续工作的改编成果', '项目交付价值')
    card(.74, 2.08, 3.77, 3.86, '可阅读', '目标语言剧本', '按场景组织成稿，\n保留原文与改稿对照，\n方便逐场审阅。')
    card(4.79, 2.08, 3.77, 3.86, '可解释', '改编依据', '选了哪种方案，\n影响了哪些场景，\n都能回头查。')
    card(8.84, 2.08, 3.77, 3.86, '可继续', '检查与修改记录', '问题落到具体场景，\n保留版本和修改记录，\n方便继续审稿、修稿。')
    takeaway('一次生成交出一份文本；StoryBridge 提供继续审、继续改的工作台。')
    d.notes(28, '最终交给编剧的有三部分。第一，按场景组织的目标语言稿和改前改后对照。第二，改编方案与影响范围，能解释为什么这么改。第三，检查结果、版本和修改记录，方便继续审稿和修稿。从选方案到交接成果，StoryBridge 提供的是完整工作台。')

    # 13 — Return to the project, not a final line from the example.
    d.slide('', '主讲结束', '跨文化故事改编智能体', dark=True)
    d.pages[-1]['title'] = 'StoryBridge：让改编有依据，让剧情接得上'
    t('StoryBridge', .78, 1.19, 11.78, .68, 36, '#E8C78F', True, align='center')
    t('让改编有依据，\n让剧情接得上。', .78, 2.62, 11.78, 1.57, 40, WHITE, True, align='center')
    t('选方案  →  追踪影响  →  检查修复', .78, 4.73, 11.78, .57, 27, '#D3DFE3', align='center')
    t('谢谢大家', .78, 5.89, 11.78, .56, 28, '#E8C78F', True, align='center')
    d.notes(16, 'StoryBridge 把文化改编、影响追踪和检查修复接成一个产品。核心改法有对象，连带场景有路径，后续修稿有依据。让改编有依据，让剧情接得上。谢谢大家。')
