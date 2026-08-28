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
    if not configured:
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


__all__ = ["ApiUsageGuard", "require_owner", "usage_guard"]
