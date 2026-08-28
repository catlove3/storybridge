# StoryBridge

> 面向中文短剧 / 网文出海的 AI 跨文化故事改编系统（“智理杯”参赛项目）

StoryBridge 不只翻译文本。它先把故事抽取为显式 `StoryState`，识别文化机制及其叙事功能，再通过依赖图限定联动改写范围，执行策略感知验证与有限自动修复，最后生成带源状态版本的目标语言剧本。

## 核心闭环

```text
创建项目 → 解析故事与文化摩擦 → 选择 A/B/C 改编方案
→ 确定性依赖传播 → 局部改写 → 静态 + 语义验证 → 原子提交新版本
→ 生成目标语言剧本 → 导出 Diff / Bible / 运行元数据
```

当前实现包括项目所有权隔离、API key 模式、输入与任务配额、持久化可取消任务、项目级串行、原子 JSON 写、状态版本检查、操作幂等、目标语言产物、隐私 opt-in、仅元数据的 LLM 运行账本、前端刷新恢复和 Playwright 端到端回归。

## 快速开始

后端要求 Python 3.12，前端要求 `.nvmrc` 中的 Node 22.12.0。

```bash
cd backend
uv sync --frozen --extra dev
cp .env.example .env        # 填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
uv run pytest -q
uv run uvicorn app.main:app --reload
```

无需真实模型的本地联调：

```bash
cd backend
uv run uvicorn app.mock_main:app --reload

# 另一个终端
cd frontend
nvm use
npm ci
npm run dev
```

完整质量检查：

```bash
cd backend
uv run ruff check app tests
uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=85

cd ../frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
```

## 安全与数据边界

- 本地未配置 `STORYBRIDGE_API_KEYS` 时是明确的单用户演示模式；联网部署必须配置 token 到 owner 的 JSON 映射。
- SFT 全文采集默认关闭。只有部署开关与项目明确授权同时开启时才采集，并记录来源、许可、同意、保留期和人工质量状态。
- 常规 LLM 运行账本不保存 prompt 或 completion，只保存 BLAKE2b 指纹、模型、步骤、延迟、token 和成本估算；项目删除会同步删除这些记录。
- 默认项目模型额度为 1,000,000 tokens，可在配置中调整或关闭。

## 文档

- [`OPTIMIZATION_PLAN.md`](OPTIMIZATION_PLAN.md) — 原始严格评审、实施状态和仍未完成的边界
- [`backend/README.md`](backend/README.md) — 后端架构、配置、API、评测与运维
- [`backend/docs/HANDOFF.md`](backend/docs/HANDOFF.md) — 当前交接说明与改动约束
- [`frontend/README.md`](frontend/README.md) — 前端启动、恢复语义与 E2E

## 目录

```text
backend/    FastAPI、工作流、图引擎、持久化、评测与测试
frontend/   React 工作台、恢复状态、可访问图关系和 Playwright 测试
docs/       竞赛方案与调研笔记
```

## 仍然诚实保留的边界

- 当前持久化面向单机、单服务进程；任务可跨重启查询，但不是多 worker 分布式队列。
- 项目状态仍使用原子 JSON 版本提交，没有完成 SQLite schema/migration。
- 超长文本的分块抽取与跨块实体合并尚未实现，不能把 50 万字符的 API 上限理解为已验证的长篇质量上限。
- baseline 已统一目标语言、支持外部人工标注与 run manifest，但真正的冻结 gold set、多人盲评和多次真实模型统计仍需人工执行。
- OpenAPI 已有严格 response model；前端类型目前仍由代码审查维护，尚未自动生成。
