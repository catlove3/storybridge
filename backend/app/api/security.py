from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.config import api_key_owners, get_config

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def require_owner(
    request: Request, api_key: str | None = Security(_API_KEY_HEADER)
) -> str:
    configured = api_key_owners()
    if get_config().share.enabled and api_key is None:
        from app.api.sessions import session_owner
        owner_id = session_owner(request)
    elif not configured and api_key is None:
        owner_id = get_config().security.default_owner
    else:
        owner_id = next(
            (
                owner
                for candidate, owner in configured.items()
                if api_key is not None and hmac.compare_digest(candidate, api_key)
            ),
            "",
        )
        if not owner_id:
            raise _error(401, "authentication_required", "A valid X-API-Key is required")
    request.state.owner_id = owner_id
    return owner_id


class ApiUsageGuard:
    def __init__(self) -> None:
        self._submissions: defaultdict[str, deque[float]] = defaultdict(deque)

    def check_job_submission(self, owner_id: str, owned_project_ids: set[str], jobs) -> None:
        config = get_config().security
        active = sum(
            job.status in {"queued", "running"}
            for project_id in owned_project_ids
            for job in jobs.list_for_project(project_id)
        )
        if active >= config.max_active_jobs_per_owner:
            raise _error(
                429,
                "concurrency_limit_exceeded",
                "Too many active jobs for this owner",
            )

        now = time.time()
        recent = self._submissions[owner_id]
        while recent and recent[0] <= now - 60:
            recent.popleft()
        if len(recent) >= config.max_job_submissions_per_minute:
            raise _error(429, "rate_limit_exceeded", "Job submission rate limit exceeded")
        recent.append(now)


def usage_guard(request: Request) -> ApiUsageGuard:
    guard = getattr(request.app.state, "usage_guard", None)
    jobs_identity = id(request.app.state.jobs)
    if guard is None or getattr(request.app.state, "usage_guard_jobs", None) != jobs_identity:
        guard = ApiUsageGuard()
        request.app.state.usage_guard = guard
        request.app.state.usage_guard_jobs = jobs_identity
    return guard


async def generation_admission(request: Request):
    """Synchronous generation endpoints share the same slots as background work."""
    from app.public_usage import PublicLimitError, public_usage

    slot = None
    if (get_config().share.enabled and request.method == "POST"
            and request.url.path.rsplit("/", 1)[-1] in {
                "analyze", "plan", "plan-batch", "apply", "apply-batch", "verify", "target-script"
            }):
        meta = request.app.state.workflow.store.load_meta(request.path_params["project_id"])
        if meta is None or meta.owner_id != request.state.owner_id:
            raise _error(404, "project_not_found", "Story not found")
        try:
            slot = public_usage().admit(request.state.owner_id)
        except PublicLimitError as exc:
            raise HTTPException(429, exc.detail()) from exc
    try:
        yield
    finally:
        if slot:
            public_usage().release(slot)


__all__ = ["ApiUsageGuard", "require_owner", "usage_guard"]
