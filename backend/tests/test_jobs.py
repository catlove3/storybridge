from __future__ import annotations

import asyncio

from app.jobs import JobManager


async def test_job_success():
    manager = JobManager()

    async def work():
        await asyncio.sleep(0.01)
        return {"answer": 42}

    job = manager.submit("analyze", "p1", work)
    assert job.status == "running"
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
    assert "ValueError" in done.error


async def test_list_for_project():
    manager = JobManager()
    manager.submit("analyze", "p1", _noop())
    manager.submit("verify", "p2", _noop())
    assert len(manager.list_for_project("p1")) == 1
    assert len(manager.list_for_project("p2")) == 1


def _noop():
    async def noop():
        return None

    return noop
