# StoryBridge Frontend

React 工作台已覆盖完整流程：创建与分析项目、多选文化摩擦、为每个点独立选择 A/B/C 方案、合并传播与图关系、批量应用与取消任务、Diff、统一验证、修订历史，以及目标语言剧本生成。

当前项目 ID 写入 URL 与 `localStorage`，活动 job ID 写入 `localStorage`。刷新后会恢复项目、Story State、修订、Diff、缓存方案、最新应用结果、目标语言产物，并继续轮询仍在运行的任务。用户取消或轮询中断时，前端会请求服务端取消任务。

## 启动

使用仓库声明的 Node 版本：

```bash
cd frontend
nvm use
npm ci
```

先启动后端。真实模型模式：

```bash
cd backend
uv sync --frozen --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

离线 fixtures 模式：

```bash
cd backend
uv run uvicorn app.mock_main:app --reload --port 8000
```

然后启动前端：

```bash
cd frontend
npm run dev
```

Vite 默认把 `/api` 代理到 `http://localhost:8000`。可通过 `VITE_API_TARGET` 覆盖目标；启用后端 API key 模式时，通过 `VITE_STORYBRIDGE_API_KEY` 为本地构建注入 token。不要把生产密钥提交进仓库或公开前端包。

## Mock 边界

`app.mock_main` 只替换 LLM 响应，项目创建、HTTP 路由、持久化 job、Story State、Graph、Propagation、Diff、revision 和目标产物仍走真实代码。固定 fixtures 只能验证产品链路，不能证明模型质量。

## 校验

```bash
npm run typecheck
npm run lint
npm run build
npm run e2e
```

Playwright 的浏览器用例会启动隔离的 mock API 和 Vite，使用临时项目目录，验证双文化点选择、不同方案、批量原子改编、最终目标语言剧本以及页面刷新恢复。CI 也执行同一用例。

## 代码边界

- `App.tsx`：页面状态机与流程编排。
- `components/AdaptationPanels.tsx`：方案与传播结果。
- `components/FinalArtifacts.tsx`：Diff、验证、修订与最终产物。
- `components/ProjectSwitcher.tsx`：项目恢复入口。
- `components/StoryGraphView.tsx`：图形和键盘/触屏可读的关系列表。
- `state/recovery.ts`：URL 与本地恢复标识。
- `api/`：HTTP client 与可取消 job 轮询。

大图缩放、关系筛选和自动生成 OpenAPI client 仍属于后续增强项。
