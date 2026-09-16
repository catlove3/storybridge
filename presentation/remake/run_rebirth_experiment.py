"""Frozen, auditable B/C and whole-script baseline run for the rebirth demo."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE / "rebirth_16k"
EVIDENCE = CASE / "evidence"
RUNTIME = CASE / "runtime"
SOURCE_PATH = REPO / "backend/data/scripts/corpus_rebirth.md"
sys.path.insert(0, str(REPO / "backend"))

for key, relative in (
    ("DATABASE_FILE", "storybridge.sqlite3"),
    ("PROJECTS_DIR", "projects"),
    ("RUN_LOG_DIR", "run_logs"),
    ("JOBS_FILE", "jobs.json"),
):
    os.environ[f"STORYBRIDGE_{key}"] = str(RUNTIME / relative)

from app.config import get_config
from app.llm import build_router
from app.llm.base import LLMRequest
from app.privacy import project_data_context
from app.schemas import AdaptationPlan, StoryState
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile, ProjectMeta
from app.workflow.engine import StoryBridgeWorkflow


REQUIREMENTS = """把这部虚构的十二场中国重生悬疑短剧改编成美国背景、英语成稿。

硬性要求：
1. 保持 S01-S12 十二场及顺序，不合并、不拆分。
2. 保留原稿的“易分系统”及系统日志；观众可以相信系统存在，不要另造前程卡、仪式、百日用笔等解释规则。
3. 笔仍是系统识别借笔人与被借笔人的锚点。林知夏把周雨落下的笔递给沈曼，沈曼误以为换到了林知夏。
4. 分数关系保持清楚：林知夏 669 不变；周雨原本 330、换后 487；沈曼原本 487、换后 330。
5. 保留沈曼的说漏嘴：“你明明只有330！”周雨追问她为什么提前知道。
6. 保留原稿的人物知情顺序、周雨与林知夏的冲突、天台收网、老宋的离线日志、庭审、恢复卷面分与开放式系统尾声。
7. 改编重点是让美国观众理解教育与录取背景，可替换高考/志愿/复核等文化机制；不得把真实学校、考试机构或司法制度写成事实。所有机构均为虚构。
8. 台词简短、动作可拍，风格为 rebirth suspense revenge vertical drama。
"""


def dump(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing to overwrite frozen artifact: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_inputs() -> None:
    CASE.mkdir(parents=True, exist_ok=True)
    source_copy = CASE / "source_demo.md"
    change_list = CASE / "change_list.md"
    if not source_copy.exists():
        source_copy.write_text(SOURCE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    if not change_list.exists():
        change_list.write_text(
            "# Demo 稿修改清单\n\n"
            "仅在原十二场稿上落实以下两点，不添加新的换分规则：\n\n"
            "- 周雨卷面原始分为 330；易分系统交换后周雨 487、沈曼 330，林知夏仍为 669。\n"
            "- S07 加入沈曼抢过周雨手机后说漏嘴：‘你明明只有330！’周雨追问她为何知道原始分。\n\n"
            "StoryBridge 与 baseline 共用完整 `source_demo.md`、本清单、美国市场和英语输出要求。\n",
            encoding="utf-8",
        )


class Recorder:
    def __init__(self, inner, group: str):
        self.inner = inner
        self.group = group

    def profile_for_step(self, step):
        return self.inner.profile_for_step(step)

    async def complete(self, request):
        started = time.monotonic()
        try:
            response = await self.inner.complete(request)
        except Exception as exc:
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            with (EVIDENCE / "failures.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "group": self.group,
                    "step": request.step,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "seconds": round(time.monotonic() - started, 3),
                }, ensure_ascii=False) + "\n")
            raise
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "group": self.group,
            "request": asdict(request),
            "response": asdict(response),
            "seconds": round(time.monotonic() - started, 3),
        }
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        with (EVIDENCE / "calls.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(self.group, request.step, f"{row['seconds']:.1f}s", flush=True)
        return response


def make_workflow(group: str) -> tuple[StoryBridgeWorkflow, Recorder]:
    config = get_config()
    config.llm.profiles[config.llm.default_profile].max_tokens = 16_384
    for step in config.llm.step_routes:
        config.llm.step_routes[step] = config.llm.default_profile
    client = Recorder(build_router(), group)
    store = SQLiteProjectStore(RUNTIME / "storybridge.sqlite3", RUNTIME / "projects")
    workflow = StoryBridgeWorkflow(store, client)
    if group == "storybridge_prepare":
        workflow.parser.chunk_threshold_chars = 2_000
        workflow.parser.chunk_chars = 1_400
    return workflow, client


def market() -> MarketProfile:
    return MarketProfile(
        market="United States",
        audience="18-35 vertical-drama viewers",
        format="12-scene vertical short drama",
        genre="Rebirth suspense revenge drama",
        source_language="zh-CN",
        target_language="English",
        target_locale="en-US",
        style_guide=REQUIREMENTS,
        terminology_map={"林知夏": "Lin Zhixia", "沈曼": "Shen Man", "周雨": "Zhou Yu", "老宋": "Old Song"},
    )


def mechanism_rank(item: dict) -> tuple[int, int, int]:
    text = " ".join([item.get("name", ""), item.get("description", ""), *item.get("surface_text", [])])
    keywords = ("高考", "志愿", "统分", "复核", "录取", "名校")
    hits = sum(word in text for word in keywords)
    importance = {"high": 2, "medium": 1, "low": 0}.get(item.get("narrative_importance"), 0)
    return hits, importance, len(item.get("scene_ids", []))


async def prepare() -> None:
    snapshot_inputs()
    if (EVIDENCE / "plan.json").exists():
        raise RuntimeError("prepare phase already completed")
    wf, _ = make_workflow("storybridge_prepare")
    source = (CASE / "source_demo.md").read_text(encoding="utf-8")
    project = await wf.create_project("她换走了我的高考 · 美国市场改编", source, market())
    state = await wf.analyze(project.id)
    expected = [f"S{i:02d}" for i in range(1, 13)]
    actual = [scene.id for scene in state.scenes]
    if actual != expected:
        dump(EVIDENCE / "invalid_parse.json", state.model_dump(mode="json"))
        raise RuntimeError(f"expected S01-S12, got {actual}")
    mechanisms = [item.model_dump(mode="json") for item in state.culture_mechanisms]
    ranked = sorted(mechanisms, key=mechanism_rank, reverse=True)
    if not ranked or mechanism_rank(ranked[0])[0] == 0:
        dump(EVIDENCE / "invalid_parse.json", state.model_dump(mode="json"))
        raise RuntimeError("no gaokao/admissions cultural mechanism detected")
    mechanism_id = ranked[0]["id"]
    plan = await wf.plan(project.id, mechanism_id)
    propagation = wf.propagate(project.id, mechanism_id)
    config = get_config()
    dump(EVIDENCE / "protocol.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "requirements": REQUIREMENTS,
        "model": config.llm.profile_for_step("rewrite_scene").model,
        "max_tokens": config.llm.profile_for_step("rewrite_scene").max_tokens,
        "same_input_policy": "B and C are cloned from this exact state and plan.",
        "selected_mechanism": ranked[0],
    })
    dump(EVIDENCE / "base_project.json", project.model_dump(mode="json"))
    dump(EVIDENCE / "base_state.json", state.model_dump(mode="json"))
    dump(EVIDENCE / "plan.json", plan.model_dump(mode="json"))
    dump(EVIDENCE / "propagation.json", propagation.model_dump(mode="json"))
    print("PREPARED", project.id, mechanism_id, flush=True)


async def replan_core() -> None:
    """Select the broad gaokao mechanism after reviewing the saved pre-plan."""
    if (EVIDENCE / "plan_core.json").exists():
        raise RuntimeError("core replan already completed")
    project = ProjectMeta.model_validate(load(EVIDENCE / "base_project.json"))
    state = StoryState.model_validate(load(EVIDENCE / "base_state.json"))
    candidates = [
        mechanism for mechanism in state.culture_mechanisms
        if mechanism.name == "高考" or "高考" in mechanism.surface_text
    ]
    if not candidates:
        raise RuntimeError("parsed state has no explicit gaokao mechanism")
    mechanism = max(candidates, key=lambda item: len(item.scene_ids))
    preselected = load(EVIDENCE / "protocol.json")["selected_mechanism"]
    if preselected["id"] == mechanism.id:
        plan = AdaptationPlan.model_validate(load(EVIDENCE / "plan.json"))
        propagation_payload = load(EVIDENCE / "propagation.json")
    else:
        wf, _ = make_workflow("storybridge_replan_core")
        # Reuse the exact persisted base project and state; no second parse.
        plan = await wf.plan(project.id, mechanism.id)
        propagation_payload = wf.propagate(project.id, mechanism.id).model_dump(mode="json")
    dump(EVIDENCE / "plan_core.json", plan.model_dump(mode="json"))
    dump(EVIDENCE / "propagation_core.json", propagation_payload)
    dump(EVIDENCE / "mechanism_selection.json", {
        "preselected": preselected,
        "selected": mechanism.model_dump(mode="json"),
        "reason": "The broad gaokao node is the core story mechanism and touches S01-S08; the first score-review node was too narrow for the planned end-to-end demo.",
        "same_parsed_state": True,
    })
    print("REPLANNED", mechanism.id, mechanism.name, mechanism.scene_ids, flush=True)


async def apply(label: str) -> None:
    label = label.upper()
    if label not in {"B", "C"}:
        raise ValueError("option must be B or C")
    target_path = EVIDENCE / f"option_{label.lower()}_target.json"
    if target_path.exists():
        raise RuntimeError(f"option {label} already completed")
    base = StoryState.model_validate(load(EVIDENCE / "base_state.json"))
    plan = AdaptationPlan.model_validate(load(EVIDENCE / "plan_core.json"))
    wf, _ = make_workflow(f"storybridge_{label.lower()}")
    project = await wf.create_project(f"她换走了我的高考 · 方案 {label}", (CASE / "source_demo.md").read_text(encoding="utf-8"), market())
    wf.store.save_state(project.id, base.model_copy(deep=True), kind="initial_parse", description="Exact clone for paired B/C run")
    initial = wf.require_state(project.id)
    plan.based_on_version = initial.version
    wf.store.save_plan(project.id, plan)
    result = await wf.apply_adaptation(project.id, plan.culture_mechanism_id, label, based_on_version=initial.version)
    final_state = wf.require_state(project.id)
    target = await wf.render_target_script(project.id)
    dump(EVIDENCE / f"option_{label.lower()}_project.json", project.model_dump(mode="json"))
    dump(EVIDENCE / f"option_{label.lower()}_apply.json", result.model_dump(mode="json"))
    dump(EVIDENCE / f"option_{label.lower()}_state.json", final_state.model_dump(mode="json"))
    dump(target_path, target.model_dump(mode="json"))
    print("COMPLETE", label, result.report.overall_status, result.applied.rewritten_scene_ids, flush=True)


async def baseline(selected_label: str) -> None:
    selected_label = selected_label.upper()
    if (EVIDENCE / "baseline_first_response.md").exists():
        raise RuntimeError("baseline first response already frozen")
    plan = load(EVIDENCE / "plan_core.json")
    option = next(item for item in plan["options"] if item["option_label"] == selected_label)
    source = (CASE / "source_demo.md").read_text(encoding="utf-8")
    payload = {"market": market().model_dump(mode="json"), "requirements": REQUIREMENTS, "selected_option": option}
    request = LLMRequest(
        step="baseline_naive_full",
        system_prompt="You are a professional screenwriter.",
        user_prompt=(
            "Directly adapt the complete source into one complete American-English screenplay. "
            "Follow all requirements and the selected creative option. Return S01-S12 exactly once and in order; "
            "do not merge or omit scenes. You may append a short adaptation note.\n\n"
            "[COMPLETE SOURCE]\n" + source + "\n\n[COMPLETE TASK]\n" + json.dumps(payload, ensure_ascii=False, indent=2)
        ),
        json_mode=False,
    )
    config = get_config()
    dump(EVIDENCE / "baseline_protocol.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": config.llm.profile_for_step("baseline_naive_full").model,
        "max_tokens": config.llm.profile_for_step("baseline_naive_full").max_tokens,
        "policy": "Freeze the first complete response. Retry only for transport failure, truncation, or missing/duplicate S01-S12, and retain every attempt.",
        "request": asdict(request),
    })
    (EVIDENCE / "baseline_prompt.md").write_text("# System\n\n" + request.system_prompt + "\n\n# User\n\n" + request.user_prompt, encoding="utf-8")
    _, client = make_workflow("baseline_full")
    meta = ProjectMeta.model_validate(load(EVIDENCE / "base_project.json"))
    with project_data_context(meta.id, meta.data_policy):
        response = await client.complete(request)
    dump(EVIDENCE / "baseline_first_response.json", asdict(response))
    (EVIDENCE / "baseline_first_response.md").write_text(response.text, encoding="utf-8")
    headings = re.findall(r"(?im)^#{0,4}\s*\[?(S\d{2})\b", response.text)
    expected = [f"S{i:02d}" for i in range(1, 13)]
    valid = response.finish_reason != "length" and headings == expected
    dump(EVIDENCE / "baseline_validation.json", {"finish_reason": response.finish_reason, "headings": headings, "expected": expected, "complete": valid})
    if not valid:
        raise RuntimeError("first baseline response is incomplete; frozen and requires a logged technical retry")
    print("BASELINE COMPLETE", response.finish_reason, flush=True)


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("prepare | replan | apply B|C | baseline B|C")
    if sys.argv[1] == "prepare":
        await prepare()
    elif sys.argv[1] == "replan":
        await replan_core()
    elif sys.argv[1] == "apply" and len(sys.argv) == 3:
        await apply(sys.argv[2])
    elif sys.argv[1] == "baseline" and len(sys.argv) == 3:
        await baseline(sys.argv[2])
    else:
        raise SystemExit("prepare | replan | apply B|C | baseline B|C")


if __name__ == "__main__":
    asyncio.run(main())
