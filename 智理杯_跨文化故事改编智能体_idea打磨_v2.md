# “智理杯”智能体大赛选题打磨：跨文化故事改编智能体

> 工作文档 v2  
> 当前目标：把一个“听起来不错”的想法，收敛成两个低年级 CS 学生在比赛周期内能够真正做出来、演示出来、解释清楚的智能体项目。

---

# 0. 一句话结论

当前最推荐的项目定位是：

> **面向中文短剧 / 网文出海的 AI 跨文化故事改编智能体：它不只是翻译文本，而是理解文化元素在故事中的叙事功能，通过显式的故事状态与依赖关系规划本土化方案，并在一个设定发生变化后自动追踪、修改和验证受影响的后续剧情。**

项目现阶段**不要做成“大而全的 AIGC 内容生产平台”**。

比赛版本建议只聚焦一个最能体现智能体价值的闭环：

> **识别文化摩擦点 → 分析其叙事功能 → 给出本土化方案 → 用户选择 → 找到受影响的后续剧情 → 自动传播修改 → 一致性检查**

只要这个闭环做扎实，即使：

- 不生成视频
- 不生成分镜
- 不支持几十万字长篇小说
- 不训练自己的模型

依然可以成为一个完整、有明确技术点的智能体项目。

---

# 1. 为什么要做这个项目

中文网文、短剧、漫剧出海时，真正困难的部分往往不是“把中文翻译成英文”，而是：

> **为什么这个情节在中国文化语境里成立？如果换到另一个文化环境，如何让相同的冲突、人物动机和情绪效果继续成立？**

例如：

- 985 / 211
- 编制
- 彩礼
- 户口
- 相亲
- 赘婿
- 家庭催婚
- 宗族关系
- 敬酒
- 微信红包
- “稳定工作”
- “给领导面子”

这些元素即使被准确翻译，目标文化观众也不一定能理解它们为什么重要。

因此我们想解决的不是：

> 中文 → 英文

而是：

> **源文化中的叙事机制 → 目标文化中能够产生相似叙事效果的机制**

---

# 2. 一个最典型的例子：985 到底应该怎么“翻译”

原剧情：

> 男主高考只考上普通一本，被女友嫌弃。  
> 三年后男主创业成功，回到高中同学聚会。  
> 曾经考上 985 的情敌当众嘲讽他学历低。  
> 最后大家发现情敌正在男主公司求职。

如果直接翻译：

```text
985 University → Project 985 university
```

目标观众可能根本不知道这意味着什么。

如果稍微改写成：

```text
985 University → prestigious university
```

虽然语言自然了一点，但仍然只是在替换名词。

真正需要回答的是：

## “985”在这个剧情里承担什么功能？

例如：

```text
Plot Function:
- 建立人物早期差距
- 为后续身份反转做铺垫

Social Function:
- 学业精英身份
- 同龄人社会地位比较

Emotional Function:
- 男主受辱
- 为后续“打脸”积累情绪势能
```

因此，本土化时可以提供多个候选方案：

```text
方案 A：Ivy League graduate
方案 B：Stanford graduate
方案 C：valedictorian + elite college admission
```

然后继续判断：

> 如果这里从“985”改成“Stanford”，后文有哪些人物动机、台词、职业设定和伏笔必须一起变化？

这一步才是本项目区别于普通翻译和一次性大模型改写的关键。

---

# 3. 项目的核心概念：Narrative Function Preserving Adaptation

可以把底层任务暂时概括为：

## Narrative Function Preserving Adaptation

中文可称为：

> **叙事功能保持的跨文化改编**

更适合产品展示的一句话可以是：

> **迁移文化，不迁丢爽点。**

但比赛材料中不宜只讲“爽点”，还应使用更严谨的概念：

- 人物动机
- 因果关系
- 世界观事实
- 伏笔与回收
- 身份 / 权力关系
- 冲突机制
- 情绪功能
- Narrative Commitments（故事已经建立、后续不能随意破坏的事实和承诺）

---

# 4. 产品边界：现在一定要收窄

## 4.1 比赛版本的主营场景

建议只讲：

