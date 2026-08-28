from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.llm import MockLLMClient
from app.main import app
from app.storage import ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


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
        yield api_client


async def test_project_not_found_paths(client):
    assert (await client.get("/api/projects/nope")).status_code == 404
    assert (await client.get("/api/projects/nope/state")).status_code == 404
    assert (await client.post("/api/projects/nope/analyze")).status_code == 404
    assert (await client.post("/api/projects/nope/verify")).status_code == 404
    assert (await client.get("/api/projects/nope/graph")).status_code == 404
    assert (await client.get("/api/projects/nope/propagate?mechanism=CM01")).status_code == 404
    assert (await client.get("/api/jobs/doesnotexist")).status_code == 404
    assert (await client.post("/api/jobs/doesnotexist/cancel")).status_code == 404


async def test_create_project_empty_script(client):
    response = await client.post("/api/projects", json={"script": ""})
    assert response.status_code == 200
    assert response.json()["id"]


async def test_create_project_missing_script(client):
    response = await client.post("/api/projects", json={"name": "x"})
    assert response.status_code == 422


async def test_state_before_analyze_404s(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    assert (await client.get(f"/api/projects/{project_id}/state")).status_code == 404
    assert (
        await client.get(f"/api/projects/{project_id}/propagate?mechanism=CM01")
    ).status_code == 404


async def test_graph_unknown_focus_404(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    await client.post(f"/api/projects/{project_id}/analyze")
    assert (
        await client.get(f"/api/projects/{project_id}/graph?focus=ZZZ")
    ).status_code == 404
    response = await client.get(f"/api/projects/{project_id}/graph?focus=CM01")
    assert response.status_code == 200
    labels = {node["id"]: node["label"] for node in response.json()["nodes"]}
    assert labels.get("CM01") == "编制"


async def test_job_flow_analyze_and_apply(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]

    job = (
        await client.post(f"/api/projects/{project_id}/jobs", json={"kind": "analyze"})
    ).json()
    assert job["status"] in {"queued", "running"}
    payload = {"status": "queued"}
    for _ in range(50):
        payload = (await client.get(f"/api/jobs/{job['job_id']}")).json()
        if payload["status"] not in {"queued", "running"}:
            break
        await asyncio.sleep(0.02)
    assert payload["status"] == "done"
    assert payload["result"]["scenes"] if isinstance(payload["result"], dict) else True

    bad = await client.post(
        f"/api/projects/{project_id}/jobs",
        json={"kind": "apply", "option_label": "B"},
    )
    assert bad.status_code == 400

    apply_job = (
        await client.post(
            f"/api/projects/{project_id}/jobs",
            json={
                "kind": "apply",
                "culture_mechanism_id": "CM01",
                "option_label": "B",
            },
        )
    ).json()
    payload = {"status": "queued"}
    for _ in range(100):
        payload = (await client.get(f"/api/jobs/{apply_job['job_id']}")).json()
        if payload["status"] not in {"queued", "running"}:
            break
        await asyncio.sleep(0.02)
    assert payload["status"] == "done"
    assert payload["result"]["applied"]["rewritten_scene_ids"]

    listing = (await client.get(f"/api/projects/{project_id}/jobs")).json()
    assert len(listing) == 2


async def test_job_unknown_kind(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    response = await client.post(
        f"/api/projects/{project_id}/jobs", json={"kind": "explode"}
    )
    assert response.status_code == 400


async def test_diff_and_bible_endpoints(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    await client.post(f"/api/projects/{project_id}/analyze")
    await client.post(
        f"/api/projects/{project_id}/adaptations/plan",
        json={"culture_mechanism_id": "CM01"},
    )
    await client.post(
        f"/api/projects/{project_id}/adaptations/apply",
        json={"culture_mechanism_id": "CM01", "option_label": "B"},
    )
    diff = (await client.get(f"/api/projects/{project_id}/diff")).json()
    assert len(diff) == 5
    bible = await client.get(f"/api/projects/{project_id}/bible")
    assert bible.status_code == 200
    assert "Adaptation Bible" in bible.json()["saved"] or bible.json()["saved"]

    revisions = (await client.get(f"/api/projects/{project_id}/revisions")).json()
    assert [revision["kind"] for revision in revisions][0] == "initial_parse"


async def test_apply_invalid_option_404(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    await client.post(f"/api/projects/{project_id}/analyze")
    response = await client.post(
        f"/api/projects/{project_id}/adaptations/apply",
        json={"culture_mechanism_id": "CM01", "option_label": "Z"},
    )
    assert response.status_code == 404


async def test_direct_apply_operation_id_cannot_commit_twice(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    await client.post(f"/api/projects/{project_id}/analyze")
    plan = (
        await client.post(
            f"/api/projects/{project_id}/adaptations/plan",
            json={"culture_mechanism_id": "CM01"},
        )
    ).json()
    body = {
        "culture_mechanism_id": "CM01",
        "option_label": "B",
        "based_on_version": plan["based_on_version"],
        "operation_id": "apply-once",
    }

    first = await client.post(f"/api/projects/{project_id}/adaptations/apply", json=body)
    duplicate = await client.post(
        f"/api/projects/{project_id}/adaptations/apply", json=body
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    revisions = (await client.get(f"/api/projects/{project_id}/revisions")).json()
    assert [revision["state_version"] for revision in revisions] == [1, 2]
