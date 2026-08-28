# StoryBridge Backend

> 面向中文短剧/网文出海的 AI 跨文化故事改编智能体后端。
> 不是翻译，是**叙事功能保持的本土化改编**：显式 Story State + 依赖传播 + 局部重写 + 双层一致性验证。

## 快速开始

```bash
cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env          # 填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

# 离线测试（无需 key，132 个测试）
python -m pytest tests/ -q

# 起服务
uvicorn app.main:app --reload   # http://localhost:8000/docs

# 一条命令跑通全闭环（离线 mock，无需 key）
python -m app.cli --mock demo data/scripts/demo_v0.md --bible /tmp/bible.md
```

## OpenAI-compatible LLM 配置

所有当前 workflow skill 默认走同一个 `general` profile，并可直接通过
`backend/.env` 切换 OpenAI-compatible 服务：

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-secret-key
LLM_MODEL=your-model-name
```

`LLM_BASE_URL` 应停在 `/chat/completions` 之前；客户端会自动拼接该路径。
密钥只从环境变量读取，不写入 YAML、代码或日志。`config/models.yaml` 仍保留
按 step 路由到其他 profile 的能力，供本地微调模型等高级用法使用。

结构化步骤会优先发送 OpenAI 风格的
`response_format={"type":"json_object"}`。如果兼容服务以 400/422 拒绝该参数，
客户端会自动移除它并重试；随后仍经过 JSON 提取、Pydantic schema 校验和原有纠错重试，
因此不支持原生 JSON mode 的服务也可以接入，但其输出稳定性仍取决于具体模型。

## 核心闭环

```
中文剧本
  ① StoryParser (LLM)        抽取人物/场景/事件/文化机制/叙事承诺/依赖边
  ② FrictionDetector (LLM)    摩擦度分级(锚定标准) + 叙事功能标签 + drop否决误抽
  ③ AdaptationPlanner (LLM)   A保留 / B功能等效替换 / C剧情重构 三方案
  ④ find_affected_scenes      ★纯代码图查询(不走LLM) 定位受影响场景+影响路径
  ⑤ SceneRewriter (LLM)       只重写受影响场景, 锁定必须保留的承诺
  ⑥ Verifier 双层验证         代码静态层(确定性) + LLM语义层(交叉验证防幻觉)
  ⑦ Repair Loop               error级issue自动修复重写(≤2轮)
```

**架构哲学**：LLM 负责语义理解与生成；**状态、依赖检索、修改范围、验证流程全部由代码控制**。
这是"为什么不是 ChatGPT 套壳"的技术根据——删掉 Story Graph，系统就退化成一次性全文改写。

## 目录结构

```text
app/
├── main.py / cli.py            # FastAPI 入口 / 命令行全闭环
├── config.py                   # 读取 config/models.yaml + .env
├── schemas/                    # 数据契约: 6类节点/9类依赖边/方案/验证报告
├── graph/                      # 图引擎: build(冲击方向语义) + query(find_affected_scenes ★)
├── skills/                     # Skill层: SkillSpec(name+schema+prompt工厂+生成参数) + 5skill注册表
├── llm/                        # router(step→model路由) / openai_compat / mock / structured(JSON重试)
├── prompts/templates.py        # Prompt模板唯一真源(微调格式与此锁定)
├── workflow/                   # engine编排+repair循环 / 六步模块 / static_checks静态验证
├── storage.py                  # JSON持久化 + rev001..N版本快照(审计) + 容错
├── jobs.py                     # 异步任务管理(长LLM调用不阻塞HTTP)
├── api/routes.py               # 16个REST端点
├── baselines/                  # A翻译/B强Prompt/C对比实验 + 指标统计
├── export/bible.py             # 逐场景Diff + Adaptation Bible导出
└── external/kunpeng.py         # 外部语料桥接(kunpeng doclevel→测试剧本)
config/models.yaml              # 模型路由配置(微调换模型只改这里)
data/scripts/                   # 语料库: demo_v0 + 5题材corpus剧本
data/external/                  # kunpeng章节样本 + idiom外部验证集
tests/                          # 132个离线测试(全走MockLLM/MockTransport, 零API成本)
```

## Skill 层与微调兼容

每个 LLM 能力 = 一个 `SkillSpec`（`app/skills/registry.py`）：
`name`(step路由名/SFT日志名) + `schema`(Pydantic输出模型) + `prompt工厂` + 生成参数(温度/重试/frequency_penalty)。

微调落地三步，**workflow 代码零改动**：

1. 语料：真实调用自动落盘 `data/sft_logs/{skill}.jsonl`（messages+completion，可直接转训练集）
2. 训练：用 `app/prompts/templates.py` 同款格式构造 SFT 数据（保证推理格式一致）
3. 部署：vLLM/Ollama 起服务 → `config/models.yaml` 的 `step_routes` 把 skill 指向新端点

```yaml
# config/models.yaml — 例: 只把改写skill换成微调模型
step_routes:
  rewrite_scene: rewriter_ft
