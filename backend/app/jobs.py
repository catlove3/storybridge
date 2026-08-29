from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.database import SQLiteDatabase
from app.storage import ProjectStore

logger = logging.getLogger(__name__)


class Job(BaseModel):
    id: str
    kind: str
    project_id: str
    status: str = "queued"
    created_at: float = 0.0
    finished_at: float | None = None
    result: Any = None
    error: str | None = None
    idempotency_key: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    cancel_requested: bool = False

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


class SQLiteJobPersistence:
    def __init__(self, database_path: Path) -> None:
        self.database = SQLiteDatabase(database_path)

    def import_legacy_once(self, path: Path | None) -> None:
        if path is None:
            return
        source_key = f"legacy-jobs:{path.resolve()}"
        raw = ProjectStore._read_json(path) or []
        if not isinstance(raw, list):
            raw = []
        with self.database.transaction(immediate=True) as connection:
            seen = connection.execute(
                "SELECT 1 FROM legacy_imports WHERE source_key = ?", (source_key,)
            ).fetchone()
            if seen is not None:
                return
            for payload in raw:
                try:
                    job = Job.model_validate(payload)
                except Exception:
                    continue
                self._upsert(connection, job)
            connection.execute(
                """
                INSERT INTO legacy_imports(source_key, imported_at, item_count)
                VALUES (?, CURRENT_TIMESTAMP, ?)
                """,
                (source_key, len(raw)),
            )

    def load(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at, id").fetchall()
        return [
            {
                "id": row["id"],
                "kind": row["kind"],
                "project_id": row["project_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "finished_at": row["finished_at"],
                "result": (
                    json.loads(row["result_json"])
                    if row["result_json"] is not None
                    else None
                ),
                "error": row["error"],
                "idempotency_key": row["idempotency_key"],
                "progress": row["progress"],
                "cancel_requested": bool(row["cancel_requested"]),
            }
            for row in rows
        ]

    @staticmethod
    def _upsert(connection, job: Job) -> None:
        payload = job.serialize()
        connection.execute(
            """
            INSERT INTO jobs(
                id, kind, project_id, status, created_at, finished_at, result_json,
                error, idempotency_key, progress, cancel_requested
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                project_id = excluded.project_id,
                status = excluded.status,
                created_at = excluded.created_at,
                finished_at = excluded.finished_at,
                result_json = excluded.result_json,
                error = excluded.error,
                idempotency_key = excluded.idempotency_key,
                progress = excluded.progress,
                cancel_requested = excluded.cancel_requested
            """,
            (
                job.id,
                job.kind,
                job.project_id,
                job.status,
                job.created_at,
                job.finished_at,
                json.dumps(payload["result"], ensure_ascii=False),
                job.error,
                job.idempotency_key,
                job.progress,
                int(job.cancel_requested),
            ),
        )

    def save(self, jobs: list[Job]) -> None:
        with self.database.transaction(immediate=True) as connection:
            retained = {job.id for job in jobs}
            if retained:
                placeholders = ",".join("?" for _ in retained)
                connection.execute(
                    f"DELETE FROM jobs WHERE id NOT IN ({placeholders})", tuple(retained)
                )
            else:
                connection.execute("DELETE FROM jobs")
            for job in jobs:
                self._upsert(connection, job)


class JobManager:
    def __init__(
        self,
        max_concurrent: int = 4,
        storage_path: Path | None = None,
        database_path: Path | None = None,
        ttl_seconds: int = 7 * 24 * 60 * 60,
    ) -> None:
        self._jobs: dict[str, Job] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._project_locks: dict[str, asyncio.Lock] = {}
        self._idempotent_jobs: dict[tuple[str, str], str] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._storage_path = storage_path if database_path is None else None
        self._sqlite = SQLiteJobPersistence(database_path) if database_path else None
        if self._sqlite is not None:
            self._sqlite.import_legacy_once(storage_path)
        self._ttl_seconds = ttl_seconds
        self._restore()

    def _restore(self) -> None:
        if self._sqlite is not None:
            raw = self._sqlite.load()
        elif self._storage_path is not None:
            raw = ProjectStore._read_json(self._storage_path) or []
        else:
            return
        now = time.time()
        for payload in raw:
            try:
                job = Job.model_validate(payload)
            except Exception:
                continue
            if job.status in {"queued", "running"}:
                job.status = "failed"
                job.error = "Interrupted: service restarted before the job completed"
                job.finished_at = now
                job.progress = 1.0
            if job.finished_at and now - job.finished_at > self._ttl_seconds:
                continue
            self._jobs[job.id] = job
            if job.idempotency_key:
                self._idempotent_jobs[(job.project_id, job.idempotency_key)] = job.id
        self._persist()

    def _persist(self) -> None:
        if self._sqlite is not None:
            self._sqlite.save(list(self._jobs.values()))
        elif self._storage_path is not None:
            ProjectStore._write_json(
                self._storage_path,
                [job.serialize() for job in self._jobs.values()],
            )

    def _prune_expired(self) -> None:
        cutoff = time.time() - self._ttl_seconds
        expired_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at is not None and job.finished_at < cutoff
        ]
        for job_id in expired_ids:
            job = self._jobs.pop(job_id)
            if job.idempotency_key:
                self._idempotent_jobs.pop((job.project_id, job.idempotency_key), None)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_for_project(self, project_id: str) -> list[Job]:
        return [j for j in self._jobs.values() if j.project_id == project_id]

    def find_idempotent(self, project_id: str, idempotency_key: str) -> Job | None:
        job_id = self._idempotent_jobs.get((project_id, idempotency_key))
        return self._jobs.get(job_id) if job_id is not None else None

    def delete_for_project(self, project_id: str) -> int:
        jobs = self.list_for_project(project_id)
        for job in jobs:
            self.cancel(job.id)
            self._jobs.pop(job.id, None)
            if job.idempotency_key:
                self._idempotent_jobs.pop((project_id, job.idempotency_key), None)
        self._persist()
        return len(jobs)

    def cancel(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status in {"done", "failed", "cancelled"}:
            return job
        job.cancel_requested = True
        job.status = "cancelled"
        job.finished_at = time.time()
        job.progress = 1.0
        task = self._tasks.get(job_id)
        if task is not None:
            task.cancel()
        self._persist()
        return job

    def submit(
        self,
        kind: str,
        project_id: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        idempotency_key: str | None = None,
    ) -> Job:
        self._prune_expired()
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
        self._persist()

        async def runner() -> None:
            try:
                async with self._semaphore:
                    project_lock = self._project_locks.setdefault(project_id, asyncio.Lock())
                    async with project_lock:
                        if job.cancel_requested:
                            return
                        job.status = "running"
                        job.progress = 0.05
                        self._persist()
                        job.result = await coro_factory()
                        job.status = "done"
                        job.progress = 1.0
            except asyncio.CancelledError:
                job.status = "cancelled"
                job.error = None
                job.progress = 1.0
            except Exception as exc:
                logger.error(
                    "job failed: id=%s kind=%s project_id=%s exception_type=%s",
                    job.id,
                    job.kind,
                    job.project_id,
                    type(exc).__name__,
                )
                job.status = "failed"
                job.error = "job_execution_failed"
                job.progress = 1.0
            finally:
                job.finished_at = job.finished_at or time.time()
                self._tasks.pop(job.id, None)
                self._persist()

        task = asyncio.get_running_loop().create_task(runner())
        self._tasks[job.id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job.id, None))
        return job

    async def shutdown(self) -> None:
        for job_id in list(self._tasks):
            self.cancel(job_id)
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._persist()
