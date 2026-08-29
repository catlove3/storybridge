# StoryBridge Backend

FastAPI 后端负责显式故事状态、文化摩擦分析、图传播、局部重写、验证/修复、版本提交和目标语言渲染。LLM 负责语义抽取与生成；节点引用、传播范围、版本冲突、静态验证和提交顺序由代码控制。

## 快速开始

```bash
uv sync --frozen --extra dev
cp .env.example .env
uv run pytest -q
uv run uvicorn app.main:app --reload
```

离线 mock 服务和 CLI：

```bash
uv run uvicorn app.mock_main:app --reload
uv run python -m app.cli --mock demo data/scripts/demo_v0.md --bible /tmp/bible.md
```

## LLM 配置

`.env` 只保存运行时 secret 和默认模型覆盖：

```dotenv
LLM_BASE_URL=https://provider.example/v1
LLM_API_KEY=secret
LLM_MODEL=model-name
```

`config/models.yaml` 负责 step route、超时、重试、最大输出、stream、模型价格以及安全配额。客户端复用 `httpx.AsyncClient`，支持 SSE usage、408/429/5xx 与连接错误的指数退避、jitter、`Retry-After`，并只在上游明确指出不支持时移除可选参数。

## 工作流

```text
StoryParser
  → FrictionDetector
  → AdaptationPlanner（每个已选机制分别生成 A / B / C）
  → MultiDiGraph + PropagationEngine（纯代码）
  → SceneRewriter（在同一候选状态上按选择顺序迭代）
  → strategy-aware static checks + semantic verifier
  → repair loop（最多 2 轮）
  → atomic StoryState version commit
  → TargetScriptRenderer（带 source_state_version）
```

关键不变量：

- A/B/C 标签、策略和数量严格对应；LLM 输出 ID 与输入必须一致。
- Story State 的跨对象引用、跨类型 ID 和图边端点均校验。
- 同一节点对可保留多种依赖关系、证据与置信度。
- 传播只自动采用置信度阈值内的路径，并返回路径解释与置信度。
- plan 绑定 state version；陈旧 plan/apply 返回冲突。
- batch apply 先在深拷贝候选状态上逐点完成重写，再统一验证，最后只提交一个版本；中途失败不暴露部分结果。
- 项目级锁串行化同项目工作；operation/job idempotency key 防止重复执行。

## 持久化与任务

生产运行路径使用一个 SQLite 数据库保存 project、Story State、历史快照、revision、plan、adaptation、target script 和 job。启动时按 `schema_migrations` 自动顺序升级；每个 migration 和每次版本提交分别处于 `BEGIN IMMEDIATE` 事务中，失败会回滚。数据库启用 foreign key、WAL、`synchronous=FULL`、busy timeout，并保留单调 state version。

旧版 `projects/` 和 `jobs.json` 会在启动时一次性导入；`legacy_imports` 使导入幂等，源文件不会被修改或删除。`ProjectStore` 暂时保留为迁移兼容层和隔离单元测试后端。

`JobManager` 在 SQLite 中持久化 queued/running/done/failed/cancelled、progress、取消标志和幂等映射。服务重启会把中断任务收敛为失败状态，已完成结果仍可查询；TTL 清理和项目级串行已启用。当前部署仍限定单机单 worker；多机 claim/lease 需要外部 worker 基础设施。

路径默认相对 `backend/` 解析，可用以下变量隔离运行数据：

```text
STORYBRIDGE_DATABASE_FILE
STORYBRIDGE_PROJECTS_DIR
STORYBRIDGE_JOBS_FILE
STORYBRIDGE_SFT_LOG_DIR
STORYBRIDGE_RUN_LOG_DIR
```

升级前应备份 `.sqlite3` 及其 `-wal`/`-shm` 文件，或在服务停止后使用 SQLite 的 backup 命令。应用不提供破坏性 down migration；需要回退旧版本时，应停止写入并恢复升级前备份。旧 JSON 导入源本身也始终保留，可用于核对。

## API