profiles:
  rewriter_ft:
    base_url: http://localhost:8000/v1   # vLLM
    model: storybridge-rewriter-v1
```

## API 契约（前端对接）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/projects` | `{name, script, market:{market,audience,format,genre}}` |
| GET | `/api/projects` / `/{id}` | 列表 / 元信息 |
| POST | `/api/projects/{id}/analyze` | 解析+摩擦检测（慢，建议走 jobs） |
| GET | `/api/projects/{id}/state` | 完整 StoryState |
| GET | `/api/projects/{id}/graph?focus=CM01&depth=2` | `{nodes:[{id,kind,label}], edges:[...]}` |
| GET | `/api/projects/{id}/propagate?mechanism=CM01` | 受影响场景+影响类型+证据路径 |
| POST | `/api/projects/{id}/adaptations/plan` | `{culture_mechanism_id}` → A/B/C |
| POST | `/api/projects/{id}/adaptations/apply` | `{culture_mechanism_id, option_label}` |
| POST | `/api/projects/{id}/verify` | 双层一致性检查 |
| GET | `/api/projects/{id}/diff` | 逐场景 before/after/diff |
| GET | `/api/projects/{id}/bible` | 导出 Adaptation Bible |
| GET | `/api/projects/{id}/revisions` | 版本历史(审计) |
| POST | `/api/projects/{id}/jobs` | `{kind: analyze\|plan\|apply\|verify}` |
| GET | `/api/jobs/{job_id}` | 轮询任务状态/结果 |

**前端注意**：analyze/apply 串联多次 LLM 调用（30s~3min），务必走 jobs 轮询。

## CLI

```bash
python -m app.cli create <script> --name X --market "United States"
python -m app.cli analyze <pid>            # 或 propagate/plan/apply/verify/bible
python -m app.cli baseline <script> --plans CM01:B CM02:B   # 三系统对比实验
python -m app.cli --mock demo data/scripts/demo_v0.md       # 离线演示
```

## 依赖边方向约定（图引擎核心语义）

| relation | 冲击方向 | 例 |
|---|---|---|
| motivates / causes / sets_up / appears_in | **正向**（改 source → 查 target） | 机制变了 → 它激发的事件要查 |
| references / depends_on / reveals / pays_off | **反向**（改 target → 查 source） | 机制变了 → 引用它的场景要查 |
| conflicts_with | 双向 | — |

## 验证体系（双层）

| 层 | 实现 | 特点 |
|---|---|---|
| 代码静态层 | `workflow/static_checks.py`：机制名残留扫描、承诺payoff校验 | 确定性、可复现、baseline硬指标 |
| LLM语义层 | `workflow/verifier.py` + 交叉验证四条件 | 抓同义说法/动机断裂/承诺违反 |
| 防幻觉 | 证据必须含旧探针且场景实际存在旧词 | 9轮实测沉淀：捏造引用/新表述冤枉/未改编误报/复读截断 全防住 |

## 质量现状

- **132 个离线测试**全绿（MockLLM/MockTransport 驱动，零 API 成本）
- **真 LLM 验证**：10 样本 × 7 题材（都市/古言/悬疑/现实/玄幻讽刺/网文长章）analyze 全过；
  难题材 apply（冲喜/彩礼/世家）score 1.0、残留清零
- **抽取稳定性**：温度 0 + 分级锚定后，同剧本 3 次重复 analyze 机制识别完全一致
- **9 轮 bug 狩猎**修 17 个真 bug，全部有测试固化（见 git log）

## 已知边界（MVP）

- 单进程同步存储，无并发锁（演示够用；上 SQLite 只需换 storage.py）
- Naturalness 维度未自动化（比赛口径：LLM Judge 辅助 + 人工）
- 图抽取质量依赖 LLM；关键节点可手工改 `data/projects/{id}/state.json` 后再 apply
- repair 循环上限 2 轮，用尽仍报 score < 1 时需人工介入看 issues

## Baseline 实验（初评数据）

```bash
python -m app.cli baseline data/scripts/demo_v0.md --plans CM01:B --out-dir data/baselines
```

产出三系统对比表（残留引用数 / 场景覆盖率 / **无关场景改动数** / 承诺保持）。
核心差异：强 Prompt 全文重写会误伤未受影响场景（实测 9 场全改），StoryBridge 只动该动的。
