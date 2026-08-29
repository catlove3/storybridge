from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.llm import MockLLMClient
from app.main import app
from app.schemas import AdaptationPlan
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


async def test_liveness_and_readiness_are_distinct(client):
    health = await client.get("/healthz")
    readiness = await client.get("/readyz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert readiness.status_code in {200, 503}
    assert set(readiness.json()["checks"]) == {
        "projects_storage",
        "jobs_storage",
        "run_log_storage",
        "llm_profile",
    }


async def test_create_project_empty_script(client):
    response = await client.post("/api/projects", json={"script": ""})
    assert response.status_code == 422


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
    assert bad.status_code == 422

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


async def test_batch_plan_and_apply_job_commit_all_selections_once(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    await client.post(f"/api/projects/{project_id}/analyze")

    cm01_payload = (
        await client.post(
            f"/api/projects/{project_id}/adaptations/plan",
            json={"culture_mechanism_id": "CM01"},
        )
    ).json()
    cm01_plan = AdaptationPlan.model_validate(cm01_payload)
    app.state.workflow.store.save_plan(
        project_id,
        cm01_plan.model_copy(
            deep=True,
            update={"culture_mechanism_id": "CM02", "original_name": "彩礼"},
        ),
    )

    plan_job = (
        await client.post(
            f"/api/projects/{project_id}/jobs",
            json={
                "kind": "plan_batch",
                "culture_mechanism_ids": ["CM01", "CM02"],
            },
        )
    ).json()
    plan_payload = {"status": "queued"}
    for _ in range(50):
        plan_payload = (await client.get(f"/api/jobs/{plan_job['job_id']}")).json()
        if plan_payload["status"] not in {"queued", "running"}:
            break
        await asyncio.sleep(0.02)
    assert plan_payload["status"] == "done"
    assert [item["culture_mechanism_id"] for item in plan_payload["result"]] == [
        "CM01",
        "CM02",
    ]

    apply_job = (
        await client.post(
            f"/api/projects/{project_id}/jobs",
            json={
                "kind": "apply_batch",
                "adaptations": [
                    {"culture_mechanism_id": "CM01", "option_label": "B"},
                    {"culture_mechanism_id": "CM02", "option_label": "C"},
                ],
                "based_on_version": 1,
                "idempotency_key": "apply-two-points",
            },
        )
    ).json()
    apply_payload = {"status": "queued"}
    for _ in range(100):
        apply_payload = (await client.get(f"/api/jobs/{apply_job['job_id']}")).json()
        if apply_payload["status"] not in {"queued", "running"}:
            break
        await asyncio.sleep(0.02)

    assert apply_payload["status"] == "done"
    assert len(apply_payload["result"]["applied"]) == 2
    assert apply_payload["result"]["from_version"] == 1
    assert apply_payload["result"]["to_version"] == 2
    state = (await client.get(f"/api/projects/{project_id}/state")).json()
    assert state["version"] == 2
    revisions = (await client.get(f"/api/projects/{project_id}/revisions")).json()
    assert [item["state_version"] for item in revisions] == [1, 2]


async def test_batch_jobs_reject_duplicate_mechanisms(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    duplicate_plan = await client.post(
        f"/api/projects/{project_id}/jobs",
        json={
            "kind": "plan_batch",
            "culture_mechanism_ids": ["CM01", "CM01"],
        },
    )
    duplicate_apply = await client.post(
        f"/api/projects/{project_id}/jobs",
        json={
            "kind": "apply_batch",
            "adaptations": [
                {"culture_mechanism_id": "CM01", "option_label": "A"},
                {"culture_mechanism_id": "CM01", "option_label": "B"},
            ],
        },
    )
    assert duplicate_plan.status_code == 422
    assert duplicate_apply.status_code == 422


async def test_job_unknown_kind(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    response = await client.post(
        f"/api/projects/{project_id}/jobs", json={"kind": "explode"}
    )
    assert response.status_code == 422


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
    assert "Adaptation Bible" in bible.json()["content"]

    revisions = (await client.get(f"/api/projects/{project_id}/revisions")).json()
    assert [revision["kind"] for revision in revisions][0] == "initial_parse"


async def test_apply_invalid_option_rejected_by_contract(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    await client.post(f"/api/projects/{project_id}/analyze")
    response = await client.post(
        f"/api/projects/{project_id}/adaptations/apply",
        json={"culture_mechanism_id": "CM01", "option_label": "Z"},
    )
    assert response.status_code == 422


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


async def test_target_script_render_and_get(client):
    project_id = (await client.post("/api/projects", json={"script": "abc"})).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    await client.post(f"/api/projects/{project_id}/analyze")

    assert (await client.get(f"/api/projects/{project_id}/target-script")).status_code == 404
    rendered = await client.post(f"/api/projects/{project_id}/target-script")
    loaded = await client.get(f"/api/projects/{project_id}/target-script")

    assert rendered.status_code == loaded.status_code == 200
    assert rendered.json() == loaded.json()
    assert rendered.json()["target_language"] == "English"
    assert len(rendered.json()["scenes"]) == 8
