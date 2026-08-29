from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.baselines.runner import BaselineRunner, EvalAnnotations, save_experiment
from app.config import get_config
from app.export.bible import export_bible
from app.llm import MockLLMClient, build_router
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile
from app.workflow.engine import StoryBridgeWorkflow, build_default_workflow


def _rewrite_echo_handler(request) -> str:
    import json as _json
    import re

    if request.step == "plan_adaptation":
        fixture_path = (
            Path(__file__).resolve().parent.parent
            / "tests"
            / "fixtures"
            / "plan_adaptation.json"
        )
        payload = _json.loads(fixture_path.read_text(encoding="utf-8"))
        mechanism_id = re.search(r'"id": "(CM\d+)"', request.user_prompt)
        mechanism_name = re.search(r'"name": "([^"]+)"', request.user_prompt)
        if mechanism_id:
            payload["culture_mechanism_id"] = mechanism_id.group(1)
        if mechanism_name:
            payload["original_name"] = mechanism_name.group(1)
        return _json.dumps(payload, ensure_ascii=False)

    if request.step == "render_target_script":
        scene_ids = list(dict.fromkeys(re.findall(r'"id": "(S\d+)"', request.user_prompt)))
        target_match = re.search(r"目标语言：([^\n]+)", request.user_prompt)
        target_language = target_match.group(1).strip() if target_match else "English"
        return _json.dumps(
            {
                "source_language": "zh-CN",
                "target_language": target_language,
                "target_locale": "en-US",
                "scenes": [
                    {
                        "id": scene_id,
                        "title": f"{scene_id} target",
                        "summary": f"Target-language summary for {scene_id}",
                        "text": f"[TARGET {scene_id}] localized target-language scene",
                    }
                    for scene_id in scene_ids
                ],
            },
            ensure_ascii=False,
        )

    match = re.search(r'"id": "(S\d+)"', request.user_prompt)
    scene_id = match.group(1) if match else "S01"
    return _json.dumps(
        {
            "id": scene_id,
            "title": f"{scene_id} adapted",
            "summary": f"[REWRITTEN-SUMMARY {scene_id}]",
            "text": f"[REWRITTEN {scene_id}] localized career-stability version",
        },
        ensure_ascii=False,
    )


def _load_default_mock_fixtures(client: MockLLMClient) -> None:
    fixture_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    for step in ("parse_story", "detect_frictions", "plan_adaptation", "verify_consistency"):
        path = fixture_dir / f"{step}.json"
        if path.exists():
            client.set_response(step, json.loads(path.read_text(encoding="utf-8")))
    client.handler = _rewrite_echo_handler


def _workflow(mock: bool, mock_responses: str | None) -> StoryBridgeWorkflow:
    if mock:
        client = MockLLMClient()
        if mock_responses:
            payload = json.loads(Path(mock_responses).read_text(encoding="utf-8"))
            for step, spec in payload.items():
                client.set_response(step, spec)
        else:
            _load_default_mock_fixtures(client)
        config = get_config()
        store = SQLiteProjectStore(
            config.storage.database_file,
            artifacts_dir=config.storage.projects_dir,
        )
        store.import_legacy_projects(config.storage.projects_dir)
        return StoryBridgeWorkflow(store, client)
    return build_default_workflow(build_router())


def _json_object_file(path: str | None) -> dict:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


def _market_profile(args) -> MarketProfile:
    return MarketProfile(
        market=args.market,
        audience=getattr(args, "audience", ""),
        format=getattr(args, "format", ""),
        genre=getattr(args, "genre", ""),
        source_language=args.source_language,
        target_language=args.target_language,
        target_locale=args.target_locale,
        style_guide=getattr(args, "style_guide", ""),
        terminology_map=_json_object_file(getattr(args, "terminology_map", None)),
    )


def _adaptation_plans(values: list[str]) -> list[tuple[str, str]]:
    plans: list[tuple[str, str]] = []
    for value in values:
        parts = value.strip().split(":", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"invalid plan {value!r}; expected MECHANISM_ID:OPTION_LABEL")
        plans.append((parts[0], parts[1]))
    return plans


def _add_localization_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-language", default="zh-CN")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--target-locale", default="en-US")
    parser.add_argument("--style-guide", default="")
    parser.add_argument(
        "--terminology-map",
        default=None,
        metavar="JSON_FILE",
        help="JSON object mapping frozen source terms to target-language terms",
    )


