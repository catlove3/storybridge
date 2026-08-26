# “智理杯”智能体大赛：StoryBridge 具体实现方案与分工

> 目标：把“跨文化故事改编智能体”从 idea 落到一个两个低年级 CS 学生能够在比赛周期内真正做出来、跑通、演示清楚的 MVP。

## 1. 总体判断

推荐采用：

> **自己写轻量前端 + Python 后端 + LLM API 调用 + 自己掌控 Workflow**

而不是一开始就使用复杂的多智能体框架。

这个项目真正有价值的地方不是“用了几个 Agent”，而是：

> **自己维护 Story State，并且让 Story Graph 真正参与后续的检索、依赖传播、局部修改和验证。**

核心目标不是做“大而全的 AI 短剧平台”，而是把下面这一条链路跑通：

```text
Story State
    ↓
文化摩擦点识别
    ↓
改编方案规划
    ↓
Dependency Propagation
    ↓
局部重写
    ↓
Consistency Verification
```

## 2. 推荐技术架构

```text
┌─────────────────────────────┐
│          React 前端          │
│                             │
│ 剧本输入 / 文化点 / Graph    │
│ 改编方案 / Diff / 验证结果   │
└──────────────┬──────────────┘
               │ HTTP JSON
               ↓
┌─────────────────────────────┐
│       FastAPI Python 后端    │
│                             │
│       Workflow Manager      │
│              │              │
│    ┌─────────┴──────────┐   │
│    ↓                    ↓   │
│ LLM Service        Story State│
│    │                + Graph  │
│    ↓                    │    │
│ analyze/plan/       dependency│
│ rewrite/verify        query   │
└──────────────┬──────────────┘
               │
               ↓
           LLM API
```

## 3. 推荐技术栈

| 部分 | 推荐 |
|---|---|
| 前端 | React + Vite + TypeScript |
| UI | Tailwind，可选 |
| Graph 可视化 | React Flow / 简单图组件 |
| 后端 | Python + FastAPI |
| 数据模型 | Pydantic |
| Story Graph | NetworkX 或自己写 adjacency list |
| 状态存储 | 第一版 JSON，后续再考虑 SQLite |
| LLM | 只接一家 API |
| Agent 框架 | 第一版不用 |
| Git | 一个 GitHub Repo，前后端 Monorepo |

第一版不建议上 Neo4j、LangGraph、CrewAI、向量数据库、Kafka、微服务、Kubernetes、复杂 RAG 框架。

原则：

> **能用一个 Python 数据结构解决的问题，就先不要引入基础设施。**

## 4. 核心 Workflow

```text
① Parse Story
       ↓
② Build Story State
       ↓
③ Detect Culture Frictions
       ↓
④ Plan Adaptation
       ↓
⑤ Query Affected Scenes
       ↓
⑥ Rewrite Affected Scenes
       ↓
⑦ Verify & Repair
```

最重要的设计原则：

> **不是每一步都交给 LLM。**

## 5. 哪些工作交给 LLM，哪些必须自己写

| 步骤 | 谁做 | 原因 |
|---|---|---|
| 理解人物 / 事件 | LLM | 语义理解 |
| 找文化摩擦点 | LLM | 文化语义理解 |
| 分析叙事功能 | LLM | 推理 |
| 生成 A/B/C 改编方案 | LLM | 创作 |
| 建立数据结构 | 自己写代码 | explicit state |
| 保存 Story State | 自己写代码 | explicit state |
| 查询 affected scenes | 自己写代码 | dependency propagation |
| 决定给 LLM 哪些 Scene | 自己写代码 | 核心创新 |
| 重写 Scene | LLM | 文本生成 |
| 检查旧元素残留 | 代码 + LLM | verification |
| 检查 Narrative Commitment | LLM + 结构化数据 | verification |
| 保存修改历史 | 自己写代码 | auditability |

这张表直接对应：

> **为什么不是 ChatGPT Wrapper？**

普通 ChatGPT：

```text
whole_story
+
instruction
↓
LLM
↓
whole_story'
```

StoryBridge：

```text
LLM 负责语义理解与生成

但是：

状态维护
依赖检索
修改范围
版本管理
验证流程

由系统控制
```

## 6. 第一件事不是写前端，而是定义 Story State

第一版只需要六类对象：

```text
Character
Scene
Event
CultureMechanism
Commitment
Dependency
```

后端整体状态可以先存成：

```json
{
  "characters": [],
  "scenes": [],
  "events": [],
  "culture_mechanisms": [],
  "commitments": [],
  "dependencies": []
}
```

## 7. 核心数据结构示例

### 7.1 Scene

