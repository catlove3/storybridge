from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
import pytest
import yaml
from cryptography.fernet import Fernet

from app import demo_scripts
from app.api.sessions import COOKIE, validate_public_url
from app.config import ShareConfig, get_config
from app.database import SQLiteDatabase
from app.jobs import JobManager
from app.main import app
from app.privacy import project_data_context
from app.public_usage import PublicLimitError, PublicUsage, public_usage
from app.schemas import DataPolicy
from app.secrets import decrypt_api_key, migrate
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile
from app.workflow.engine import StoryBridgeWorkflow


@pytest.fixture
async def public_server(tmp_path, monkeypatch, mock_client):
    config = get_config()
    monkeypatch.setattr(
        config, "share", ShareConfig(enabled=True, public_url="https://stories.test")
    )
    monkeypatch.setattr(config.storage, "database_file", tmp_path / "public.sqlite3")
    monkeypatch.setenv("STORYBRIDGE_API_KEYS", '{"api-secret":"api-owner"}')
    store = SQLiteProjectStore(config.storage.database_file, tmp_path / "artifacts")
    app.state.workflow = StoryBridgeWorkflow(store, mock_client)
    app.state.jobs = JobManager(database_path=config.storage.database_file)
    app.state.mock_mode = True
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="https://stories.test") as a,
        httpx.AsyncClient(transport=transport, base_url="https://stories.test") as b,
    ):
        yield a, b, store, mock_client
    await app.state.jobs.shutdown()


async def login(client):
    response = await client.post("/api/session", headers={"Origin": "https://stories.test"})
    assert response.status_code == 200, response.text
    client.headers.update(
        {"Origin": "https://stories.test", "X-CSRF-Token": response.json()["csrf_token"]}
    )
    return response


def test_encryption_migration_atomic_repeatable_and_wrong_key(tmp_path):
    env = tmp_path / ".env"
    key = tmp_path / "secrets/master.key"
    env.write_text(
        'LLM_BASE_URL=https://example.test/v1\nLLM_MODEL=model-a\nLLM_API_KEY="sensitive\nmultiline"\nKEEP=yes\n'
    )
    assert migrate(env, key)
    assert key.stat().st_mode & 0o777 == 0o600
    encrypted_env = env.read_text()
    assert "sensitive" not in encrypted_env and "LLM_API_KEY=" not in encrypted_env
    assert "LLM_MODEL=model-a" in encrypted_env and "KEEP=yes" in encrypted_env
    encrypted = encrypted_env.split("LLM_API_KEY_ENCRYPTED=")[1].strip()
    assert decrypt_api_key(encrypted, key) == "sensitive\nmultiline"
    assert not migrate(env, key)
    key.write_bytes(Fernet.generate_key())
    with pytest.raises(ValueError, match="无法解密"):
        migrate(env, key)
    assert env.read_text() == encrypted_env
    key.unlink()
    with pytest.raises(ValueError):
        migrate(env, key)
    assert not key.exists()


def test_migration_duplicates_and_permission_failures(tmp_path):
    env = tmp_path / ".env"
    key = tmp_path / "master.key"
    env.write_text("LLM_API_KEY=secret\n")
    migrate(env, key)
    encrypted = env.read_text()
    env.write_text(encrypted + "LLM_API_KEY=secret\n")
    assert migrate(env, key)
    env.write_text(encrypted + "LLM_API_KEY=different\n")
    with pytest.raises(ValueError, match="不一致"):
        migrate(env, key)
    assert "different" in env.read_text()
    key.chmod(0o644)
    with pytest.raises(ValueError):
        migrate(env, key)
    env.write_text("LLM_MODEL=x\n")
    with pytest.raises(ValueError, match="配置"):
        migrate(env, key)


