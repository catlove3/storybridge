from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel


class Job(BaseModel):
    id: str
    kind: str
    project_id: str
    status: str = "running"
    created_at: float = 0.0
    finished_at: float | None = None
    result: Any = None
    error: str | None = None
    idempotency_key: str | None = None

    def serialize(self) -> dict:
        payload = self.model_dump()
        result = payload.get("result")
        if hasattr(result, "model_dump"):
            payload["result"] = result.model_dump(mode="json")
        elif isinstance(result, list):
            payload["result"] = [
                r.model_dump(mode="json") if hasattr(r, "model_dump") else r for r in result
            ]
        return payload

    @property
    def elapsed_ms(self) -> int:
        end = self.finished_at or time.time()
        return int((end - self.created_at) * 1000)


class JobManager:
    def __init__(self, max_concurrent: int = 4) -> None:
        self._jobs: dict[str, Job] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._project_locks: dict[str, asyncio.Lock] = {}
        self._idempotent_jobs: dict[tuple[str, str], str] = {}

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_for_project(self, project_id: str) -> list[Job]:
        return [j for j in self._jobs.values() if j.project_id == project_id]

    def submit(
        self,
        kind: str,
        project_id: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        idempotency_key: str | None = None,
    ) -> Job:
        if idempotency_key:
            existing_id = self._idempotent_jobs.get((project_id, idempotency_key))
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if existing.kind != kind:
                    raise ValueError("idempotency key was already used for another job kind")
                return existing

        job = Job(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            project_id=project_id,
            created_at=time.time(),
            idempotency_key=idempotency_key,
        )
        self._jobs[job.id] = job
        if idempotency_key:
            self._idempotent_jobs[(project_id, idempotency_key)] = job.id

        async def runner() -> None:
            async with self._semaphore:
                project_lock = self._project_locks.setdefault(project_id, asyncio.Lock())
                async with project_lock:
                    try:
                        job.result = await coro_factory()
                        job.status = "done"
                    except Exception as exc:
                        job.status = "failed"
                        job.error = f"{type(exc).__name__}: {exc}"
                    finally:
                        job.finished_at = time.time()

        asyncio.get_running_loop().create_task(runner())
        return job