```json
{
  "id": "S03",
  "summary": "女方父亲要求男主必须有编制，否则不同意结婚",
  "characters": ["C01", "C03"],
  "text": "……"
}
```

### 7.2 CultureMechanism

```json
{
  "id": "CM01",
  "name": "编制",
  "scenes": ["S01", "S03", "S07"],
  "friction": "high",
  "functions": {
    "plot": ["conflict", "setup"],
    "social": ["status", "economic_security"],
    "emotional": ["humiliation"]
  }
}
```

### 7.3 Narrative Commitment

```json
{
  "id": "NC01",
  "description": "女方家庭认为男主社会地位低且前途不稳定",
  "established_at": "S02",
  "must_preserve": true
}
```

```json
{
  "id": "NC02",
  "description": "结局必须通过男主事业成功完成身份反转",
  "established_at": "S01",
  "must_preserve": true
}
```

## 8. Dependency 才是 Story Graph 的核心

Story Graph 不能只是给用户看的漂亮关系图。

```text
[CM01 编制]
      │
      ├── motivates ──→ [Event03 女方父亲反对]
      │
      ├── referenced_by ──→ [S03]
      │
      ├── referenced_by ──→ [S06]
      │
      └── sets_up ──→ [Event08 身份反转]
```

第一版可以直接用 NetworkX：

```python
graph = nx.DiGraph()

graph.add_edge(
    "CM01",
    "S03",
    relation="referenced_by"
)
```

## 9. 整个项目最重要的函数之一

```python
find_affected_scenes(changed_node)
```

例如用户决定：

> 把“编制”重新设计为北美语境中的职业稳定性 / 社会地位机制。

系统根据 Graph 查询并输出：

```text
Affected Scenes

S02  direct reference
S03  character motivation
S04  causal dependency
S08  payoff dependency
```

关键要求：

> **Affected Scenes 不能每次重新问 LLM：“哪些场景受影响？”**

而应该是真正的程序查询：

```python
affected = graph_query(...)
```

## 10. Rewrite 也不要整篇重写

假设 Graph 判断：

```text
Affected:
S02
S03
S06
S08
```

只把相关信息给 LLM：

```text
Target adaptation
+ S02 / S03 / S06 / S08
+ relevant characters
+ relevant commitments
+ nearby context
```

Prompt 中明确：

```text
Current adaptation:
“编制”机制已替换为……

Must preserve:
NC01
NC02
NC04

Rewrite:
S03

Do not modify unrelated facts.
```

这就是：

> **Graph-driven generation**

而不是：

> Graph decoration + whole-story prompt

## 11. Verification 是第二个核心

Rewrite 后不能直接结束。

```text
Verification

[✓] 原“编制”引用已全部删除
[✓] 女方父亲反对男主的动机仍成立
[✓] S08 身份反转仍成立
[!] S06 仍然出现“事业单位”
```

系统继续：

```text
Need repair:
S06
```

形成：

```text
Plan
 ↓
Act
 ↓
Verify
 ↓
有问题？
 ├─ No → Finish
 └─ Yes → Repair
             ↓
          Verify
```

## 12. 推荐后端 API

```text
POST /projects
```

输入：

```text
script
target_market
```

---

```text
POST /projects/{id}/analyze
```

执行 Story Parser + Culture Friction Detection。

---

```text
GET /projects/{id}/state
```

返回 Characters、Scenes、CultureMechanisms、Commitments、Graph。

---

```text
POST /projects/{id}/adaptations/plan
```

输入：

```text
culture_mechanism_id
```

输出 A / B / C 三种方案。

---

```text
POST /projects/{id}/adaptations/apply
```

输入：

```text
culture_mechanism_id
chosen_plan
```

内部：

```text
Graph Query
→ Affected Scenes
→ Rewrite
→ Update State
```

---

```text
POST /projects/{id}/verify
```

返回：

```text
issues
consistency score
commitment status
```

## 13. 前端只需要 5 个主要页面 / 区域

### Screen 1：输入剧本

左侧：

```text
Paste Chinese Script
```

右侧：

```text
Target Market

United States
18–30
Vertical Drama
Romance / Revenge
```

### Screen 2：Culture Friction Map

```text
Culture Frictions

🔴 编制       High
🔴 彩礼       High
🟠 相亲       Medium
🟢 春节       Low
```

### Screen 3：Adaptation Plan

```text
Original:
编制

Narrative Functions:
Status
Economic Security
Family Approval
Humiliation
```

下面：

```text
A Preserve
B Functional Replacement
C Plot Reconstruction
```

### Screen 4：Impact Propagation

```text
Changing “编制” affects:

S02 ─ direct reference
S03 ─ motivation
S05 ─ causal dependency
S08 ─ payoff
```

