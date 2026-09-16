"""Opt-in real model acceptance using an edited demo and the public HTTP API.

Run from backend: .venv/bin/python -m scripts.acceptance_smoke
Consumes real model tokens; records them in the normal durable site ledger.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import httpx


async def main(option: str = "B") -> None:
    from app.secrets import migrate

    root = Path(__file__).resolve().parents[2]
    migrate(root / "backend/.env")
    os.environ["STORYBRIDGE_SHARE"] = "1"
    os.environ.setdefault("STORYBRIDGE_PUBLIC_URL", "https://acceptance.storybridge.invalid")
    from app.config import get_config
    from app.main import app

    url = get_config().share.public_url
    result = {"stages": [], "passed": False}
    output = root / f".storybridge/acceptance-real-{option}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=url
        ) as client:
            session = await client.post("/api/session", headers={"Origin": url})
            session.raise_for_status()
            client.headers.update({"Origin": url, "X-CSRF-Token": session.json()["csrf_token"]})
            demo = (await client.get("/api/demo-scripts/meet_the_parents")).json()
            edited = (
                demo["text"]
                + "\n【补充结尾】小陈和女友决定共同承担新家庭的开支，每个月公开一次收支。"
            )
            created = await client.post(
                "/api/projects",
                json={
                    "name": "真实验收：修改后的拜见岳父大人",
                    "script": edited,
                    "idempotency_key": uuid.uuid4().hex,
                    "market": {
                        "market": "United States",
                        "target_language": "English",
                        "target_locale": "en-US",
                    },
                },
            )
            created.raise_for_status()
            pid = created.json()["id"]
            result["project_id"] = pid

            async def run(kind, **body):
                response = await client.post(
                    f"/api/projects/{pid}/jobs",
                    json={"kind": kind, "idempotency_key": uuid.uuid4().hex, **body},
                )
                response.raise_for_status()
                jid = response.json()["job_id"]
                print(f"{kind}: started", flush=True)
                while True:
                    status = (await client.get(f"/api/jobs/{jid}")).json()
                    if status["status"] in {"done", "failed", "cancelled"}:
                        result["stages"].append(
                            {
                                "stage": kind,
                                "status": status["status"],
                                "error_code": status.get("error_code"),
                            }
                        )
                        if status["status"] != "done":
                            raise RuntimeError(f"{kind}: {status.get('error')}")
                        print(f"{kind}: done", flush=True)
                        return status["result"]
                    await asyncio.sleep(1)

            try:
                state = await run("analyze")
                mechanisms = state["culture_mechanisms"]
                if mechanisms:
                    point = next(
                        (p for p in mechanisms if p["friction_level"] == "high"), mechanisms[0]
                    )
                    await run("plan_batch", culture_mechanism_ids=[point["id"]])
                    await run(
                        "apply_batch",
                        based_on_version=state["version"],
                        auto_verify_and_repair=False,
                        adaptations=[{"culture_mechanism_id": point["id"], "option_label": option}],
                    )
                report = await run("verify")
                result["verification"] = report
                if report["overall_status"] in {"not_run", "fail"}:
                    raise RuntimeError(
                        "Verification blocked target generation; review saved report."
                    )
                target = await run("render")
                result["passed"] = True
                result["scene_count"] = len(target["scenes"])
                (root / f".storybridge/acceptance-real-{option}.txt").write_text(
                    "\n\n".join(f"{s['title']}\n{s['text']}" for s in target["scenes"]),
                    encoding="utf-8",
                )
            finally:
                result["policy"] = (await client.get("/api/runtime-policy")).json()
                output.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                print("Acceptance metadata saved; passed=" + str(result["passed"]), flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--option", choices=["A", "B", "C"], default="B")
    asyncio.run(main(parser.parse_args().option))
