"""Second paired run: localize both the education setting and score-swap system."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRIOR = HERE / "rebirth_16k/evidence"
CASE = HERE / "rebirth_system_16k"
EVIDENCE = CASE / "evidence"
RUNTIME = CASE / "runtime"
SOURCE = REPO / "backend/data/scripts/corpus_rebirth.md"
sys.path.insert(0, str(REPO / "backend"))

for key, relative in (("DATABASE_FILE", "storybridge.sqlite3"), ("PROJECTS_DIR", "projects"), ("RUN_LOG_DIR", "run_logs"), ("JOBS_FILE", "jobs.json")):
    os.environ[f"STORYBRIDGE_{key}"] = str(RUNTIME / relative)

from app.config import get_config
from app.llm import build_router
from app.llm.base import LLMRequest
from app.schemas import AdaptationPlan, StoryState
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile
from app.workflow.engine import AdaptationSelection, StoryBridgeWorkflow


REQUIREMENTS = """把完整十二场重生悬疑短剧改编为美国背景和英语成稿，同时本土化教育体系与换分系统，而不是只替换“高考”。

硬性要求：
- 保持 S01-S12 与原顺序，不合并、不拆分。
- 不使用“前程卡”，不添加仪式、百日用笔等新规则。借笔本身仍是触发系统识别借笔人与被借笔人的锚点。
- “易分系统”不是必须保留的名字或中国统分后台；把它替换为适合新教育背景的虚构技术平台、黑箱模块或数据机制，并同步日志字段、取证方式、庭审说法和结尾称呼。
- 保留功能：沈曼主动借笔并误换周雨；林知夏 669 不变，周雨原 330、换后 487，沈曼原 487、换后 330；沈曼说漏嘴“你明明只有330”；离线日志能证明错误目标；最后恢复卷面成绩，系统威胁仍未完全消失。
- 保留原稿的人物知情顺序、周雨与林知夏的冲突、天台收网、老宋协助、庭审与开放式尾声。
- 所有学校、考试、公司、政府与司法机构均为虚构，避免使用 College Board 等真实机构。
- 台词简短、动作可拍，类型为 rebirth suspense revenge vertical drama。
"""


def dump(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Recorder:
    def __init__(self, inner, group): self.inner, self.group = inner, group
    def profile_for_step(self, step): return self.inner.profile_for_step(step)
    async def complete(self, request):
        started = time.monotonic()
        response = await self.inner.complete(request)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        row = {"timestamp": datetime.now(timezone.utc).isoformat(), "group": self.group, "request": asdict(request), "response": asdict(response), "seconds": round(time.monotonic()-started, 3)}
        with (EVIDENCE/"calls.jsonl").open("a", encoding="utf-8") as handle: handle.write(json.dumps(row, ensure_ascii=False)+"\n")
        print(self.group, request.step, f"{row['seconds']:.1f}s", flush=True)
        return response


def profile() -> MarketProfile:
    return MarketProfile(market="United States", audience="18-35 vertical-drama viewers", format="12-scene vertical short drama", genre="Rebirth suspense revenge drama", source_language="zh-CN", target_language="English", target_locale="en-US", style_guide=REQUIREMENTS, terminology_map={"林知夏":"Lin Zhixia","沈曼":"Shen Man","周雨":"Zhou Yu","老宋":"Old Song"})


def workflow(group: str):
    config = get_config(); config.llm.profiles[config.llm.default_profile].max_tokens = 16_384
    for step in config.llm.step_routes: config.llm.step_routes[step] = config.llm.default_profile
    client = Recorder(build_router(), group)
    store = SQLiteProjectStore(RUNTIME/"storybridge.sqlite3", RUNTIME/"projects")
    return StoryBridgeWorkflow(store, client)


async def prepare():
    if (EVIDENCE/"plans.json").exists(): raise RuntimeError("already prepared")
    state = StoryState.model_validate(load(PRIOR/"base_state.json"))
    state.style_guide = REQUIREMENTS
    state.target_market = "United States"; state.target_language = "English"; state.target_locale = "en-US"
    wf = workflow("system_prepare")
    project = await wf.create_project("她换走了我的分数 · 教育与系统联合改编", SOURCE.read_text(encoding="utf-8"), profile())
    wf.store.save_state(project.id, state, kind="initial_parse", description="Reused frozen parse; changed only target adaptation requirements")
    mechanism_ids = ["CM01", "CM02", "CM10"]
    plans = []
    for mechanism_id in mechanism_ids:
        plans.append(await wf.plan(project.id, mechanism_id))
    dump(EVIDENCE/"project.json", project.model_dump(mode="json"))
    dump(EVIDENCE/"base_state.json", wf.require_state(project.id).model_dump(mode="json"))
    dump(EVIDENCE/"plans.json", [plan.model_dump(mode="json") for plan in plans])
    dump(EVIDENCE/"protocol.json", {"model":get_config().llm.profile_for_step("rewrite_scene").model,"max_tokens":16384,"mechanisms":mechanism_ids,"requirements":REQUIREMENTS,"source":"Same frozen 12-scene demo and parsed state as rebirth_16k"})
    print("PREPARED", project.id, mechanism_ids, flush=True)


async def apply(label: str):
    label = label.upper()
    if label not in {"B","C","D"}: raise ValueError("B, C, or D")
    if (EVIDENCE/f"option_{label.lower()}_target.json").exists(): raise RuntimeError("already complete")
    state = StoryState.model_validate(load(EVIDENCE/"base_state.json"))
    plans = [AdaptationPlan.model_validate(item) for item in load(EVIDENCE/"plans.json")]
    wf = workflow(f"system_{label.lower()}")
    project = await wf.create_project(f"教育与换分系统联合改编 · {label}", SOURCE.read_text(encoding="utf-8"), profile())
    wf.store.save_state(project.id, state, kind="initial_parse", description="Exact clone for paired multi-mechanism run")
    current = wf.require_state(project.id)
    for plan in plans:
        plan.based_on_version = current.version
        wf.store.save_plan(project.id, plan)
    if label == "D":
        # Reviewed combination: localize the education-data environment and its
        # black-box module, while leaving the source score-exchange mechanism
        # intact instead of accepting CM02-C's admission-result reconstruction.
        selections = [
            AdaptationSelection(culture_mechanism_id="CM01", option_label="C"),
            AdaptationSelection(culture_mechanism_id="CM10", option_label="C"),
        ]
    else:
        selections = [AdaptationSelection(culture_mechanism_id=plan.culture_mechanism_id, option_label=label) for plan in plans]
    result = await wf.apply_adaptations(project.id, selections, based_on_version=current.version)
    target = await wf.render_target_script(project.id)
    dump(EVIDENCE/f"option_{label.lower()}_project.json", project.model_dump(mode="json"))
    dump(EVIDENCE/f"option_{label.lower()}_apply.json", result.model_dump(mode="json"))
    dump(EVIDENCE/f"option_{label.lower()}_state.json", wf.require_state(project.id).model_dump(mode="json"))
    dump(EVIDENCE/f"option_{label.lower()}_target.json", target.model_dump(mode="json"))
    print("COMPLETE", label, result.report.overall_status, result.repaired_scene_ids, flush=True)


async def baseline():
    if (EVIDENCE/"baseline_first_response.md").exists(): raise RuntimeError("baseline already frozen")
    plans = load(EVIDENCE/"plans.json")
    selected = []
    for mechanism_id in ("CM01", "CM10"):
        plan = next(p for p in plans if p["culture_mechanism_id"] == mechanism_id)
        selected.append(next(o for o in plan["options"] if o["option_label"] == "C"))
    request = LLMRequest(
        step="baseline_naive_full",
        system_prompt="You are a professional screenwriter.",
        user_prompt="Directly adapt the complete source into one complete American-English screenplay. Follow every requirement and both selected StoryBridge options. Return S01-S12 exactly once and in order. Do not merge or omit scenes.\n\n[COMPLETE SOURCE]\n"+SOURCE.read_text(encoding="utf-8")+"\n\n[COMPLETE REQUIREMENTS]\n"+REQUIREMENTS+"\n\n[SELECTED OPTIONS]\n"+json.dumps(selected,ensure_ascii=False,indent=2),
        json_mode=False,
    )
    dump(EVIDENCE/"baseline_protocol.json", {"model":get_config().llm.profile_for_step("baseline_naive_full").model,"max_tokens":16384,"policy":"Freeze first complete response; retry only for technical failure or incomplete S01-S12.","request":asdict(request)})
    wf = workflow("system_baseline")
    response = await wf.rewriter.client.complete(request)
    dump(EVIDENCE/"baseline_first_response.json", asdict(response))
    (EVIDENCE/"baseline_first_response.md").write_text(response.text,encoding="utf-8")
    headings=re.findall(r"(?im)^\s*(?:#{1,4}\s*)?(?:\*{1,2})?\[?(S\d{2})\b",response.text);expected=[f"S{i:02d}" for i in range(1,13)]
    dump(EVIDENCE/"baseline_validation.json",{"finish_reason":response.finish_reason,"headings":headings,"expected":expected,"complete":response.finish_reason!="length" and headings==expected})
    if response.finish_reason=="length" or headings!=expected: raise RuntimeError("baseline incomplete; first response preserved")
    print("BASELINE COMPLETE",response.finish_reason,flush=True)


async def main():
    if len(sys.argv)==2 and sys.argv[1]=="prepare": await prepare()
    elif len(sys.argv)==3 and sys.argv[1]=="apply": await apply(sys.argv[2])
    elif len(sys.argv)==2 and sys.argv[1]=="baseline": await baseline()
    else: raise SystemExit("prepare | apply B|C|D")


if __name__ == "__main__": asyncio.run(main())
