from __future__ import annotations

import asyncio

from app.jobs import JobManager


async def test_job_success():
    manager = JobManager()

    async def work():
        await asyncio.sleep(0.01)
        return {"answer": 42}

    job = manager.submit("analyze", "p1", work)
    assert job.status == "queued"
    await asyncio.sleep(0.1)
    done = manager.get(job.id)
    assert done.status == "done"
    assert done.result == {"answer": 42}
    assert done.error is None
    assert done.elapsed_ms >= 0


async def test_job_failure_captured():
    manager = JobManager()

    async def boom():
        raise ValueError("llm exploded")

    job = manager.submit("verify", "p1", boom)
    await asyncio.sleep(0.1)
    done = manager.get(job.id)
    assert done.status == "failed"
    assert done.error == "job_execution_failed"


async def test_find_idempotent_job():
    manager = JobManager()

    async def work():
        return "ok"

    job = manager.submit("analyze", "p1", work, idempotency_key="same")
    assert manager.find_idempotent("p1", "same") is job
    assert manager.find_idempotent("p1", "missing") is None
    await manager.shutdown()


async def test_list_for_project():
    manager = JobManager()
    manager.submit("analyze", "p1", _noop())
    manager.submit("verify", "p2", _noop())
    assert len(manager.list_for_project("p1")) == 1
    assert len(manager.list_for_project("p2")) == 1


async def test_cancel_running_job():
    manager = JobManager()
    started = asyncio.Event()

    async def work():
        started.set()
        await asyncio.sleep(60)

    job = manager.submit("analyze", "p1", work)
    await started.wait()
    cancelled = manager.cancel(job.id)
    await asyncio.sleep(0)

    assert cancelled.status == "cancelled"
    assert cancelled.cancel_requested is True
    assert cancelled.progress == 1.0


def test_jobs_restore_and_mark_interrupted(tmp_path):
    from app.storage import ProjectStore

    path = tmp_path / "jobs.json"
    ProjectStore._write_json(
        path,
        [
            {
                "id": "interrupted",
                "kind": "analyze",
                "project_id": "p1",
                "status": "running",
                "created_at": 1.0,
            },
            {
                "id": "complete",
                "kind": "verify",
                "project_id": "p1",
                "status": "done",
                "created_at": 1.0,
                "finished_at": 2.0,
                "result": {"ok": True},
            },
        ],
    )

    manager = JobManager(storage_path=path, ttl_seconds=10**12)

    interrupted = manager.get("interrupted")
    assert interrupted.status == "failed"
    assert "restarted" in interrupted.error
    assert manager.get("complete").result == {"ok": True}


async def test_completed_job_survives_manager_restart(tmp_path):
    path = tmp_path / "jobs.json"
    manager = JobManager(storage_path=path)

    async def work():
        return {"persisted": True}

    job = manager.submit("verify", "p1", work, idempotency_key="persist-once")
    while job.status in {"queued", "running"}:
        await asyncio.sleep(0.01)

    restored = JobManager(storage_path=path)
    restored_job = restored.get(job.id)
    duplicate = restored.submit(
        "verify", "p1", work, idempotency_key="persist-once"
    )

    assert restored_job.status == "done"
    assert restored_job.result == {"persisted": True}
    assert duplicate.id == job.id


def _noop():
    async def noop():
        return None

    return noop
