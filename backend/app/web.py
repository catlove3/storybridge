from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.api.sessions import session_router, validate_public_url
from app.config import BACKEND_ROOT, api_key_for, get_config
from app.public_usage import public_usage


def prepare_public_runtime(*, mock: bool = False) -> None:
    config = get_config()
    if not config.share.enabled:
        return
    # A URL may be omitted only for the explicitly labelled mock test server.
    if config.share.public_url or not mock:
        validate_public_url(config.share.public_url)
    if not mock:
        for name in {config.llm.default_profile, *config.llm.step_routes.values()}:
            if not api_key_for(config.llm.profiles[name]):
                raise ValueError("默认模型尚未配置。")
    public_usage().recover()


def install_web(app: FastAPI) -> None:
    app.include_router(session_router)

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    if os.environ.get("STORYBRIDGE_SERVE_FRONTEND") == "1":
        frontend = Path(
            os.environ.get("STORYBRIDGE_FRONTEND_DIR", BACKEND_ROOT.parent / "frontend/dist")
        )
        app.mount("/", StaticFiles(directory=frontend, html=True), name="website")
