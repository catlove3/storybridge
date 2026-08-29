from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.cli import _load_default_mock_fixtures
from app.jobs import JobManager
from app.llm import MockLLMClient
from app.workflow.engine import build_default_workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    mock = MockLLMClient()
    _load_default_mock_fixtures(mock)
    # The browser demo can select any number of mechanisms. Let the mock handler
    # adapt the canned plan identity to the mechanism requested by each batch item.
    mock.responses.pop("plan_adaptation", None)
    app.state.workflow = build_default_workflow(mock)
    app.state.jobs = JobManager()
    try:
        yield
    finally:
        await app.state.jobs.shutdown()


app = FastAPI(title="StoryBridge Mock API", version="0.1.0-mock", lifespan=lifespan)
app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "llm_mode": "mock"}