> **中文短剧 / 短篇网文 → 北美市场的跨文化改编辅助**

为什么先选短剧 / 短篇而不是几十万字小说：

1. 数据规模更可控；
2. 场景数有限，容易构建依赖关系；
3. 比赛现场容易看懂；
4. 可以设计出清楚的 baseline 对比；
5. 两个人在有限时间内更有可能做完整闭环。

---

## 4.2 暂时不要做的东西

比赛 MVP 不建议投入大量时间做：

- 小说 → 剧本
- 剧本 → 分镜
- 文生图
- 图生视频
- AI 数字人
- 自动配音
- 多语言全覆盖
- 支持任意百万字小说
- 完整影视生产平台

这些功能已有很多成熟模型和产品可以完成，而且会极大消耗开发时间。

我们的重点应该是：

> **跨文化改编决策与故事一致性维护**

---

## 4.3 “西游记 + 系统”等传统文学二创怎么处理

这个方向可以保留，但**不要作为初赛第二主营业务**。

否则产品会从：

> “解决一个明确的内容出海问题”

迅速变成：

> “万能 AI 写作 / 二创工具”

更好的表达是：

> 同一套“理解故事结构—修改设定—传播影响”的底层能力，未来还可以拓展至经典文学二创、IP 重构等场景。

最多在最后作为扩展性展示。

---

# 5. 三个必须解决的致命问题

这三个问题应该贯穿后续所有产品和技术设计。

---

# 致命问题 1：为什么不用 ChatGPT / Claude 直接做？

这是最危险的问题。

评委完全可以问：

> 我直接把整个剧本放进 ChatGPT 或 Claude，再写一个很详细的 Prompt：
>
> “识别文化元素、分析叙事功能、改成美国背景，并保证前后剧情一致。”
>
> 为什么还需要你们？

这个问题如果回答成：

> “我们的 Prompt 更好”

项目基本就塌了。

---

## 5.1 我们真正需要提供的差异

普通一次性大模型工作流：

```text
whole_story + instruction
          ↓
        LLM
          ↓
   rewritten_story
```

我们希望做成：

```text
原始剧本
   ↓
结构化 Story State
   ↓
文化摩擦点检测
   ↓
改编计划
   ↓
用户选择一个文化设定修改
   ↓
依赖关系查询
   ↓
找到受影响 Scene
   ↓
局部修改
   ↓
一致性验证
   ↓
可审计修改记录
```

区别不应该是“大模型更聪明”，而是：

### 1. Explicit State

系统显式保存：

- 人物
- 人物关系
- 关键事件
- 世界观事实
- 人物动机
- 伏笔
- 叙事承诺
- 文化机制

而不是每一次都让大模型从全文重新理解。

### 2. Dependency Propagation

一个设定发生变化后：

> 系统明确计算 / 检索哪些剧情节点可能受到影响。

### 3. Auditable Adaptation

用户可以看到：

- 原来是什么
- 为什么需要改
- 它承担什么叙事功能
- 有哪些方案
- 用户选了哪一个
- 哪些场景因此被修改
- 修改后还有没有冲突

这三点应该成为“为什么不是 ChatGPT Wrapper”的核心回答。

---

# 致命问题 2：如何判断一次 Adaptation 是好的？

“海外观众觉得自然，同时原作爽点不丢”很好听，但必须可评价。

否则最后可能只是：

> Agent A 改了一版 → Agent B 说很好 → 我们宣布成功。

这种评测说服力很低。

---

## 5.2 建议的三维评价体系

### A. Preservation：原故事关键叙事功能是否保留

在改编之前，先抽取核心 Narrative Commitments。

例如：

```text
C1：男主一开始社会地位低于男二
C2：女方家庭反对婚姻
C3：分手必须来源于“前途 / 地位”冲突
C4：结尾必须发生身份反转
C5：身份反转必须回收前面的羞辱
```

改编之后检查这些 Commitment 是否仍然成立。

可以输出：

```text
Narrative Preservation
C1 ✓
C2 ✓
C3 ✓
C4 ✓
C5 ⚠
```

---

### B. Naturalness：目标文化下是否自然

这个维度最难完全自动化。

