from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_config
from app.jobs import JobManager
from app.llm import build_router
from app.workflow.engine import build_default_workflow

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    router_llm = build_router()
    app.state.workflow = build_default_workflow(router_llm)
    app.state.jobs = JobManager(storage_path=config.storage.jobs_file)
    logger.info(
        "StoryBridge paths: projects=%s jobs=%s sft_logs=%s",
        config.storage.projects_dir,
        config.storage.jobs_file,
        config.logging.sft_log_dir,
    )
    try:
        yield
    finally:
        await app.state.jobs.shutdown()
        await router_llm.aclose()


app = FastAPI(title="StoryBridge", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
