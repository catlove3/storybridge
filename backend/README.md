# StoryBridge Backend

跨文化故事改编智能体的后端：Story State + Dependency Graph + Propagation + 局部重写 + Verify/Repair 闭环。

## 快速开始

```bash
cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # 填入 API key
uvicorn app.main:app --reload
```

跑测试（离线，不需要 LLM key）：

```bash
python -m pytest tests/ -q
```

## 架构总览

```text
script → StoryParser(parse_story) → FrictionDetector(detect_frictions)
       → AdaptationPlanner(plan_adaptation) → 用户选方案
       → PropagationEngine.find_affected_scenes()   [纯图查询，不走 LLM]
       → SceneRewriter(rewrite_scene, 仅受影响场景) 
       → Verifier(verify_consistency) → 有 error 级 issue 自动修复循环
```

核心原则：**状态、依赖检索、修改范围、验证流程由代码控制；LLM 只负责语义理解与生成。**

## Skill 层（v2 架构）

每个 LLM 能力是一个 **SkillSpec**（`app/skills/registry.py`）：prompt 模板 + 输出 schema +
生成参数（max_tokens/temperature/重试次数）+ step 路由名，集中声明、独立演进。

```python
from app.skills import get_skill
state = await get_skill("parse_story").run(client, script_text=..., target_market=...)
```

- **微调落地路径**：SFT 语料按 skill 名分文件落盘（`data/sft_logs/{skill}.jsonl`），
  `config/models.yaml` 的 `step_routes` 把该 skill 指向微调模型端点即可，workflow 代码零改动
- **新增能力**：定义 SkillSpec → 注册 → workflow 注入，不动 generate_structured 逻辑
- 5 个内置 skill：parse_story / detect_frictions / plan_adaptation / rewrite_scene / verify_consistency

## 微调模型兼容设计

1. **模型路由** `config/models.yaml`：每个 skill 独立绑定模型 profile。
   将来某个 skill 换微调模型，只改 yaml：

   ```yaml
   step_routes:
     rewrite_scene: rewriter_ft   # 指向 vLLM 部署的微调模型
   profiles:
     rewriter_ft:
       provider: openai_compat
       base_url: http://localhost:8000/v1   # vLLM / Ollama / sglang
       model: storybridge-rewriter-v1
   ```

2. **统一 OpenAI 兼容协议**：`app/llm/openai_compat.py` 同时适配 DeepSeek/Qwen/OpenAI 及本地 vLLM。

3. **SFT 语料自动积累**：所有真实 LLM 调用自动落盘到 `data/sft_logs/{step}.jsonl`
   （messages + completion），可直接转微调训练集。训练时请复用
   `app/prompts/templates.py` 的模板格式，保证 SFT 与推理格式一致。

4. **结构化输出兜底**：小模型 JSON 不稳时，`structured.py` 会做 JSON 提取 +
   Pydantic 校验 + 带 error feedback 的自动重试；不依赖 provider 的 json_mode。

## API 契约（前端对接）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/projects` | body: `{name, script, market:{market,audience,format,genre}}` |
| GET | `/api/projects` | 项目列表 |
| GET | `/api/projects/{id}` | 元信息（含 analyzed 状态） |
| POST | `/api/projects/{id}/analyze` | 解析剧本+摩擦点检测，耗时较长 |
| GET | `/api/projects/{id}/state` | 完整 StoryState JSON |
| GET | `/api/projects/{id}/graph?focus=CM01&depth=2` | 图数据 `{nodes:[{id,kind,label}], edges:[{source,target,relation,evidence}]}` |
| GET | `/api/projects/{id}/propagate?mechanism=CM01` | 受影响场景预览 `{affected_scenes:[{scene_id,impact_kinds,reason_path,evidence}]}` |
| POST | `/api/projects/{id}/adaptations/plan` | body:`{culture_mechanism_id}` → A/B/C 方案 |
| POST | `/api/projects/{id}/adaptations/apply` | body:`{culture_mechanism_id, option_label}` → 改写+自动验证修复 |
| POST | `/api/projects/{id}/verify` | 手动触发一致性检查（LLM + 代码静态层） |
| GET | `/api/projects/{id}/revisions` | 修改历史（审计用） |
| GET | `/api/projects/{id}/diff` | 与初始版本的逐场景 before/after/diff |
| GET | `/api/projects/{id}/bible` | 导出 Adaptation Bible (markdown) |
| POST | `/api/projects/{id}/jobs` | 异步任务 `{kind: analyze\|plan\|apply\|verify, ...}` |
| GET | `/api/jobs/{job_id}` | 轮询任务状态与结果 |
| GET | `/api/projects/{id}/jobs` | 项目任务列表 |