MVP 阶段不必假装已经解决。

可以采用：

- LLM Judge 作为辅助
- 人工小规模打分
- 目标文化背景测试者反馈
- 基础规则检查

重点是承认：

> **文化自然度本身存在主观性，AI 只能辅助，不应该宣称拥有“唯一正确的美国文化答案”。**

---

### C. Consistency：修改后故事是否自洽

这是比赛阶段最应该重点量化的指标。

例如：

- 人物事实冲突数
- 未同步修改的文化引用数
- 动机不一致节点数
- 世界观冲突数
- 未回收伏笔数
- 受到影响但未更新的 Scene 数量

可以做 baseline：

```text
强 LLM 一次性改写：
遗漏 5 个 downstream references

我们的 Agent：
遗漏 1 个
```

这种结果比“我们觉得我们的文化适配更自然”更容易说服评委。

---

# 致命问题 3：Story Graph 到底是不是装饰？

Story Graph 本身不是创新。

“把人物、事件、关系做成图”已经是很常见的故事理解思路。

真正的问题是：

> **它有没有参与系统决策？**

如果 Story Graph 只是 UI 上画一张漂亮关系图，而真正生成时仍然是：

```python
prompt = whole_story + user_request
answer = llm(prompt)
```

那 Story Graph 基本就是装饰。

---

## 5.3 Story Graph 必须真正驱动三件事

### 1. Affected-scene Retrieval

当“彩礼”被改掉时，Graph 用来查：

> 哪些场景直接 / 间接依赖这个设定？

### 2. Propagation

根据依赖关系：

> 按影响范围生成需要修改的 Scene 列表。

### 3. Verification

改完后再根据 Story State 检查：

> 原有事实和新设定是否仍然冲突？

只有真正参与这三步，Graph 才有存在价值。

---

# 6. Story Graph 不要一开始做得过于复杂

对于两个低年级 CS 学生，不建议上来设计一个巨大的文学知识图谱。

比赛 MVP 可以只存非常有限的对象。

---

## 6.1 推荐的节点类型

```text
Character        人物
Scene            场景
Event            事件
Setting          设定 / 世界观事实
CultureMechanism 文化机制
Commitment       叙事承诺
```

---

## 6.2 推荐的边类型

先控制在几个最有用的关系：

```text
appears_in
motivates
causes
depends_on
references
reveals
conflicts_with
sets_up
pays_off
```

没必要一开始追求一个“文学理论完备”的 ontology。

---

## 6.3 例子

```text
[彩礼]
   │
   ├── motivates ──> [男主借钱]
   │
   ├── causes ─────> [女方父母羞辱男主]
   │
   ├── appears_in ─> [Scene 2]
   │
   ├── references ─> [Scene 5]
   │
   └── sets_up ────> [Scene 8 身份反转]
```

用户把：

```text
彩礼
```

替换成：

```text
女方家庭设置的经济门槛
```

系统查询这些边，就能找到优先需要重新检查的场景。

---

# 7. “叙事功能”也不能只让 LLM 自由发挥

“彩礼的叙事功能是什么？”这个问题本身很模糊。

它可能同时承担：

- 家庭控制
- 阶层羞辱
- 婚姻经济压力
- 男女家庭权力关系
- 主角贫穷证明
- 后续逆袭铺垫

所以 MVP 阶段可以把叙事功能**半结构化**。

---

## 7.1 Plot Function

```text
Motivation
Constraint
Conflict
Revelation
Foreshadowing
Payoff
Reversal
```

---

## 7.2 Social Function

```text
Status
Power
Obligation
Kinship
Reputation
Institutional Access
Economic Security
```

---

## 7.3 Emotional Function

```text
Humiliation
Aspiration
Fear
Sympathy
Suspense
Satisfaction
```

例如：

```text
Culture Mechanism: 彩礼

Plot:
Conflict / Setup

Social:
Economic Status
Family Power

Emotional:
Humiliation
Anticipation of Payoff
```

这样比让模型自由写一段散文式分析更容易：

- 存储
- 比较
- 传播
- 验证
- 展示

---

# 8. 不要把“美国文化”当成一个整体

