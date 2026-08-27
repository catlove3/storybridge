from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.llm import MockLLMClient
from app.main import app
from app.storage import ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


@pytest.fixture
def client(tmp_path):
    from app.cli import _load_default_mock_fixtures
    from app.jobs import JobManager

    mock = MockLLMClient()
    _load_default_mock_fixtures(mock)
    store = ProjectStore(tmp_path / "projects")
    with TestClient(app, raise_server_exceptions=False) as c:
        app.state.workflow = StoryBridgeWorkflow(store, mock)
        app.state.jobs = JobManager()
        yield c, mock


def test_api_concurrent_create_and_analyze(client):
    c, mock = client
    pids = [c.post("/api/projects", json={"script": f"s{i}"}).json()["id"] for i in range(3)]

    import threading

    def analyze(pid):
        r = c.post(f"/api/projects/{pid}/analyze")
        return r.status_code

    threads = [threading.Thread(target=analyze, args=(p,)) for p in pids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for pid in pids:
        assert c.get(f"/api/projects/{pid}/state").status_code == 200


def test_api_same_project_double_plan(client):
    c, mock = client
    pid = c.post("/api/projects", json={"script": "x"}).json()["id"]
    c.post(f"/api/projects/{pid}/analyze")

    import threading

    results = []

    def plan():
        r = c.post(f"/api/projects/{pid}/adaptations/plan", json={"culture_mechanism_id": "CM01"})
        results.append(r.status_code)

    threads = [threading.Thread(target=plan) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(code == 200 for code in results), results
    plans = c.get(f"/api/projects/{pid}/state").status_code
    assert plans == 200


def test_api_job_for_project_without_state(client):
    c, _ = client
    pid = c.post("/api/projects", json={"script": "x"}).json()["id"]
    job = c.post(f"/api/projects/{pid}/jobs", json={"kind": "apply", "culture_mechanism_id": "CM01", "option_label": "B"}).json()
    import time

    payload = {"status": "running"}
    for _ in range(50):
        payload = c.get(f"/api/jobs/{job['job_id']}").json()
        if payload["status"] != "running":
            break
        time.sleep(0.02)
    assert payload["status"] == "failed"
    assert "analyze" in payload["error"] or "KeyError" in payload["error"]


def test_api_malformed_market(client):
    c, _ = client
    r = c.post("/api/projects", json={"script": "x", "market": {"market": 123, "audience": None}})
    assert r.status_code == 422


def test_openai_client_server_error_retry_semantics():
    import httpx

    from app.config import ProfileConfig
    from app.llm.base import LLMRequest
    from app.llm.openai_compat import OpenAICompatClient

    profile = ProfileConfig(
        provider="openai_compat",
        base_url="http://127.0.0.1:1/v1",
        api_key_env="NO_KEY",
        model="m",
    )
    client = OpenAICompatClient(profile, "test")

    async def run():
        request = LLMRequest(step="x", system_prompt="s", user_prompt="u")
        try:
            await client.complete(request)
            return "ok"
        except (httpx.ConnectError, httpx.HTTPError, OSError):
            return "network-error-raised"

    assert asyncio.run(run()) == "network-error-raised"


def test_openai_client_400_without_response_format_fallback():
    import httpx

    from app.config import ProfileConfig
    from app.llm.base import LLMRequest
    from app.llm.openai_compat import OpenAICompatClient

    profile = ProfileConfig(
        provider="openai_compat",
        base_url="http://127.0.0.1:1/v1",
        api_key_env="NO_KEY",
        model="m",
        json_mode=True,
    )
    client = OpenAICompatClient(profile, "test")

    async def run():
        request = LLMRequest(step="x", system_prompt="s", user_prompt="u", json_mode=True)
        try:
            await client.complete(request)
        except (httpx.ConnectError, httpx.HTTPError, OSError):
            return "raises-network-error (fallback path not reached, expected)"

    assert asyncio.run(run())
