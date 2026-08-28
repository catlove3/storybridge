from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.llm import MockLLMClient
from app.main import app
from app.storage import ProjectStore
from app.workflow.engine import StoryBridgeWorkflow


@pytest.fixture
async def client(tmp_path):
    from app.cli import _load_default_mock_fixtures
    from app.jobs import JobManager

    mock = MockLLMClient()
    _load_default_mock_fixtures(mock)
    store = ProjectStore(tmp_path / "projects")
    app.state.workflow = StoryBridgeWorkflow(store, mock)
    app.state.jobs = JobManager()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as api_client:
        yield api_client, mock


async def test_api_concurrent_create_and_analyze(client):
    api_client, _ = client
    project_ids = [
        (await api_client.post("/api/projects", json={"script": f"s{i}"})).json()["id"]
        for i in range(3)
    ]
    responses = await asyncio.gather(
        *(api_client.post(f"/api/projects/{project_id}/analyze") for project_id in project_ids)
    )
    assert all(response.status_code == 200 for response in responses)
    for project_id in project_ids:
        assert (await api_client.get(f"/api/projects/{project_id}/state")).status_code == 200


async def test_api_same_project_double_plan(client):
    api_client, _ = client
    project_id = (
        await api_client.post("/api/projects", json={"script": "x"})
    ).json()["id"]
    await api_client.post(f"/api/projects/{project_id}/analyze")
    responses = await asyncio.gather(
        *(
            api_client.post(
                f"/api/projects/{project_id}/adaptations/plan",
                json={"culture_mechanism_id": "CM01"},
            )
            for _ in range(4)
        )
    )
    assert all(response.status_code == 200 for response in responses), responses
    assert (await api_client.get(f"/api/projects/{project_id}/state")).status_code == 200


async def test_api_job_for_project_without_state(client):
    api_client, _ = client
    project_id = (
        await api_client.post("/api/projects", json={"script": "x"})
    ).json()["id"]
    job = (
        await api_client.post(
            f"/api/projects/{project_id}/jobs",
            json={
                "kind": "apply",
                "culture_mechanism_id": "CM01",
                "option_label": "B",
            },
        )
    ).json()
    payload = {"status": "running"}
    for _ in range(50):
        payload = (await api_client.get(f"/api/jobs/{job['job_id']}")).json()
        if payload["status"] != "running":
            break
        await asyncio.sleep(0.02)
    assert payload["status"] == "failed"
    assert "analyze" in payload["error"] or "KeyError" in payload["error"]


async def test_api_malformed_market(client):
    api_client, _ = client
    response = await api_client.post(
        "/api/projects",
        json={"script": "x", "market": {"market": 123, "audience": None}},
    )
    assert response.status_code == 422


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