一个明显风险是文化刻板印象。

不能简单输入：

```text
Target Culture: America
```

然后让模型自己想象“美国人一般怎么样”。

更合理的是把目标市场描述得更具体：

```text
Market:
United States

Audience:
18–30

Format:
Vertical drama

Genre:
Romance / revenge

Setting:
Contemporary New York

Localization Intensity:
High
```

如果未来继续做，还可以加入：

- 地区
- 年龄
- 社会阶层
- 作品类型
- 平台
- 目标受众偏好

因此我们的目标不是：

> 模拟一个国家的“唯一文化”

而是：

> **在明确的目标受众、类型和故事设定下做文化适配。**

这也能降低刻板化表达的风险。

---

# 9. Human-in-the-loop 不能变成“用户点 70 次”

如果一个剧本检测出 50 个文化摩擦点，然后要求用户逐个：

> A / B / C 选择

体验会非常糟糕。

所以应该先有：

# Adaptation Policy

例如：

```text
Localization Style:
High-intensity North American adaptation

Policy:
- 地理位置全部本土化
- 教育制度采用功能等效替换
- 婚姻 / 家庭制度高影响节点需人工确认
- 食物 / 节庆默认保留
- 人物核心性格不得修改
- 主线事件顺序默认保持
```

系统自动处理：

> 低风险、低影响、高置信度节点

只把：

> 高影响 + 高不确定度

的少数节点交给用户。

可以把 Human Review Priority 定义成：

```text
Review Priority
≈ Narrative Importance
× Adaptation Uncertainty
× Downstream Impact
```

不一定真的需要严谨数学公式，但这个思路很适合做产品交互。

---

# 10. 不要为了“智能体”硬做很多 Agent

比赛名字里有“智能体”，不等于必须做：

```text
Story Agent
Culture Agent
Translator Agent
Critic Agent
Director Agent
Manager Agent
Supervisor Agent
```

多 Agent 会带来：

- Token 成本
- 延迟
- 状态冲突
- 调试困难
- 错误级联

对于两个人的比赛项目，更推荐：

```text
                 Orchestrator
                /            \
        Story State          LLM
      (Graph / JSON)          │
                              │
             analyze / plan / rewrite
                              │
                              ↓
                     Consistency Checker
```

也就是：

> **一个主 Agent + 几个明确的工具 / 模块**

完全够用。

---

# 11. 推荐的最小技术架构

## 11.1 模块 1：Story Parser

输入：

```text
5～15 场中文短剧剧本
```

输出结构化 JSON：

```json
{
  "characters": [],
  "scenes": [],
  "events": [],
  "settings": [],
  "culture_mechanisms": [],
  "commitments": [],
  "dependencies": []
}
```

第一版可以完全通过 LLM Structured Output 完成。

不用训练模型。

---

## 11.2 模块 2：Culture Friction Detector

对每个候选文化元素输出：

```json
{
  "element": "彩礼",
  "scene_ids": ["S2", "S5"],
  "friction_level": "high",
  "narrative_importance": "high",
  "plot_functions": ["conflict", "setup"],
  "social_functions": ["economic_status", "family_power"],
  "emotional_functions": ["humiliation"]
}
```

---

## 11.3 模块 3：Adaptation Planner

给高优先级元素生成：

```text
方案 A：保留中国文化语境
方案 B：寻找功能等效元素
方案 C：重构冲突机制
```

每个方案必须解释：

```text
- 为什么这样改
- 原叙事功能保留了哪些
- 会影响哪些 Scene
- 风险是什么
```

---

## 11.4 模块 4：Dependency Resolver

这是 MVP 最重要的技术模块。

输入：

```text
changed_node = “彩礼”
```

查询：

```text
直接 references 它的 Scene
依赖它的人物动机
依赖它的后续事件
依赖它的 payoff / foreshadowing
```

输出：

```text
Affected Scenes:
S2
S5
S7
S9
```

第一版完全可以：

> NetworkX / 自己写邻接表 + BFS / DFS

没必要上 Neo4j。

---

## 11.5 模块 5：Scene Rewriter

只重写受到影响的场景，而不是全文重新生成。

