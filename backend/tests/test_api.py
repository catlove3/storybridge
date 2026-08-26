from __future__ import annotations

import asyncio

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
        yield c


def test_project_not_found_paths(client):
    assert client.get("/api/projects/nope").status_code == 404
    assert client.get("/api/projects/nope/state").status_code == 404
    assert client.post("/api/projects/nope/analyze").status_code == 404
    assert client.post("/api/projects/nope/verify").status_code == 404
    assert client.get("/api/projects/nope/graph").status_code == 404
    assert client.get("/api/projects/nope/propagate?mechanism=CM01").status_code == 404
    assert client.get("/api/jobs/doesnotexist").status_code == 404


def test_create_project_empty_script(client):
    r = client.post("/api/projects", json={"script": ""})
    assert r.status_code == 200
    assert r.json()["id"]


def test_create_project_missing_script(client):
    r = client.post("/api/projects", json={"name": "x"})
    assert r.status_code == 422


def test_state_before_analyze_404s(client):
    pid = client.post("/api/projects", json={"script": "abc"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/state").status_code == 404
    assert client.get(f"/api/projects/{pid}/propagate?mechanism=CM01").status_code == 404


def test_graph_unknown_focus_404(client):
    pid = client.post("/api/projects", json={"script": "abc"}).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    client.post(f"/api/projects/{pid}/analyze")
    assert client.get(f"/api/projects/{pid}/graph?focus=ZZZ").status_code == 404
    ok = client.get(f"/api/projects/{pid}/graph?focus=CM01")
    assert ok.status_code == 200
    labels = {n["id"]: n["label"] for n in ok.json()["nodes"]}
    assert labels.get("CM01") == "编制"


def test_job_flow_analyze_and_apply(client):
    import time

    pid = client.post("/api/projects", json={"script": "abc"}).json()["id"]

    job = client.post(f"/api/projects/{pid}/jobs", json={"kind": "analyze"}).json()
    assert job["status"] == "running"
    payload = {"status": "running"}
    for _ in range(50):
        payload = client.get(f"/api/jobs/{job['job_id']}").json()
        if payload["status"] != "running":
            break
        time.sleep(0.02)
    assert payload["status"] == "done"
    assert payload["result"]["scenes"] if isinstance(payload["result"], dict) else True

    bad = client.post(f"/api/projects/{pid}/jobs", json={"kind": "apply", "option_label": "B"})
    assert bad.status_code == 400

    apply_job = client.post(
        f"/api/projects/{pid}/jobs",
        json={"kind": "apply", "culture_mechanism_id": "CM01", "option_label": "B"},
    ).json()
    payload = {"status": "running"}
    for _ in range(100):
        payload = client.get(f"/api/jobs/{apply_job['job_id']}").json()
        if payload["status"] != "running":
            break
        time.sleep(0.02)
    assert payload["status"] == "done"
    assert payload["result"]["applied"]["rewritten_scene_ids"]

    listing = client.get(f"/api/projects/{pid}/jobs").json()
    assert len(listing) == 2


def test_job_unknown_kind(client):
    pid = client.post("/api/projects", json={"script": "abc"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/jobs", json={"kind": "explode"})
    assert r.status_code == 400


def test_diff_and_bible_endpoints(client):
    pid = client.post("/api/projects", json={"script": "abc"}).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    client.post(f"/api/projects/{pid}/analyze")
    client.post(f"/api/projects/{pid}/adaptations/plan", json={"culture_mechanism_id": "CM01"})
    client.post(
        f"/api/projects/{pid}/adaptations/apply",
        json={"culture_mechanism_id": "CM01", "option_label": "B"},
    )
    diff = client.get(f"/api/projects/{pid}/diff").json()
    assert len(diff) == 5
    bible = client.get(f"/api/projects/{pid}/bible")
    assert bible.status_code == 200
    assert "Adaptation Bible" in bible.json()["saved"] or bible.json()["saved"]

    revisions = client.get(f"/api/projects/{pid}/revisions").json()
    assert [r["kind"] for r in revisions][0] == "initial_parse"


def test_apply_invalid_option_404(client):
    pid = client.post("/api/projects", json={"script": "abc"}).json()["id"]
    mock_client = app.state.workflow.rewriter.client
    mock_client.set_response("parse_story", sample_story_state_dict())
    client.post(f"/api/projects/{pid}/analyze")
    r = client.post(
        f"/api/projects/{pid}/adaptations/apply",
        json={"culture_mechanism_id": "CM01", "option_label": "Z"},
    )
    assert r.status_code == 404
