from __future__ import annotations

import json

from app.schemas import AdaptationOption

SYSTEM_STORY_EXPERT = (
    "你是一名精通中文短剧与网文叙事结构的故事分析师。"
    "你只输出严格合法的 JSON，不输出任何解释性文字。"
    "所有 id 必须严格遵守给定的前缀规范。"
)

SYSTEM_LOCALIZATION_EXPERT = (
    "你是一名中文内容出海的跨文化本土化专家，熟悉北美短剧市场。"
    "你只输出严格合法的 JSON。"
    "你的任务不是翻译语言，而是在保持叙事功能（人物动机、因果关系、伏笔回收、情绪效果）的前提下进行文化机制替换。"
)


def _json_block(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


PARSE_STORY_SCHEMA = """{
  "characters": [{"id": "C01", "name": "...", "role": "protagonist|antagonist|supporting|minor", "description": "...", "goals": ["..."]}],
  "scenes": [{"id": "S01", "title": "...", "summary": "一句话概括本场景发生什么", "text": "场景原文", "character_ids": ["C01"], "event_ids": ["E01"]}],
  "events": [{"id": "E01", "description": "...", "scene_ids": ["S01"]}],
  "settings": [{"id": "SET01", "name": "...", "description": "世界观事实，如时代、城市、职业背景"}],
  "culture_mechanisms": [{"id": "CM01", "name": "文化机制名称，如：编制", "description": "...", "surface_text": ["剧本中出现的原词"], "scene_ids": ["S01"]}],
  "commitments": [{"id": "NC01", "description": "故事已建立、后续不可破坏的叙事承诺", "established_at_scene_id": "S02", "payoff_scene_id": null, "must_preserve": true}],
  "dependencies": [{"source_id": "CM01", "target_id": "E03", "relation": "motivates|causes|depends_on|references|appears_in|sets_up|pays_off", "evidence": "支持该关系的原文片段", "confidence": 0.9}]
}

注意：输出顶层必须是一个 JSON 对象（如上所示），绝不要输出数组。characters/scenes/... 是这个对象的字段。"""


def parse_story_system() -> str:
    return SYSTEM_STORY_EXPERT + "\n输出会很长，请务必完整输出所有场景与依赖，不要省略。"


def parse_story_user(script_text: str, target_market: str = "") -> str:
    return (
        "分析以下中文短剧剧本，抽取故事结构。输出 JSON，schema 如下：\n\n"
        f"{PARSE_STORY_SCHEMA}\n\n"
        "要求：\n"
        "1. id 规范：Character=C 前缀、Scene=S 前缀、Event=E 前缀、Setting=SET 前缀、"
        "CultureMechanism=CM 前缀、Commitment=NC 前缀，编号从 01 开始。\n"
        "2. scenes 按剧本顺序编号；每个 scene 的 text 保留原文（可精简舞台提示但保留台词）。\n"
        "3. culture_mechanisms 抽取目标文化读者可能不理解的中国特有社会/文化元素"
        "（如编制、彩礼、985、户口、相亲、催婚等），surface_text 填剧本原词。\n"
        "4. commitments 记录明确的伏笔与叙事承诺（如'结尾必须身份反转'），有回收场景的填 payoff_scene_id。\n"
        "5. dependencies 是重点。边方向约定：\n"
        "   - 场景 --references--> 它引用的文化机制；人物动机链用 机制 --motivates--> 事件、事件 --causes--> 事件；\n"
        "   - 人物 --appears_in--> 场景，事件 --appears_in--> 它发生的场景；\n"
        "   - 前置 --sets_up--> 后续回收，承诺 --depends_on--> 其依赖的机制。\n"
        "   一个机制影响多个场景时，每条依赖单独一条记录。\n"
        "6. 只输出 JSON。\n\n"
        f"目标市场（可空）：{target_market or '未指定'}\n\n"
        "剧本全文：\n---\n"
        f"{script_text}\n---"
    )


FRICTION_SCHEMA = """{
  "mechanisms": [
    {
      "id": "CM01",
      "friction_level": "high|medium|low",
      "narrative_importance": "high|medium|low",
      "functions": {
        "plot": ["从 motivation|constraint|conflict|revelation|foreshadowing|payoff|reversal 中选"],
        "social": ["从 status|power|obligation|kinship|reputation|institutional_access|economic_security 中选"],
        "emotional": ["从 humiliation|aspiration|fear|sympathy|suspense|satisfaction 中选"]
      }
    }
  ]
}"""


FRICTION_ANCHORS = """分级锚定标准（必须严格对照，不确定时取较低档）：
- high：目标市场观众完全无法从字面理解该元素为何重要，需成段解释才成立。
  例：编制/彩礼/户口/985（涉及他国特有制度或社会结构）。
- medium：字面可猜但社会分量会被大幅低估。
  例：相亲/催婚/敬酒规矩（跨文化存在相似物但含义不同）。
- low：仅是地方色彩，不影响剧情理解。
  例：春节/饺子/微信红包（可保留或轻注即可）。
narrative_importance 锚定：
- high：该元素承载人物核心动机、关键冲突或伏笔回收，改它牵动 3+ 场景。
- medium：影响 1-2 个场景的因果或台词。
- low：纯氛围点缀。"""


def detect_frictions_system() -> str:
    return SYSTEM_LOCALIZATION_EXPERT


def detect_frictions_user(state_digest_json: str, target_market: str) -> str:
    return (
        "以下是已抽取的故事状态 JSON。请对其中每一个 culture_mechanism 评估跨文化摩擦度并补充叙事功能标签。"
        f"输出 JSON schema：\n\n{FRICTION_SCHEMA}\n\n"
        f"{FRICTION_ANCHORS}\n\n"
        "评估要求：\n"
        "- friction_level：目标市场观众无法理解该元素重要性的程度。\n"
        "- narrative_importance：该元素承担的剧情功能有多关键（影响的动机/因果/伏笔越多越 high）。\n"
        "- 严格按锚定标准打分，同一元素多次评估应得到相同档位。\n"
        "- functions 只能从枚举中选，可多选。\n"
        "只输出 JSON。\n\n"
        f"目标市场：{target_market}\n\n"
        f"故事状态：\n{_json_block(state_digest_json)}"
    )


PLAN_OPTIONS_EXAMPLE = json.dumps(
    AdaptationOption(
        option_label="B",
        strategy="functional_replacement",
        title="示例标题",
        replacement_definition="替换后的具体设定",
        rationale="为什么这样改",
        preserved_functions=["status"],
        lost_functions=["institutional_access"],
        risks=["风险说明"],
    ).model_dump(),
    ensure_ascii=False,
    indent=2,
)


def plan_adaptation_system() -> str:
    return SYSTEM_LOCALIZATION_EXPERT


def plan_adaptation_user(
    mechanism_json: str,
    related_context_json: str,
    target_market_profile: dict,
) -> str:
    return (
        "请为下面这个中国文化机制生成面向目标市场的改编方案。输出 JSON：\n"
        '{\n'
        '  "culture_mechanism_id": "CM01",\n'
        '  "original_name": "机制名",\n'
        '  "friction_level": "high|medium|low",\n'
        '  "options": [三个方案，option_label 分别为 A/B/C]\n'
        "}\n\n"
        f"每个 option 的字段结构：\n{PLAN_OPTIONS_EXAMPLE}\n\n"
        "要求：\n"
        "1. 必须给出恰好三个方案：\n"
        "   - A strategy=preserve：保留中国语境，仅加注或弱化；\n"
        "   - B strategy=functional_replacement：在目标文化中找到功能等效元素（保留 plot/social/emotional 功能）；\n"
        "   - C strategy=plot_reconstruction：重构冲突机制（改动更大但更彻底）。\n"
        "2. replacement_definition 要具体到可直接指导台词改写。\n"
        "3. 若机制名是泛化词（如'世家''门阀'），替换定义必须给出与原词字面无重叠的具体新设定"
        "（如'百年财阀帝国'而非近义词'家族'），禁止用近义词糊弄。\n"
        "3. preserved_functions / lost_functions 从该机制的叙事功能出发逐条说明。\n"
        "4. 避免刻板印象；结合目标受众画像，不要把整个国家当成单一文化。\n"
        "只输出 JSON。\n\n"
        f"文化机制数据：\n{_json_block(mechanism_json)}\n\n"
        f"相关上下文（涉及场景/事件/承诺/依赖边）：\n{_json_block(related_context_json)}\n\n"
        f"目标市场画像：\n{_json_block(target_market_profile)}"
    )


REWRITE_SCHEMA = """{
  "id": "<与输入相同的场景 id>",
  "title": "...",
  "summary": "改写后的一句话摘要",
  "text": "改写后的完整场景文本"
}"""


def rewrite_scene_system() -> str:
    return SYSTEM_LOCALIZATION_EXPERT


def rewrite_scene_user(
    scene_json: str,
    adaptation_brief: str,
    must_preserve_commitments: list[str],
    neighbor_summaries: list[str],
    character_sheet: str,
) -> str:
    commitments = "\n".join(f"- {c}" for c in must_preserve_commitments) or "- （无）"
    neighbors = "\n".join(f"- {s}" for s in neighbor_summaries) or "- （无相邻场景信息）"
    return (
        "你正在执行一次【局部改写】任务。只重写指定场景，不要改写其他场景的内容。\n\n"
        f"当前已确定的改编决定：\n{adaptation_brief}\n\n"
        f"必须保留的叙事承诺（Narrative Commitments）：\n{commitments}\n\n"
        f"相邻场景摘要（用于衔接，禁止修改其事实）：\n{neighbors}\n\n"
        f"相关人物设定：\n{character_sheet}\n\n"
        f"待改写场景：\n{_json_block(scene_json)}\n\n"
        f"输出 JSON schema：\n{REWRITE_SCHEMA}\n\n"
        "要求：\n"
        "1. 彻底移除已被替换的文化机制的旧表述（包括同义说法），换成本地化设定下自然的表达。\n"
        "2. 保持人物关系、事件顺序、情绪走向不变，除非改编决定明确要求重构。\n"
        "3. 不新增与其他场景冲突的事实。\n"
        "4. text 使用与原文一致的剧本文体（场景描述+台词）。只输出 JSON。"
    )


VERIFY_SCHEMA = """{
  "issues": [
    {
      "issue_type": "stale_reference|fact_conflict|motivation_break|commitment_violation|unresolved_payoff",
      "severity": "error|warning|info",
      "scene_id": "S03 或 null",
      "description": "...",
      "evidence": "问题原文片段"
    }
  ],
  "commitment_checks": [
    {"commitment_id": "NC01", "status": "preserved|violated|needs_review", "explanation": "..."}
  ]
}"""


def verify_consistency_system() -> str:
    return SYSTEM_STORY_EXPERT


def verify_consistency_user(
    state_digest_json: str,
    changed_scene_ids: list[str],
    applied_adaptations_summary: str,
) -> str:
    return (
        "请对改编后的故事做一致性审查。审查范围：全故事，重点是刚被修改的场景。\n\n"
        "**检查范围规则（最重要）**：\n"
        "- 只有 adapted_to 非空的机制才属于'已替换'，其旧表述出现在场景文本中才是 stale_reference。\n"
        "- 未改编的机制（adapted_to 为 null）出现在任何地方（场景/事件/摘要）都完全正常，绝不报告。\n"
        "- events/settings 是结构元数据，其中出现旧词不算场景残留，不要据此报告。\n"
        "- 改编后的新表述（如'婚礼基金''稳定职业'）是正确内容，不是残留。\n\n"
        "其他检查项：\n"
        "1. fact_conflict：人物事实/世界观自相矛盾。\n"
        "2. motivation_break：人物行为失去动机支撑。\n"
        "3. commitment_violation：叙事承诺被破坏。\n"
        "4. unresolved_payoff：伏笔失去回收。\n\n"
        "**关键规则**：\n"
        "- evidence 必须逐字摘自场景 text，禁止推测。\n"
        "- 只报告确实存在的问题。不是问题的、不确定的、规则里排除的，一律不输出。\n"
        "- description 用一句话陈述事实（<60字），禁止推理过程、禁止'但…然而…因此'式分析。\n"
        "- issues 为空数组是完全正常的输出，不要为了凑数而报告。\n\n"
        f"输出 JSON schema：\n{VERIFY_SCHEMA}\n\n"
        "注意：必须对每一条 commitment 给出检查结果。只输出 JSON。\n\n"
        f"刚修改过的场景：{changed_scene_ids}\n\n"
        f"已应用的改编决定：\n{applied_adaptations_summary or '（无）'}\n\n"
        f"故事状态（含全部场景文本）：\n{_json_block(state_digest_json)}"
    )