输入包括：

```text
- 当前 Scene
- 新文化设定
- 必须保留的 Narrative Commitments
- 相邻场景摘要
- 角色状态
```

输出新 Scene。

---

## 11.6 模块 6：Consistency Checker

重新检查：

```text
人物事实是否冲突
旧文化元素是否仍被引用
人物动机是否成立
关键 Commitment 是否仍被满足
伏笔是否仍能回收
```

输出：

```text
✓ S5 consistent
✓ S7 consistent
⚠ S9 still references original setting
```

---

# 12. 推荐的 Agent 工作流

完整闭环：

```text
用户上传短剧
      ↓
Story Parser
      ↓
建立 Story State / Graph
      ↓
Culture Friction Detector
      ↓
展示文化摩擦点
      ↓
用户选择目标市场 + Adaptation Policy
      ↓
Planner 给高影响节点生成候选方案
      ↓
用户确认修改
      ↓
Dependency Resolver
      ↓
定位受影响 Scenes
      ↓
Scene Rewriter
      ↓
Consistency Checker
      ↓
发现冲突？
   ↙        ↘
 Yes        No
 ↓           ↓
再次修复     输出 Adapted Script
```

这就是最基本的 Agent Loop：

> **Observe → Plan → Act → Verify → Revise**

---

# 13. 最适合比赛现场的 Demo

不要用几十页小说。

专门写一个 **8～10 场狗血中文短剧**，其中加入彼此依赖的文化设定。

例如：

```text
男主没有“稳定编制”
        ↓
女方父亲认为他没有前途
        ↓
提出高额彩礼作为经济保障
        ↓
男主为了筹钱放弃创业机会
        ↓
女主误以为他没有事业心
        ↓
分手
        ↓
数年后男主创业成功
        ↓
身份反转 / payoff
```

这里：

- 编制
- 彩礼
- 家庭婚姻决策

不能独立随便替换。

---

## 13.1 Demo 高潮

用户点击：

```text
“编制” → 改为适合目标市场的“职业稳定性 / 社会地位机制”
```

页面立即显示：

```text
This adaptation may affect:

Scene 1
Scene 2
Scene 4
Scene 7

Reason:
✓ Motivation dependency
✓ Dialogue reference
✓ Payoff dependency
```

然后用户点击：

```text
Propagate Changes
```

系统局部重写。

最后：

```text
Consistency Check

✓ Scene 1 resolved
✓ Scene 2 resolved
✓ Scene 4 resolved
⚠ Scene 7 contains an outdated reference
```

再自动修复。

这个过程比“一键生成了一篇英文剧本”更能体现智能体。

---

# 14. 一定要准备 Baseline

比赛不能只展示：

> “我们成功改写了一个剧本。”

因为评委不知道普通大模型能做到什么程度。

建议做三个对照：

---

## Baseline A：直接翻译

```text
请把剧本翻译成英文。
```

---

## Baseline B：强 Prompt 的大模型

```text
请把这个中国短剧深度本土化为美国短剧，
分析文化差异，修改不自然的文化元素，
并保证剧情一致。
```

---

## Ours：StoryBridge

显式 Story State + Adaptation Planning + Dependency Propagation + Verification。

---

## 14.1 对比指标

| 能力 | 直接翻译 | 强 Prompt LLM | 我们 |
|---|---:|---:|---:|
| 英文翻译 | ✓ | ✓ | ✓ |
| 文化元素识别 | × | ✓ | ✓ |
| 叙事功能分析 | × | ✓ | ✓ |
| 多方案改编 | × | ✓ | ✓ |
| 显式故事状态 | × | × | ✓ |
| 可查询依赖关系 | × | × | ✓ |
| 修改影响传播 | × | △ | ✓ |
| 局部可控修改 | × | △ | ✓ |
| 可审计修改记录 | × | × | ✓ |
| 一致性验证 | × | △ | ✓ |

真正要拉开差距的是最后几项。

---

# 15. 比赛 MVP：两个低年级 CS 学生应该做到什么程度

目标不是“做一个创业公司级产品”。

目标应该是：

> **让评委完整地看到一个别人不能简单用一次 Prompt 替代的 Agent 闭环。**