Graph 中对应节点同时高亮。

### Screen 5：Before / After + Verify

```text
Narrative Commitments

✓ NC01 preserved
✓ NC02 preserved
⚠ NC03 needs review
```

## 14. 两个人推荐分工

| Backend / Agent Owner | Frontend / Product Owner |
|---|---|
| StoryState Schema | React 页面 |
| LLM API | API 调用 |
| Structured Output | Graph 展示 |
| Graph Construction | Culture Friction UI |
| Dependency Query | Adaptation 选择 UI |
| Rewrite Workflow | Diff UI |
| Verifier | Demo UX |
| 后端测试 | 前端联调 |
| Baseline 实验 | Demo 演示流程 |

三件事必须共同做：

1. Story Schema
2. Demo 剧本
3. Prompt

## 15. 推荐开发时间表

当前日期：2026 年 8 月 25 日。建议把 **8 月 31 日作为代码冻结线**。

### 8 月 25 日晚上

```text
1. 建 GitHub Repo
2. 定 StoryState Schema
3. 写一篇 8～10 Scene Demo 剧本
```

### 8 月 26 日

Backend 跑通：

```text
script
 ↓
LLM
 ↓
StoryState JSON
```

Frontend 做五个静态页面骨架。

### 8 月 27 日

重点完成：

```text
CultureMechanism
+
Dependency Graph
```

第一个生死线：

```python
find_affected_scenes("CM01")
```

必须真正跑起来。

### 8 月 28 日

跑完整：

```text
plan
→ user choose
→ query graph
→ rewrite affected scenes
```

### 8 月 29 日

增加：

```text
verification
+
repair loop
```

### 8 月 30 日

前后端正式合并，重点做：

```text
Graph highlight
Before / After
Diff
Commitment result
```

### 8 月 31 日

停止加新功能，开始跑 Baseline：

```text
编制
彩礼
985
户口
相亲
```

比较：

```text
Strong Prompt LLM
vs
StoryBridge
```

重点记录：

```text
Affected-scene Recall
Consistency Violations
Commitment Preservation
```

## 16. 不需要真正 Multi-Agent

第一版完全可以只是：

```python
class StoryBridgeWorkflow:

    def analyze(self):
        ...

    def detect_frictions(self):
        ...

    def plan_adaptation(self):
        ...

    def find_affected_scenes(self):
        ...

    def rewrite(self):
        ...

    def verify(self):
        ...
```

后面真的发现 Verifier 有必要独立成 Agent，再拆。

## 17. 最需要避免的坑

Vibe Coding 很容易生成：

```text
agent/
├── story_agent.py
├── culture_agent.py
├── translation_agent.py
├── critic_agent.py
├── director_agent.py
├── graph_agent.py
└── supervisor_agent.py
```

看起来很高级，但要先问：

> **哪个模块保存唯一可信的 Story State？**

以及：

> **哪个函数在某个 cultural node 改变后，通过明确依赖关系计算 affected scenes？**

如果回答不出来，这些 Agent 很可能只是不同 Prompt 文件。

## 18. 第一版 MVP 成功标准

只要稳定跑通下面这一条路径，就认为项目成立：

```text
上传一个 8 场中文短剧
        ↓
系统识别“编制”为高风险文化机制
        ↓
用户点击“编制”
        ↓
系统解释：
社会地位 + 职业稳定 + 家庭认可
        ↓
Agent 给出三个北美改编方案
        ↓
用户选择一个
        ↓
Story Graph 自动指出：
S2 / S4 / S7 / S8 受到影响
        ↓
系统只重写这四个 Scene
        ↓
Verifier 检测到：
S7 仍引用旧设定
        ↓
Agent 修复 S7
        ↓
最终：
4 / 4 Narrative Commitments Preserved
```

## 19. 核心结论

“自己写前后端 + API 调用 + workflow”的方向是对的。

真正应该优先自己写的是：

> **State 和 Workflow，而不是 Agent 人设。**

整个项目最重要的三个技术对象是：

```text
1. Story State
2. Dependency Graph
3. Verify / Repair Loop
```

LLM 负责：

```text
理解
规划
生成
语义验证
```

你们自己的程序负责：

```text
状态
范围
依赖
流程
记录
```

这才是 StoryBridge 能回答：

> **“为什么不用 ChatGPT 直接做？”**

的真正技术基础。

## 20. 下一步行动

现在最应该立即确定三样东西：

1. **StoryState 的 Pydantic 数据结构**
2. **后端 Repo 目录结构**
3. **第一版 8～10 Scene Demo 剧本**

这三项完成后，两个人就可以正式分头开发。
