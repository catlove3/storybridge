from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.security import ApiUsageGuard
from app.jobs import JobManager
from app.llm import MockLLMClient
from app.main import app
from app.storage import ProjectStore
from app.workflow.engine import StoryBridgeWorkflow


@pytest.fixture
async def secure_client(tmp_path, monkeypatch):
    from app.cli import _load_default_mock_fixtures

    monkeypatch.setenv(
        "STORYBRIDGE_API_KEYS",
        json.dumps({"alice-secret": "alice", "bob-secret": "bob"}),
    )
    mock = MockLLMClient()
    _load_default_mock_fixtures(mock)
    app.state.workflow = StoryBridgeWorkflow(ProjectStore(tmp_path / "projects"), mock)
    app.state.jobs = JobManager()
    app.state.usage_guard = ApiUsageGuard()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, mock


async def test_api_key_authentication_and_owner_isolation(secure_client):
    client, _ = secure_client
    assert (await client.get("/api/projects")).status_code == 401
    assert (
        await client.get("/api/projects", headers={"X-API-Key": "wrong"})
    ).status_code == 401

    alice = {"X-API-Key": "alice-secret"}
    bob = {"X-API-Key": "bob-secret"}
    policy = await client.get("/api/runtime-policy", headers=alice)
    assert policy.status_code == 200
    assert policy.json()["authentication_required"] is True
    assert policy.json()["max_project_llm_tokens"] > 0
    assert "alice-secret" not in policy.text
    created = await client.post("/api/projects", json={"script": "private"}, headers=alice)
    project_id = created.json()["id"]

    assert len((await client.get("/api/projects", headers=alice)).json()) == 1
    assert (await client.get("/api/projects", headers=bob)).json() == []
    assert (await client.get(f"/api/projects/{project_id}", headers=bob)).status_code == 404
    assert (
        await client.post(
            f"/api/projects/{project_id}/jobs",
            json={"kind": "analyze"},
            headers=bob,
        )
    ).status_code == 404


async def test_project_data_export_and_delete(secure_client):
    client, _ = secure_client
    alice = {"X-API-Key": "alice-secret"}
    created = await client.post(
        "/api/projects",
        json={"name": "exportable", "script": "private script"},
        headers=alice,
    )
    project_id = created.json()["id"]

    exported = await client.get(f"/api/projects/{project_id}/data-export", headers=alice)
    assert exported.status_code == 200
    assert exported.json()["script"] == "private script"
    assert exported.json()["project"]["data_policy"]["sft_opt_in"] is False
    assert exported.json()["llm_runs"] == []

    deleted = await client.delete(f"/api/projects/{project_id}", headers=alice)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["run_records_deleted"] == 0
    assert (await client.get(f"/api/projects/{project_id}", headers=alice)).status_code == 404


async def test_api_input_boundaries_and_stable_upstream_error(secure_client):
    client, mock = secure_client
    alice = {"X-API-Key": "alice-secret"}

    oversized = await client.post(
        "/api/projects", json={"script": "x" * 500_001}, headers=alice
    )
    assert oversized.status_code == 422

    invalid_consent = await client.post(
        "/api/projects",
        json={"script": "x", "data_policy": {"sft_opt_in": True}},
        headers=alice,
    )
    assert invalid_consent.status_code == 422

    created = await client.post("/api/projects", json={"script": "x"}, headers=alice)
    project_id = created.json()["id"]

    def secret_failure(_request):
        raise RuntimeError("provider-secret-detail")

    mock.responses.pop("parse_story", None)
    mock.handler = secret_failure
    failed = await client.post(f"/api/projects/{project_id}/analyze", headers=alice)
    assert failed.status_code == 502
    body = failed.text
    assert "upstream_generation_failed" in body
    assert "provider-secret-detail" not in body


def test_openapi_exposes_typed_contracts_and_api_key_scheme():
    schema = app.openapi()
    assert "APIKeyHeader" in schema["components"]["securitySchemes"]
    assert schema["paths"]["/api/projects"]["post"]["responses"]["200"]["content"]
    depth = next(
        parameter
        for parameter in schema["paths"]["/api/projects/{project_id}/graph"]["get"][
            "parameters"
        ]
        if parameter["name"] == "depth"
    )
    assert depth["schema"]["maximum"] == 6
    assert "JobKind" in schema["components"]["schemas"]


def test_api_preflight_rejects_exhausted_project_budget(tmp_path):
    from app.api.routes import _enforce_llm_budget
    from app.llm import LLMRequest, LLMResponse
    from app.llm.router import RunMetadataLogger
    from app.privacy import project_data_context
    from app.schemas import DataPolicy

    mock = MockLLMClient()
    mock.run_logger = RunMetadataLogger(tmp_path / "runs", max_tokens_per_project=1)
    workflow = StoryBridgeWorkflow(ProjectStore(tmp_path / "projects"), mock)
    with project_data_context("project-budget", DataPolicy()):
        mock.run_logger.record(
            LLMRequest(step="parse_story", system_prompt="s", user_prompt="u"),
            LLMResponse(
                text="x",
                model="mock",
                profile_name="mock",
                step="parse_story",
                prompt_tokens=1,
            ),
        )

    with pytest.raises(HTTPException) as exc_info:
        _enforce_llm_budget(workflow, "project-budget")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "llm_budget_exhausted"
