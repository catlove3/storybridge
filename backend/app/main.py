from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.jobs import JobManager
from app.llm import build_router
from app.workflow.engine import build_default_workflow

app = FastAPI(title="StoryBridge", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    router_llm = build_router()
    app.state.workflow = build_default_workflow(router_llm)
    app.state.jobs = JobManager()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