async def test_sessions_csrf_and_all_owner_boundaries(public_server):
    a, b, store, _ = public_server
    local = store.create_project("old private", "local text", MarketProfile())
    assert (await a.get("/api/projects")).status_code == 401
    assert (
        await a.post("/api/session", headers={"Origin": "https://evil.test"})
    ).status_code == 403
    first = await login(a)
    cookie = first.headers["set-cookie"]
    assert all(flag in cookie for flag in ["HttpOnly", "Secure", "SameSite=lax", "Max-Age="])
    assert (await login(a)).json()["visitor_id"] == first.json()["visitor_id"]
    assert (await login(b)).json()["visitor_id"] != first.json()["visitor_id"]
    assert (await a.get(f"/api/projects/{local.id}")).status_code == 404
    body = {"script": "edited story", "idempotency_key": "create-once"}
    pid = (await a.post("/api/projects", json=body)).json()["id"]
    assert (await a.post("/api/projects", json=body)).json()["id"] == pid
    assert len((await a.get("/api/projects")).json()) == 1
    for path in [
        "",
        "/state",
        "/jobs",
        "/data-export",
        "/target-script",
        "/verification",
        "/bible",
    ]:
        assert (await b.get(f"/api/projects/{pid}{path}")).status_code == 404
    assert (await b.delete(f"/api/projects/{pid}")).status_code == 404
    assert (await b.post(f"/api/projects/{pid}/jobs", json={"kind": "analyze"})).status_code == 404
    for headers in [{"X-CSRF-Token": "bad"}, {"Origin": "https://evil.test"}]:
        assert (
            await a.post("/api/projects", json={"script": "x"}, headers=headers)
        ).status_code == 403
    job = await a.post(
        f"/api/projects/{pid}/jobs", json={"kind": "analyze", "idempotency_key": "analysis"}
    )
    jid = job.json()["job_id"]
    assert (await b.get(f"/api/jobs/{jid}")).status_code == 404
    assert (await b.post(f"/api/jobs/{jid}/cancel")).status_code == 404
    assert (await b.get("/api/projects")).json() == []
    assert (await b.get("/api/projects", headers={"X-API-Key": "api-secret"})).status_code == 200
    assert (await b.get("/api/projects", headers={"X-API-Key": "wrong"})).status_code == 401
    with public_usage().database.transaction() as db:
        assert a.cookies[COOKIE] not in [
            row[0] for row in db.execute("SELECT credential_hash FROM visitor_sessions")
        ]
    with public_usage().database.transaction(immediate=True) as db:
        db.execute("UPDATE visitor_sessions SET expires_at=0")
    assert (await a.get("/api/projects")).status_code == 401
    assert (await login(a)).json()["visitor_id"] != first.json()["visitor_id"]


async def test_quota_restart_deletion_and_read_access(public_server):
    a, _, _, mock = public_server
    owner = (await login(a)).json()["visitor_id"]
    pid = (await a.post("/api/projects", json={"script": "x"})).json()["id"]
    amount = get_config().share.visitor_daily_tokens
    ledger = public_usage()
    ledger.settle(ledger.reserve(owner, amount), None)
    blocked = await a.post(f"/api/projects/{pid}/analyze")
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "visitor_daily_quota"
    assert blocked.json()["detail"]["resets_at"].endswith("+08:00")
    assert (await a.post(f"/api/projects/{pid}/jobs", json={"kind": "analyze"})).status_code == 429
    assert (await a.get(f"/api/projects/{pid}/data-export")).status_code == 200
    assert (await a.delete(f"/api/projects/{pid}")).status_code == 200
    assert (
        PublicUsage(SQLiteDatabase(ledger.database.path), ledger.config).status(owner)[
            "visitor_used"
        ]
        == amount
    )
    assert (await a.get("/api/runtime-policy")).json()["max_project_llm_tokens"] == 0
    assert not mock.calls