---

## P0：必须完成

### 1. 剧本输入

支持一个固定格式或简单文本。

### 2. Story State 抽取

至少抽：

- 人物
- Scene
- 关键事件
- 文化机制
- Narrative Commitments
- dependencies

### 3. Culture Friction Map

识别 3～8 个关键文化摩擦点。

### 4. Adaptation Plan

对高优先级节点给出多个候选方案。

### 5. Dependency Propagation

修改一个节点后：

> 真正通过依赖数据找到后续受影响 Scene。

### 6. 局部重写

只修改 affected scenes。

### 7. Consistency Check

至少能发现：

- 旧元素残留
- 人物事实冲突
- Commitment 被破坏

### 8. 一个能稳定跑通的 Demo

比支持很多剧本更重要。

---

## P1：有时间再做

- 交互式 Story Graph 可视化
- Adaptation Policy
- 风险等级
- 人工确认队列
- 修改前后 Diff
- Adaptation Bible 导出
- 多个目标市场 preset

---

## P2：比赛后再考虑

- 超长网文
- 小说自动转短剧
- 分镜
- 文生图
- 视频
- 多语言
- IP 二创
- 真正商业化工作流

---

# 16. 两个人如何分工

不建议两个人同时到处写。

可以按“系统 / 产品”切。

---

## 同学 A：Agent / 后端 / Story State

负责：

- LLM API 调用
- Structured Output
- Story Parser
- Story Graph 数据结构
- Dependency Resolver
- Consistency Checker
- baseline 实验

---

## 同学 B：前端 / 交互 / Adaptation Flow

负责：

- 剧本上传 / 输入
- Culture Friction Map 展示
- Adaptation Plan UI
- affected scenes 高亮
- 修改 Diff
- 最终 Demo 页面

---

## 两个人共同

- Prompt 设计
- Demo 剧本
- Story schema
- 测试集
- 初赛材料
- 答辩

如果两个人都更偏后端，可以直接使用简单 Web 框架做 UI，不要为了前端效果花太多时间。

---

# 17. 技术选型：能简单就不要复杂

对比赛 MVP，推荐：

```text
Frontend:
Streamlit / Gradio / 简单 React

Backend:
Python

LLM:
现成 API

Structured State:
JSON

Graph:
NetworkX / adjacency list

Storage:
本地 JSON / SQLite

Diff:
Python 文本 diff

Visualization:
NetworkX + PyVis / 前端简单节点图
```

第一版完全没必要：

- 自己训练模型
- Fine-tuning
- Neo4j
- Kafka
- 微服务
- Kubernetes
- 向量数据库
- 复杂 RAG 框架

除非后续真的发现需求。

---

# 18. 初评前的现实开发节奏

比赛日程中 9 月 1 日至 9 月 8 日已经进入初评，因此现在最重要的是：

> **尽快获得一个最小闭环，而不是继续无限讨论功能。**

建议按如下节奏推进。

---

## 8 月 25～26 日：定 Schema + Demo 剧本

完成：

- 项目一句话定义
- 8～10 场测试剧本
- Story State JSON Schema
- 文化节点 Schema
- Narrative Commitment 定义
- baseline Prompt

---

## 8 月 27～28 日：跑通后端闭环

目标：

```text
剧本
↓
抽取结构
↓
修改一个节点
↓
找到 affected scenes
↓
重新生成
↓
检查冲突
```

先命令行跑通。

不追求 UI。

---

## 8 月 29～30 日：做最小 UI

重点页面：

1. 原剧本
2. Culture Friction Map
3. Adaptation Plan
4. Affected Scenes
5. Before / After
6. Consistency Check

---

## 8 月 31 日：Baseline + 数据

至少测试 3～5 个改编案例：

```text
直接翻译
强 Prompt
StoryBridge
```

记录：

- 漏改节点数
- 逻辑冲突数
- commitment preservation 情况

---

## 9 月 1 日以后：打磨初评材料

此时再做：

- 产品介绍
- 技术与应用
- 创新与优势
- 截图 / Demo 链接
- 进一步 UI 美化