async def cmd_create(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    script = Path(args.script).read_text(encoding="utf-8") if args.script else sys.stdin.read()
    meta = await workflow.create_project(args.name, script, _market_profile(args))
    print(json.dumps({"id": meta.id}, ensure_ascii=False))


async def cmd_analyze(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    state = await workflow.analyze(args.project_id)
    print(
        json.dumps(
            {
                "scenes": len(state.scenes),
                "characters": len(state.characters),
                "mechanisms": [
                    {"id": cm.id, "name": cm.name, "friction": cm.friction_level.value}
                    for cm in state.culture_mechanisms
                ],
                "commitments": len(state.commitments),
                "dependencies": len(state.dependencies),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def cmd_propagate(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    result = workflow.propagate(args.project_id, args.mechanism)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


async def cmd_plan(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    plan = await workflow.plan(args.project_id, args.mechanism)
    print(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2))


async def cmd_apply(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    result = await workflow.apply_adaptation(args.project_id, args.mechanism, args.option)
    payload = result.model_dump()
    payload["summary"] = {
        "affected": [a.scene_id for a in result.applied.propagation.affected_scenes],
        "rewritten": result.applied.rewritten_scene_ids,
        "repair_rounds": result.repair_rounds,
        "status": result.report.overall_status,
        "score": result.report.consistency_score,
        "coverage": {
            "static_checks": f"{result.report.static_checks_passed}/{result.report.static_checks_total}",
            "commitments": f"{result.report.commitments_verified}/{result.report.commitments_total}",
            "scenes": f"{result.report.scenes_checked}/{result.report.scenes_total}",
        },
    }
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


async def cmd_verify(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    report = await workflow.verify(args.project_id)
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


async def cmd_bible(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    path = export_bible(workflow, args.project_id, Path(args.out))
    print(f"saved: {path}")


async def cmd_render(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    target = await workflow.render_target_script(args.project_id)
    text = (
        json.dumps(target.model_dump(), ensure_ascii=False, indent=2)
        if args.json
        else target.text
    )
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"saved: {args.out}")
    else:
        print(text)


async def cmd_baseline(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    script = Path(args.script).read_text(encoding="utf-8")
    plans = _adaptation_plans(args.plans)
    annotations = None
    if args.annotations:
        payload = _json_object_file(args.annotations)
        payload.setdefault("source", Path(args.annotations).name)
        annotations = EvalAnnotations.model_validate(payload)
    runner = BaselineRunner(workflow, workflow.rewriter.client)
    result = await runner.run_experiment(
        args.name, script, plans, _market_profile(args), annotations=annotations
    )
    save_experiment(result, Path(args.out_dir))
    from app.baselines.metrics import format_metrics_table

    print(format_metrics_table(result.metrics))


async def cmd_demo(args) -> None:
    workflow = _workflow(args.mock, args.mock_responses)
    script = Path(args.script).read_text(encoding="utf-8")
    meta = await workflow.create_project(
        "cli-demo", script, MarketProfile(market="United States", audience="18-30")
    )
    print(f"[1/5] created project {meta.id}")
    state = await workflow.analyze(meta.id)
    print(f"[2/5] analyzed: {len(state.scenes)} scenes, {len(state.culture_mechanisms)} mechanisms")
    target = next(
        (cm for cm in state.culture_mechanisms if cm.friction_level.value == "high"),
        state.culture_mechanisms[0],
    )
    print(f"[3/5] planning for {target.id} ({target.name})")
    await workflow.plan(meta.id, target.id)
    result = await workflow.apply_adaptation(meta.id, target.id, "B")
    print(
        f"[4/5] applied B: affected={result.applied.propagation.summary}, "
        f"repair_rounds={result.repair_rounds}"
    )
    print(
        f"[5/5] status={result.report.overall_status}, "
        f"consistency_score={result.report.consistency_score}, "
        f"scene_coverage={result.report.scenes_checked}/{result.report.scenes_total}"
    )
    if args.bible:
        path = export_bible(workflow, meta.id, Path(args.bible))
        print(f"bible: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storybridge")
    parser.add_argument("--mock", action="store_true", help="use MockLLMClient (offline)")
    parser.add_argument(
        "--mock-responses", default=None, help="JSON file of canned responses for mock"
    )
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("create")
    p.add_argument("script")
    p.add_argument("--name", default="")
    p.add_argument("--market", default="")
    p.add_argument("--audience", default="")
    p.add_argument("--format", default="")
    p.add_argument("--genre", default="")
    _add_localization_args(p)
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("analyze")
    p.add_argument("project_id")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("propagate")
    p.add_argument("project_id")
    p.add_argument("mechanism")
    p.set_defaults(func=cmd_propagate)

    p = sub.add_parser("plan")
    p.add_argument("project_id")
    p.add_argument("mechanism")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("apply")
    p.add_argument("project_id")
    p.add_argument("mechanism")
    p.add_argument("option")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("verify")
    p.add_argument("project_id")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("bible")
    p.add_argument("project_id")
    p.add_argument("out")
    p.set_defaults(func=cmd_bible)

    p = sub.add_parser("render")
    p.add_argument("project_id")
    p.add_argument("--out", default=None)
    p.add_argument("--json", action="store_true", help="emit the structured artifact")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("baseline")
    p.add_argument("script")
    p.add_argument("--name", default="experiment")
    p.add_argument("--market", default="United States")
    p.add_argument("--plans", nargs="+", required=True, help="e.g. CM01:B CM02:B")
    p.add_argument(
        "--annotations",
        default=None,
        metavar="JSON_FILE",
        help="human expected_affected_ids and forbidden_target_terms",
    )
    p.add_argument("--out-dir", default="data/baselines")
    _add_localization_args(p)
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("demo")
    p.add_argument("script")
    p.add_argument("--bible", default=None)
    p.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        asyncio.run(args.func(args))
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc.filename}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc
    except ValueError as exc:
        print(f"error: invalid input: {exc}", file=sys.stderr)
        raise SystemExit(4) from exc


if __name__ == "__main__":
    main()
