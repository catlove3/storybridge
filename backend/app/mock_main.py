from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.cli import _load_default_mock_fixtures
from app.jobs import JobManager
from app.llm import MockLLMClient
from app.workflow.engine import build_default_workflow

app = FastAPI(title="StoryBridge Mock API", version="0.1.0-mock")
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    mock = MockLLMClient()
    _load_default_mock_fixtures(mock)
    app.state.workflow = build_default_workflow(mock)
    app.state.jobs = JobManager()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "llm_mode": "mock"}
