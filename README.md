# StoryBridge

[![CI](https://github.com/chenxizhao-cs/storybridge/actions/workflows/ci.yml/badge.svg)](https://github.com/chenxizhao-cs/storybridge/actions/workflows/ci.yml)

StoryBridge 是面向中文短剧与网文出海的跨文化故事改编系统。它把故事解析成显式状态和依赖图，识别文化机制承担的剧情、社会与情绪功能，只改写真正受影响的场景，并在提交新版本前完成一致性验证。

它解决的不是“逐句翻译”，而是一个设定变化之后，人物动机、因果链、伏笔和回收如何一起保持成立。

## 工作流

```text
中文剧本 + 目标市场
  → Story State 与文化摩擦分析
  → 同时选择一个或多个文化点
  → 为每个点选择 A 保留解释 / B 功能替换 / C 情节重构
  → 合并依赖图影响范围，在同一候选剧本上逐点迭代
  → 统一验证、有限自动修复与原子批量提交
  → 静态检查 + 语义验证
  → 原子提交 Story State 新版本
  → 生成带来源版本的目标语言剧本
```

核心特点：

- Pydantic 约束人物、场景、事件、机制、承诺与依赖边的业务不变量。
- `MultiDiGraph` 保留同一节点对之间的多种关系、证据和置信度。
- plan 绑定 state version；项目锁、原子文件替换和幂等键防止重复或交错提交。
- 批量改编允许各文化点采用不同 A/B/C 方案，共享场景按选择顺序反复改写，任一点失败均不提交部分状态。
- job 可持久化、取消、恢复轮询并进行 TTL 清理。
- verifier 按改编策略执行不同规则，并显式展示 commitment 与场景覆盖率。
- 最终目标语言稿记录 `source_state_version`，不会误用已经过期的产物。
- API 支持 owner 隔离、调用配额、数据导出/删除和默认关闭的 SFT 采集。
- React 工作台支持刷新恢复，Playwright 覆盖完整 mock 浏览器流程。

## 环境要求

| 组件 | 版本 |
|---|---|
| Python | 3.12.x |
| Node.js | 22.12.0（见 `frontend/.nvmrc`） |
| Python 包管理 | 推荐 uv；同时提供标准 `requirements.txt` |
| 浏览器测试 | Playwright Chromium |

## 最快启动：离线 Mock

Mock 模式不需要模型密钥。它只替换 LLM 返回值，HTTP、job、storage、Graph、Propagation、Diff、revision 和目标语言产物仍走真实代码。

终端一：

```bash
cd backend
uv sync --frozen --extra dev
uv run uvicorn app.mock_main:app --host 127.0.0.1 --port 8000
```

终端二：

```bash
cd frontend
nvm use
npm ci
npm run dev
```

浏览器访问 Vite 输出的地址。固定 fixtures 只能用于验证产品链路，不能作为模型质量证据。

## 使用真实模型

```bash
cd backend
cp .env.example .env
```

在 `.env` 中配置：

```dotenv
LLM_BASE_URL=https://provider.example/v1
LLM_API_KEY=replace-me
LLM_MODEL=model-name
```

然后启动：

```bash
uv sync --frozen --extra dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

OpenAPI 文档位于 `http://127.0.0.1:8000/docs`，就绪检查位于 `/readyz`。

## 不使用 uv 的安装方式

根目录的 `requirements.txt` 是从 `backend/uv.lock` 导出的精确版本兼容清单，包含运行与测试依赖：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd backend
python -m pytest -q
```

`pyproject.toml` 和 `uv.lock` 是依赖真源。修改依赖后重新生成兼容清单：

```bash
cd backend
uv lock
uv export --frozen --extra dev --no-hashes --no-annotate --no-header \
  --output-file ../requirements.txt
```

CI 会检查 `requirements.txt` 与 lock 是否一致，避免两套安装说明漂移。

## 完整质量检查

后端：

```bash
cd backend
uv sync --frozen --extra dev
uv run ruff check app tests
uv run pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=85
```

前端：

```bash
cd frontend
nvm use
npm ci
npm run typecheck
npm run lint
npm run build
```

浏览器流程：

```bash
cd frontend
npx playwright install chromium
npm run e2e
```

E2E 会自行启动隔离的 mock API 与 Vite，等待真实 HTTP 健康检查，通过后执行创建、分析、刷新恢复、多点选择、逐点方案、批量传播与改写、统一验证和目标语言渲染，并在结束时清理临时数据与子进程。

## 配置与数据安全

- 未配置 `STORYBRIDGE_API_KEYS` 时是单用户本地演示模式；联网部署应配置 token 到 owner 的 JSON 映射。
- SFT 全文采集默认关闭，必须同时开启部署开关并取得项目级来源、许可和同意。
- 常规 LLM 账本不保存 prompt 或 completion，只保存 BLAKE2b 指纹、模型、步骤、耗时、token 和成本估算。
- 默认每项目模型额度为 1,000,000 tokens，可在 `backend/config/models.yaml` 调整。
- 项目删除会同步清理项目状态、job、SFT 样本与运行元数据。

运行数据可通过以下环境变量放到独立持久卷：

```text
STORYBRIDGE_PROJECTS_DIR
STORYBRIDGE_JOBS_FILE
STORYBRIDGE_SFT_LOG_DIR
STORYBRIDGE_RUN_LOG_DIR
```

## 仓库结构

```text
backend/                 FastAPI、工作流、图引擎、存储、评测与测试
frontend/                React 工作台与 Playwright E2E
.github/workflows/       后端、前端和浏览器 CI
requirements.txt         从 uv.lock 导出的精确兼容依赖
OPTIMIZATION_PLAN.md      严格评审、实施记录与后续边界
```

更多资料：

- [后端说明](backend/README.md)
- [前端说明](frontend/README.md)
- [交接文档](backend/docs/HANDOFF.md)
- [优化方案与实施状态](OPTIMIZATION_PLAN.md)

## 当前边界

- 存储和任务系统面向单机单进程，不是多 worker 分布式队列。
- 尚未完成 SQLite migration 和超长文本跨块实体合并。
- baseline 已支持统一目标语言、外部 annotations 和 run manifest，但正式结论仍需要冻结 gold set、多位评审盲评和重复真实模型实验。
- OpenAPI response model 已严格化，前端 client/types 尚未自动生成。