这样比先花一周设计完整产品更安全。

---

# 19. 一个非常重要的工程原则：先硬编码一点也没关系

比赛早期不要追求所有东西都自动化。

例如第一版：

- 叙事功能 taxonomy 可以手工定义
- Adaptation Policy 可以只有 2～3 个 preset
- Graph edge 类型可以固定
- Demo 剧本可以精心设计
- Naturalness 可以人工辅助评价

关键是：

> **核心闭环必须真的工作。**

后续再逐渐替换硬编码模块。

---

# 20. 风险清单

---

## 风险 1：最后还是一个 Prompt Wrapper

### 判断标准

如果删掉 Story Graph 后，产品结果几乎不变：

> Graph 没有实际作用。

### 对策

必须让 Graph 参与：

- retrieval
- propagation
- verification

---

## 风险 2：LLM 抽出来的 Graph 本身就错

### 对策

MVP 不需要完美。

可以：

- 限制剧本长度
- 限制 edge 类型
- 给用户允许人工修改关键节点
- 只处理高置信关系

---

## 风险 3：文化适配本身太主观

### 对策

比赛阶段不要承诺：

> “自动生成唯一正确的美国版本。”

而是：

> **帮助创作者发现文化摩擦、理解叙事依赖、比较多个方案，并维护改编一致性。**

最终决策仍然 Human-in-the-loop。

---

## 风险 4：做太多功能导致哪个都不好用

### 对策

始终守住：

> **一个文化设定修改后的依赖传播闭环**

只要它还没做好，就不碰视频 / 分镜。

---

## 风险 5：Story Graph 过于复杂

### 对策

MVP 只需要：

```text
6 类节点
9 类以内的边
```

甚至更少。

---

# 21. 当前版本最合适的创新表述

不要写：

> “我们首创 Story Graph。”

也不要写：

> “我们首创 AI 文化本土化。”

更稳妥的创新点是：

---

## 创新 1：从语言翻译升级为叙事功能迁移

系统不仅识别文化词汇，还分析其在：

- 情节
- 社会关系
- 情绪

中的作用，再生成等效改编方案。

---

## 创新 2：文化修改驱动的依赖传播

一个文化设定发生改变后：

> 自动定位与之相关的人物动机、事件、对白、伏笔和 payoff，并局部更新。

---

## 创新 3：可审计的 Human-in-the-loop Adaptation

不是让大模型黑盒式重写全文。

用户能够看到：

```text
为什么改
→ 有哪些选择
→ 我选择了什么
→ 哪些地方被影响
→ Agent 修改了什么
→ 修改后还有哪些风险
```

---

## 创新 4：Narrative Commitment Verification

把原故事必须保留的关键叙事约束显式化，并在改编后检查这些约束是否仍成立。

---

# 22. 一个更加成熟的产品形态：Adaptation Bible

最终输出除了英文剧本之外，可以生成一份：

# Adaptation Bible

例如：

```text
TARGET
United States
18–30
Vertical Romance Drama

CORE NARRATIVE COMMITMENTS
C1. Male lead begins at lower social status.
C2. Female family controls marriage decision.
C3. Separation is caused by perceived lack of prospects.
C4. Final identity reversal must repay the earlier humiliation.

LOCALIZATION POLICY
High intensity

CRITICAL ADAPTATION 01
Original:
编制

Narrative Function:
Status Security / Family Approval

Adaptation:
Stable career + social prestige

Affected Scenes:
S1 / S2 / S7

Status:
Resolved
```

这个结果比简单输出：

> “这是翻译后的英文剧本”

更像真正提供给编剧 / 内容团队使用的专业工具。

---

# 23. 推荐的比赛叙事顺序

答辩时不要先讲 Agent 架构。

顺序最好是：

---

## Step 1：抛问题

> 中国故事出海时，经常出现“每句话都翻译对了，但整个故事放到海外语境就不成立”的问题。

---

## Step 2：给一个所有人都懂的例子

例如：

> 985 / 编制 / 彩礼

解释：

> 这些不是一个单词，而是一整套社会关系和剧情功能。

---

## Step 3：展示普通 LLM 的缺陷

一次性改写后：

