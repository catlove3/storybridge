# StoryBridge 交接文档

> 更新：2026-08-29。本文只描述当前实现；历史问题与取舍见仓库根目录 `OPTIMIZATION_PLAN.md`。

## 接手前先跑

```bash
cd backend
uv sync --frozen --extra dev
uv run ruff check app tests
uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=85

cd ../frontend
nvm use
npm ci
npm run typecheck
npm run lint
npm run build
npm run e2e
```

## 当前系统边界

- FastAPI lifespan 统一创建/关闭共享 LLM client、workflow 和持久化 JobManager。
- `StoryBridgeWorkflow` 与 `JobManager` 都按 project 串行，避免同项目写入竞态；不同项目可并行。
- `ProjectStore` 使用版本化、原子 JSON 提交，`state.json` 是最后提交标记。
- Job 可持久化、取消、TTL 清理和幂等重试，但服务仍须单 worker。
- 前端可从 URL/localStorage 恢复项目和活动 job，完整 E2E 使用隔离 mock 服务。
- 默认不采集 SFT 全文；run metadata 不含正文，可导出、删除并用于 token 配额。

## 改动热力图

| 变更 | 风险 | 必做检查 |
|---|---:|---|
| prompt 或 skill 参数 | 中 | structured dirty-output、workflow E2E、真实模型 smoke |
| schema 字段或 ID 规则 | 高 | fixtures、schema invariant、graph、旧数据迁移 |
| 图边方向/阈值 | 极高 | multi-relation、传播路径、低置信覆盖测试 |
| save/commit 顺序 | 极高 | fault injection、revision/version、并发与幂等测试 |
| job 状态 | 高 | restart、cancel、TTL、API 与前端恢复 E2E |
| API contract | 高 | response model、OpenAPI、前端 types/client、Playwright |
| SFT/run logger | 高 | opt-in、正文泄露、retention、export/delete、budget |

## 不要回退的设计决定

1. plan 必须绑定 state version，apply 必须在候选副本验证完成后再提交。
2. 同节点对的多种依赖关系必须全部保留，不能退回普通 `DiGraph`。
3. preserve、functional replacement、plot reconstruction 使用不同静态检查规则。
4. must-preserve commitment 的 `needs_review` 不能显示为绿色通过；UI 必须同时展示 coverage。
5. 可选 provider 参数只能在错误正文明确点名不支持时删除，不能逐个盲删掩盖真实 400。
6. 读路径不得创建目录；项目 ID 与 owner 检查必须覆盖每个项目/job 端点。
7. SFT 必须同时满足部署开关和项目明确授权，且未经人工验收的样本只能标为 `unreviewed`。
8. 常规运行日志不得保存完整剧本/prompt/completion；只记录 BLAKE2b 指纹和运行元数据。

## 前后端联调

推荐离线模式：

```bash
cd backend
uv run uvicorn app.mock_main:app --port 8000

cd ../frontend
npm run dev
```

mock 只替换 LLM 输出，HTTP、job、storage、Graph、Propagation、Diff、revision 与 target artifact 都是真实实现。固定 fixtures 不可用于模型效果结论。

长任务统一走 `POST /api/projects/{id}/jobs`。提交时传稳定的 `idempotency_key`；轮询 `GET /api/jobs/{job_id}`，刷新后可从 `GET /api/projects/{id}/jobs` 恢复。用户终止时调用 `/cancel`，不要只停浏览器轮询。

## 数据与部署

- 联网部署设置 `STORYBRIDGE_API_KEYS`，并确保只使用一个 Uvicorn worker。
- 用四个 `STORYBRIDGE_*_DIR/FILE` 变量把 project、job、SFT、run metadata 放到持久卷。
- 模型价格在 profile 的 `input_cost_per_million_usd` / `output_cost_per_million_usd` 中配置；未配置时成本显示为 0，但 token 仍统计。
- `max_project_llm_tokens: 0` 表示关闭额度；默认启用硬停止，达到上限后的新 LLM 操作返回 429。
- 删除项目会删除项目目录、任务、SFT 样本和 run metadata。导出先于删除由调用方负责。

## 仍需后续处理

1. SQLite schema、migration 与多进程 job claim。
2. 场景分块解析、跨块实体归一、承诺二次链接和 checkpoint。
3. 由 OpenAPI 自动生成前端 client/types。
4. 冻结人工 gold set、多人盲评、重复运行和统计报告。
5. 大图缩放/筛选以及更细粒度的前端 reducer/page 拆分。

这些不是当前代码已经完成的能力，答辩和部署说明不要超范围承诺。
