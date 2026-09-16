# StoryBridge Frontend

React 页面采用“输入故事 → 选择方案 → 查看结果”流程，支持动态示例目录、可编辑草稿、多文化点选择、后台改写与检查、完整目标语言稿，以及复制和下载。手机为单列布局，图谱、对比和检查详情按需展开。

初始化匿名会话后再读取故事和运行政策。草稿、选择和任务链按访客隔离保存；提交前保存幂等键，刷新恢复当前阶段。断网或切后台只暂停查询；只有点击“取消”才取消后台任务。二维码只包含首页地址，不带项目或身份。

分享启动及现场验收说明见 [手机扫码体验](../docs/SHARING.md)。

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
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run e2e
```

Playwright 的浏览器用例会启动隔离的 mock API 和 Vite，使用临时项目目录，验证双文化点选择、不同方案、批量原子改编、最终目标语言剧本以及页面刷新恢复。CI 也执行同一用例。

## OpenAPI 客户端

`src/api/generated/schema.ts` 和 `openapi.json` 由 FastAPI 应用生成，业务代码通过 `openapi-fetch` 获得编译期校验。后端路由或响应模型变更后运行：

```bash
npm run openapi:generate
```

不要手工编辑生成文件。`npm run openapi:check` 会重新生成并与运行前的文件内容比较，CI 用它阻止前后端契约漂移。

## 代码边界

- `App.tsx`：页面状态机与流程编排。
- `components/AdaptationPanels.tsx`：方案与传播结果。
- `components/ExperienceDialogs.tsx`：示例选择、替换确认、二维码与复制下载。
- `components/StoryGraphView.tsx`：图形和键盘/触屏可读的关系列表。
- `state/recovery.ts`：访客隔离的草稿、步骤状态与幂等请求。
- `api/`：OpenAPI 类型安全 HTTP client、生成 schema 与断网与后台恢复的任务轮询。

大图缩放和关系筛选仍属于后续增强项。
