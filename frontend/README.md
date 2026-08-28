# StoryBridge Frontend

第一阶段前端 Demo：输入剧本后创建项目，通过 `analyze` job 轮询等待分析完成，读取真实 `StoryState`，并展示 `CultureMechanism` 的文化摩擦等级与 Narrative Functions。

## 启动

先启动真实后端（需要配置真实 LLM key）：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

或启动仓库 fixtures 驱动的离线 mock 后端：

```bash
cd backend
source .venv/bin/activate
uvicorn app.mock_main:app --reload --port 8000
```

再启动前端：

```bash
cd frontend
nvm use                    # Node 22.12.0；Vite 8 至少需要 Node 20.19+
npm install
npm run dev
```

Vite 会把浏览器发往 `/api` 的请求代理到 `http://localhost:8000`，因此这一阶段不需要改 FastAPI CORS。

## Mock 边界

`app.mock_main` 复用仓库 `tests/fixtures` 和 `MockLLMClient`。在该模式下，LLM 的 `parse_story` 与 `detect_frictions` 结果是固定 fixtures，不能用于判断模型质量；但项目创建、FastAPI 路由、job 提交与轮询、JSON 持久化、`GET /state` 和前端渲染均走真实路径。前端本身不包含硬编码分析结果。

## 校验

```bash
npm run typecheck
npm run build
```