async def test_generation_slots_cover_sync_async_and_deduplicate(public_server):
    a, b, _, _ = public_server
    await login(a)
    await login(b)
    pid = (await a.post("/api/projects", json={"script": "x"})).json()["id"]
    other = (await b.post("/api/projects", json={"script": "x"})).json()["id"]
    gate = asyncio.Event()

    async def stalled(_):
        await gate.wait()
        return {"ok": True}

    app.state.workflow.analyze = stalled
    body = {"kind": "analyze", "idempotency_key": "once"}
    first = await a.post(f"/api/projects/{pid}/jobs", json=body)
    repeat = await a.post(f"/api/projects/{pid}/jobs", json=body)
    assert first.json()["job_id"] == repeat.json()["job_id"]
    assert (await a.post(f"/api/projects/{pid}/verify")).json()["detail"][
        "code"
    ] == "visitor_concurrency"
    assert (await b.post(f"/api/projects/{other}/jobs", json=body)).status_code == 200
    ledger = public_usage()
    extra_slots = [
        ledger.admit(f"concurrent-visitor-{index}")
        for index in range(get_config().share.site_concurrency - 2)
    ]
    with pytest.raises(PublicLimitError) as error:
        ledger.admit("over-site-concurrency")
    assert error.value.code == "site_concurrency"
    for slot in extra_slots:
        ledger.release(slot)
    gate.set()
    await asyncio.sleep(0.03)
    with public_usage().database.transaction() as db:
        assert all(row[0] == 0 for row in db.execute("SELECT active FROM generation_slots"))


async def test_job_error_details_persist(public_server):
    a, _, _, _ = public_server
    await login(a)
    pid = (await a.post("/api/projects", json={"script": "x"})).json()["id"]

    async def fails(_):
        raise PublicLimitError(
            "site_daily_quota", "今天的全站额度不足。", "2030-01-02T00:00:00+08:00"
        )

    app.state.workflow.analyze = fails
    job = await a.post(f"/api/projects/{pid}/jobs", json={"kind": "analyze"})
    await asyncio.sleep(0.03)
    result = await a.get("/api/jobs/" + job.json()["job_id"])
    assert result.json()["error_code"] == "site_daily_quota"
    restored = JobManager(database_path=get_config().storage.database_file)
    assert restored.get(job.json()["job_id"]).resets_at == "2030-01-02T00:00:00+08:00"


def test_atomic_reservations_and_beijing_rollover(tmp_path):
    now = [datetime.fromisoformat("2030-01-01T23:59:59+08:00").timestamp()]
    config = ShareConfig(visitor_daily_tokens=100, site_daily_tokens=150)
    usage = PublicUsage(SQLiteDatabase(tmp_path / "ledger.sqlite3"), config, clock=lambda: now[0])

    def reserve(_):
        try:
            return usage.reserve("a", 30)
        except PublicLimitError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations = [i for i in pool.map(reserve, range(8)) if i]
    assert len(reservations) == 3
    usage.settle(reservations[0], 10)
    usage.settle(reservations[0], 0)
    assert usage.status("a")["visitor_used"] == 70
    usage.reserve("b", 80)
    with pytest.raises(PublicLimitError, match="全站"):
        usage.reserve("c", 1)
    now[0] += 2
    assert usage.status("a")["visitor_used"] == 0
    usage.reserve("a", 100)
    assert usage.status("a")["site_used"] == 100
    with pytest.raises(ValueError):
        usage.reserve("", 10)


def test_persistent_submission_rates(tmp_path):
    now = [1000.0]
    config = ShareConfig(visitor_submissions_per_minute=2, site_submissions_per_minute=3)
    db = SQLiteDatabase(tmp_path / "rate.sqlite3")
    usage = PublicUsage(db, config, clock=lambda: now[0])
    for _ in range(2):
        usage.release(usage.admit("a"))
    restarted = PublicUsage(db, config, clock=lambda: now[0])
    restarted.recover()
    with pytest.raises(PublicLimitError) as error:
        restarted.admit("a")
    assert error.value.code == "visitor_rate_limit"
    restarted.release(restarted.admit("b"))
    with pytest.raises(PublicLimitError) as error:
        restarted.admit("c")
    assert error.value.code == "site_rate_limit"
    now[0] += 61
    assert restarted.admit("a")