**前端注意**：analyze/apply 串联多次 LLM 调用（10s~2min），建议走 jobs 接口轮询，或 fetch 设长超时。

## CLI（先于 UI 的命令行闭环）

```bash
# 离线 mock 全链路 demo（无需 API key）
python -m app.cli --mock demo data/scripts/demo_v0.md --bible out/bible.md

# 真实 LLM
python -m app.cli create data/scripts/demo_v0.md --name demo --market "United States"
python -m app.cli analyze <project_id>
python -m app.cli propagate <project_id> CM01     # 预览受影响场景
python -m app.cli plan <project_id> CM01
python -m app.cli apply <project_id> CM01 B
python -m app.cli verify <project_id>
python -m app.cli bible <project_id> out/bible.md

# Baseline 对比实验（A 翻译 / B 强Prompt / C StoryBridge）
python -m app.cli baseline data/scripts/demo_v0.md --plans CM01:B CM02:B --out-dir data/baselines
```

## Baseline 实验模块（初评对比数据）

`app/baselines/` 对三个系统跑**同一套代码级评测**，结果落盘 markdown + json：

| 指标 | A 直接翻译 | B 强Prompt | C StoryBridge |
|---|---|---|---|
| 残留引用数 | 高（只翻译不改编） | 中（全文一次改写易漏） | 目标：0 |
| 场景覆盖率 | N/A | 对比项 | 图查询 100% |
| 承诺保持 | N/A | 对比项 | Verifier 可查 |

- 残留检测：改编稿中重新检索机制名 + surface_text 探针（确定性，可复现）
- 场景覆盖率：以 StoryBridge 图查询结果为 ground truth，diff 原文/改编稿
- 承诺保持：复用 Verifier 的 commitment_checks

## 一致性验证：双层设计

1. **代码静态层**（`workflow/static_checks.py`，确定性）：机制名/surface_text 残留检测、
   承诺 payoff 场景缺失检测——不依赖 LLM，结果可复现，是 baseline 对比的硬指标
2. **LLM 语义层**（`workflow/verifier.py`）：事实冲突、动机断裂、语义级残留、承诺违反
3. 两层结果自动合并去重后计分

## 目录结构

```text
app/
├── config.py            # 配置加载 (config/models.yaml + .env)
├── schemas/             # Pydantic: 6 类节点 / 9 类依赖边 / 方案 / 验证报告
├── graph/
│   ├── build.py         # StoryGraph (NetworkX)，冲击方向语义在此定义
│   └── query.py         # find_affected_scenes —— 全项目最核心函数
├── llm/
│   ├── base.py          # LLMClient 协议
│   ├── openai_compat.py # OpenAI 兼容客户端
│   ├── mock.py          # MockLLMClient（离线测试）
│   ├── router.py        # step→model 路由 + SFT 日志
│   └── structured.py    # JSON 提取/校验/重试
├── prompts/templates.py # 5 个 step 的 prompt 模板（微调时保持一致！）
├── workflow/            # Parser / Detector / Planner / Rewriter / Verifier + 编排器
│   └── static_checks.py # 代码级确定性检查（残留/承诺覆盖）
├── baselines/           # A翻译 / B强Prompt / C StoryBridge 对比实验
├── export/bible.py      # Diff + Adaptation Bible 导出
├── jobs.py              # 异步任务管理（长 LLM 调用不阻塞 HTTP）
├── cli.py               # 命令行全闭环
├── storage.py           # 项目持久化 + 版本快照 (data/projects/)
└── api/routes.py        # FastAPI 路由
tests/                   # 28 个离线测试（Mock LLM 全链路）
data/scripts/demo_v0.md  # 8 场 Demo 剧本 v0（编制→彩礼→分手→反转依赖链）
```

## 依赖边冲击方向约定

| relation | 冲击方向 | 例 |
|---|---|---|
| motivates / causes / sets_up / appears_in | 正向（改 source → 查 target） | 编制 changed → 提出反对的事件要查 |
| references / depends_on / reveals / pays_off | 反向（改 target → 查 source） | 场景引用了彩礼 → 彩礼 changed 时该场景要查 |
| conflicts_with | 双向 | |

## 已知边界（MVP）

- 单进程同步存储，无并发锁；演示场景够用
- verify 的 Naturalness 维度未实现（比赛口径：LLM Judge 辅助 + 人工）
- Graph 抽取质量依赖 LLM，关键节点可在 state.json 中人工修正后重新 apply