```text
前面改了
后面还引用旧设定
人物动机断了
伏笔回收失败
```

---

## Step 4：展示我们的 Agent

```text
理解故事状态
→ 找文化摩擦
→ 生成方案
→ 用户选择
→ 计算影响
→ 局部修改
→ 一致性验证
```

---

## Step 5：最后讲技术

此时再讲：

- Story State
- Dependency Graph
- Structured Output
- Agent loop
- consistency checker

评委会更容易理解这些技术为什么存在。

---

# 24. 当前建议的项目名字

都只是暂名，不必现在决定。

### StoryBridge

特点：

> 比较直观，强调文化 / 故事之间的桥梁。

### PlotPort

特点：

> Story portability / 跨文化迁移的感觉。

### NarrAdapt

特点：

> Narrative Adaptation，偏技术项目。

### TransPlot

特点：

> 强调故事结构迁移，而不是 translation。

比赛阶段使用一个简单好记的名字即可，不值得投入太多时间。

---

# 25. 当前版本的产品定义 v0.2

> **StoryBridge（暂名）是一款面向中文短剧与网文出海的 AI 跨文化故事改编智能体。与直接翻译或一次性重写不同，它首先将原剧本解析为人物、事件、文化机制、关键叙事承诺及其依赖关系，并识别可能在目标市场造成理解障碍的文化摩擦点。对于高影响节点，系统分析其在情节、社会关系和情绪中的叙事功能，生成“保留、等效替换、剧情重构”等改编方案供创作者选择。当一个文化设定被修改后，StoryBridge 会通过故事依赖关系定位受到影响的后续场景，对其进行局部重写，并检查人物动机、世界观事实、伏笔和核心叙事承诺是否仍然一致。最终目标不是替代编剧，而是把跨文化改编中最耗时、最容易遗漏的分析、影响追踪和一致性维护工作交给 AI，成为一个可控、可审计的改编搭档。**

---

# 26. 最终 Go / No-Go 判断标准

在投入更多时间之前，只需要验证四件事。

---

## Go 条件 1

Story Parser 能够在一个 8～10 场剧本上：

> 稳定抽出基本 Story State。

不要求 100% 准确。

---

## Go 条件 2

修改一个关键文化节点后：

> Dependency Resolver 确实能够比全文简单关键词搜索更准确地定位 affected scenes。

---

## Go 条件 3

使用 Story State + Commitments 的局部重写：

> 能够在一致性上明显优于“强 Prompt 一次性改写”。

---

## Go 条件 4

你们能在 Demo 中让评委 30 秒内看懂：

> **为什么这个东西不是 ChatGPT 套壳。**

---

如果这四个条件里：

- 3～4 个成立：继续冲；
- 2 个成立：继续做，但要调整方案；
- 0～1 个成立：及时换题。

---

# 27. 目前最应该做的下一步

现在不要继续扩充产品功能。

最应该立刻完成的是：

## 第一步：设计一份 8～10 场的 Demo 剧本

要求：

- 包含 3～5 个典型中国文化机制；
- 至少有 1 个文化机制影响三个以上后续场景；
- 包含明确的伏笔 / payoff；
- 普通大模型一键改写有机会发生遗漏。

## 第二步：设计 Story State JSON Schema

只保留真正会参与：

- retrieval
- propagation
- verification

的数据。

## 第三步：跑三个 baseline

```text
翻译
强 Prompt
StoryBridge Prototype
```

先验证：

> **这个技术思路真的能在一个具体故事上产生差异吗？**

如果答案是“能”，再做 UI。

如果答案是“不能”，尽早调整，避免把时间花在包装一个实际上没有差异的系统上。

---

# 28. 当前项目核心原则

整个开发过程中始终问四个问题：

> **1. 这个功能能不能直接被一个 Prompt 替代？**

> **2. Story State / Graph 有没有真正参与决策？**

> **3. 修改一个设定以后，Agent 有没有追踪 downstream impact？**

> **4. 我们有没有办法证明改编后的故事比 baseline 更一致？**

只要这四个问题一直能回答清楚，这个项目就不会轻易退化成普通 AI 写作助手。