async def test_http_and_structured_retries_and_missing_usage_are_charged(
    public_server, monkeypatch
):
    from pydantic import BaseModel

    from app.config import ProfileConfig
    from app.llm.base import LLMRequest
    from app.llm.openai_compat import OpenAICompatClient
    from app.llm.structured import generate_structured

    monkeypatch.setattr("app.llm.openai_compat.api_key_for", lambda _: "test")
    count = 0

    async def response(request):
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"value":1}'}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 6},
            },
        )

    client = OpenAICompatClient(
        ProfileConfig(model="test", max_tokens=40, retry_base_delay=0),
        "test",
        transport=httpx.MockTransport(response),
    )
    request = LLMRequest(step="test", system_prompt="a", user_prompt="b")
    with project_data_context("p", DataPolicy(), "a"):
        result = await client.complete(request)
    assert result.http_attempts == 2
    used = public_usage().status("a")["visitor_used"]
    assert used > 1040
    await client.aclose()

    async def no_usage(_):
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"value":1}'}}]})

    client = OpenAICompatClient(
        ProfileConfig(model="test", max_tokens=40), "test", transport=httpx.MockTransport(no_usage)
    )
    with project_data_context("p", DataPolicy(), "a"):
        await client.complete(request)
    assert public_usage().status("a")["visitor_used"] > used + 1000
    await client.aclose()
    attempts = 0

    async def dirty(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "bad" if attempts == 1 else '{"value":1}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        )

    client = OpenAICompatClient(
        ProfileConfig(model="test"), "test", transport=httpx.MockTransport(dirty)
    )

    class Output(BaseModel):
        value: int

    before = public_usage().status("a")["visitor_used"]
    with project_data_context("p", DataPolicy(), "a"):
        assert (
            await generate_structured(
                client, Output, step="test", system_prompt="x", user_prompt="y"
            )
        ).value == 1
    assert public_usage().status("a")["visitor_used"] == before + 40
    await client.aclose()


async def test_live_catalog_and_failure_does_not_block_manual_input(
    public_server, tmp_path, monkeypatch
):
    a, _, _, mock = public_server
    await login(a)
    root = tmp_path / "scripts"
    root.mkdir()
    catalog = tmp_path / "catalog.yaml"
    monkeypatch.setattr(demo_scripts, "CATALOG", catalog)
    monkeypatch.setattr(demo_scripts, "SCRIPTS", root)

    def entry(id, file, order=0, enabled=True):
        return dict(
            id=id, file=file, title=id, summary="介绍", genre="喜剧", order=order, enabled=enabled
        )

    root.joinpath("a.md").write_text("完整故事 A", encoding="utf-8")
    catalog.write_text(yaml.safe_dump([entry("a", "a.md", 20)]))
    assert (await a.get("/api/demo-scripts")).json()[0]["id"] == "a"
    assert (await a.get("/api/demo-scripts/a")).json()["text"] == "完整故事 A"
    root.joinpath("b.txt").write_text("故事 B")
    catalog.write_text(yaml.safe_dump([entry("a", "a.md", 20), entry("b", "b.txt", 10)]))
    assert [e["id"] for e in (await a.get("/api/demo-scripts")).json()] == ["b", "a"]
    root.joinpath("a.md").write_text("修改后的正文")
    assert (await a.get("/api/demo-scripts/a")).json()["text"] == "修改后的正文"
    outside = tmp_path / "private.md"
    outside.write_text("private")
    root.joinpath("link.md").symlink_to(outside)
    catalog.write_text(
        yaml.safe_dump(
            [
                entry("a", "a.md", enabled=False),
                entry("traversal", "../private.md"),
                entry("absolute", str(outside)),
                entry("symlink", "link.md"),
                entry("missing", "missing.txt"),
                {"broken": True},
            ]
        )
    )
    assert (await a.get("/api/demo-scripts/a")).status_code == 404
    assert [e["id"] for e in (await a.get("/api/demo-scripts")).json()] == ["missing"]
    assert (await a.get("/api/demo-scripts/missing")).status_code == 503
    catalog.write_text("bad: [")
    assert (await a.get("/api/demo-scripts")).status_code == 503
    assert (await a.post("/api/projects", json={"script": "手动输入依然可用"})).status_code == 200
    assert not mock.calls


async def test_render_gate_and_homepage_only_qr(public_server):
    a, _, _, _ = public_server
    await login(a)
    pid = (await a.post("/api/projects", json={"script": "x"})).json()["id"]
    assert (await a.post(f"/api/projects/{pid}/analyze")).status_code == 200
    blocked = await a.post(f"/api/projects/{pid}/target-script")
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "verification_blocked"
    assert (await a.post(f"/api/projects/{pid}/verify")).status_code == 200
    assert (await a.get(f"/api/projects/{pid}/verification")).json()["overall_status"] != "not_run"
    qr = await a.get("/api/share-code")
    assert qr.status_code == 200 and "image/svg+xml" in qr.headers["content-type"]
    assert qr.headers["cache-control"] == "no-store"
    for url in [
        "http://bad.test",
        "https://a:b@bad.test",
        "https://ok.test/?project=p",
        "https://ok.test/#secret",
        "https://ok.test/path",
    ]:
        with pytest.raises(ValueError):
            validate_public_url(url)
    validate_public_url("https://ok.test")


async def test_idempotency_rejects_changed_payload(public_server):
    a, _, _, _ = public_server
    await login(a)
    body = {"script": "original", "idempotency_key": "same"}
    pid = (await a.post("/api/projects", json=body)).json()["id"]
    conflict = await a.post("/api/projects", json={**body, "script": "changed"})
    assert conflict.status_code == 409
    first = await a.post(
        f"/api/projects/{pid}/jobs", json={"kind": "analyze", "idempotency_key": "same-job"}
    )
    assert first.status_code == 200
    conflict = await a.post(
        f"/api/projects/{pid}/jobs",
        json={
            "kind": "analyze",
            "idempotency_key": "same-job",
            "auto_verify_and_repair": True,
        },
    )
    assert conflict.status_code == 409


def test_public_startup_fails_without_valid_encrypted_key(public_server, tmp_path, monkeypatch):
    from app.config import api_key_for
    from app.web import prepare_public_runtime

    config = get_config()
    profile = config.llm.profiles[config.llm.default_profile]
    monkeypatch.delenv("LLM_API_KEY_ENCRYPTED", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "plaintext-test")
    with pytest.raises(ValueError, match="加密"):
        api_key_for(profile)
    with pytest.raises(ValueError):
        prepare_public_runtime()
    key = tmp_path / "master.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    monkeypatch.setenv("STORYBRIDGE_MASTER_KEY_FILE", str(key))
    monkeypatch.setenv(
        "LLM_API_KEY_ENCRYPTED", Fernet(key.read_bytes()).encrypt(b"private-test").decode()
    )
    assert api_key_for(profile) == "private-test"
    prepare_public_runtime()
    key.unlink()
    with pytest.raises(ValueError):
        prepare_public_runtime()


async def test_same_origin_static_site_keeps_api_routes_and_hides_server_files(
    public_server, tmp_path, monkeypatch
):
    from fastapi import FastAPI

    from app.api.routes import router
    from app.web import install_web

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "assets").mkdir()
    (dist / "index.html").write_text("<html>StoryBridge website</html>")
    (dist / "assets/site.css").write_text("body { color: black; }")
    monkeypatch.setenv("STORYBRIDGE_SERVE_FRONTEND", "1")
    monkeypatch.setenv("STORYBRIDGE_FRONTEND_DIR", str(dist))
    website = FastAPI()
    website.state.workflow = app.state.workflow
    website.state.jobs = app.state.jobs
    website.include_router(router)
    install_web(website)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=website), base_url="https://stories.test"
    ) as client:
        assert "StoryBridge website" in (await client.get("/")).text
        assert (await client.get("/assets/site.css")).status_code == 200
        assert (await client.get("/.env")).status_code == 404
        assert (await client.get("/api/not-an-endpoint")).status_code == 404
        await login(client)
        assert (await client.get("/api/demo-scripts")).status_code == 200
