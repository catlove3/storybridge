from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from app.api.routes import router
from app.api.security import ApiUsageGuard
from app.config import api_key_owners, get_config
from app.jobs import JobManager
from app.llm import build_router
from app.workflow.engine import build_default_workflow

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    configured_api_keys = api_key_owners(config)
    router_llm = build_router()
    app.state.workflow = build_default_workflow(router_llm)
    app.state.jobs = JobManager(storage_path=config.storage.jobs_file)
    app.state.usage_guard = ApiUsageGuard()
    logger.info(
        "StoryBridge paths: projects=%s jobs=%s sft_logs=%s run_logs=%s",
        config.storage.projects_dir,
        config.storage.jobs_file,
        config.logging.sft_log_dir,
        config.logging.run_log_dir,
    )
    logger.info(
        "StoryBridge security mode=%s sft_collection=%s",
        "api-key" if configured_api_keys else "local-single-user",
        "enabled-with-project-opt-in" if config.logging.sft_log_enabled else "disabled",
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


@app.get("/readyz")
async def readyz(response: Response) -> dict:
    config = get_config()
    checks = {
        "projects_storage": config.storage.projects_dir.is_dir()
        and os.access(config.storage.projects_dir, os.R_OK | os.W_OK),
        "jobs_storage": config.storage.jobs_file.parent.is_dir()
        and os.access(config.storage.jobs_file.parent, os.R_OK | os.W_OK),
        "run_log_storage": config.logging.run_log_dir.is_dir()
        and os.access(config.logging.run_log_dir, os.R_OK | os.W_OK),
        "llm_profile": config.llm.default_profile in config.llm.profiles,
    }
    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}