所有业务端点在 `/api` 下并声明 response model。完整交互契约以 `/docs` 和 `/openapi.json` 为准。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` / `/readyz` | 存活 / storage、run log、模型配置就绪检查 |
| GET | `/api/runtime-policy` | 模型端点、SFT、输入和 token 配额披露 |
| POST / GET | `/api/projects` | 创建 / 列出当前 owner 的项目 |
| GET / DELETE | `/api/projects/{id}` | 项目详情 / 删除项目及关联数据 |
| POST | `/api/projects/{id}/analyze` | 同步分析 |
| GET | `/api/projects/{id}/state` | 最新已提交 Story State |
| GET | `/api/projects/{id}/graph` | 可聚焦的多关系图 |
| GET | `/api/projects/{id}/propagate` | 确定性影响传播 |
| POST | `/api/projects/{id}/adaptations/plan` | 生成或读取当前版本的 A/B/C 方案 |
| POST | `/api/projects/{id}/adaptations/apply` | 版本化、可幂等的改编提交 |
| POST | `/api/projects/{id}/adaptations/plan-batch` | 为多个机制生成同版本方案 |
| POST | `/api/projects/{id}/adaptations/apply-batch` | 逐点迭代、统一验证并原子提交 |
| POST | `/api/projects/{id}/verify` | 验证当前状态 |
| POST / GET | `/api/projects/{id}/target-script` | 生成 / 读取版本化目标语言稿 |
| GET | `/api/projects/{id}/diff` / `revisions` / `bible` | 审计产物 |
| GET | `/api/projects/{id}/data-export` | 项目与 LLM 元数据导出 |
| POST | `/api/projects/{id}/jobs` | 提交 analyze/plan/apply/plan_batch/apply_batch/verify/render |
| GET | `/api/projects/{id}/jobs` | 项目任务历史 |
| GET / POST | `/api/jobs/{job_id}` / `cancel` | 轮询 / 取消 |

## 身份、配额与隐私

本地默认是显式单用户模式。联网部署用 JSON 环境变量启用 API key 与 owner 隔离：

```dotenv
STORYBRIDGE_API_KEYS={"token-a":"owner-a","token-b":"owner-b"}
```

客户端用 `X-API-Key`。API 对项目枚举与所有读写统一执行 owner 检查，并限制剧本长度、每 owner 活动任务数、分钟提交数和每项目 LLM token 总量。

SFT 全文日志默认关闭。启用后仍要求项目提供 `sft_opt_in`、内容来源、许可和同意说明；日志脱敏、有 retention、标为 `unreviewed`，不会自动成为 gold data。

独立的 run metadata 默认开启，但不保存 prompt/completion 正文，只保存 BLAKE2b 指纹、run ID、step、prompt version、模型、延迟、重试、token 与按配置价格计算的成本估算。上游不返回 usage 时会使用保守字符估计。项目导出与删除会包含/清除这些记录。

## Baseline 与评测

三套系统都输出相同 `TargetScript` 结构、相同目标语言、locale 和场景 ID：直接翻译、强 Prompt 全文改写、StoryBridge。可用人工 annotations 提供 affected scenes 和目标语言禁用词；没有人工标注时输出明确标为 `lexical_fallback`，不可用于强结论。

```bash
uv run python -m app.cli baseline data/scripts/demo_v0.md \
  --plans CM01:B \
  --annotations data/eval/your_annotations.json \
  --out-dir data/baselines
```

每次结果带 run manifest：输入与输出 BLAKE2b、annotation 来源、方案、目标画像、模型 route、prompt version、run ID 和可选 `STORYBRIDGE_COMMIT`。真正的多人盲评与重复真实模型实验仍需要单独执行。

## 质量检查

```bash
uv run ruff check app tests
uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=85
```

CI 还运行前端 typecheck/lint/build 与 Playwright mock E2E。测试数量不写死在文档里，以当前 CI 收集结果为准。

## 已知边界

- SQLite 存储已满足单机生产运行；多 worker/多机 job claim、lease 与故障转移仍需要外部基础设施。
- 尚未实现超长文本分块、跨块 entity merge 和 checkpoint；API 字符上限不是质量承诺。
- Naturalness、文化准确性和刻板印象风险必须由盲评补齐，当前自动指标不能替代目标文化评审者。
- OpenAPI 契约会生成前端 client/types，并由 CI 检查漂移。
