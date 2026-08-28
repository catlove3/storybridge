from __future__ import annotations

BASELINE_TRANSLATE_SYSTEM = "你是一名专业的中英影视字幕译者。"

BASELINE_TRANSLATE_USER = """请把以下{source_language}短剧剧本翻译成{target_language}。要求译文自然流畅。
必须输出严格 JSON：
{{"source_language":"{source_language}","target_language":"{target_language}","target_locale":"{target_locale}","scenes":[{{"id":"S01","title":"...","summary":"...","text":"..."}}]}}
必须保留输入中的全部场景 ID 和顺序，不得合并或拆分场景。

剧本：
---
{script}
---

只输出 JSON。"""


BASELINE_STRONG_PROMPT_SYSTEM = """\
你是一名中文内容出海的跨文化本土化专家。你将一次性完成整个剧本的深度本土化改写。"""

BASELINE_STRONG_PROMPT_USER = """请把这个中国短剧深度本土化为面向{market}观众的短剧：
1. 分析文化差异，识别中国特有的文化元素（如编制、彩礼、985、户口、相亲等）；
2. 将这些元素改写为目标文化中能产生相似叙事效果的表达；
3. 保持人物动机、因果关系、伏笔与回收、情绪效果一致；
4. 保证前后剧情一致，不遗漏任何对旧设定的引用；
5. 输出改编后的完整剧本（{language}）；
6. 必须输出严格 JSON：
{{"source_language":"{source_language}","target_language":"{language}","target_locale":"{target_locale}","scenes":[{{"id":"S01","title":"...","summary":"...","text":"..."}}]}}
必须保留输入中的全部场景 ID 和顺序，不得合并或拆分场景。

目标受众画像：{profile}

剧本：
---
{script}
---

只输出 JSON。"""
