from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.baselines.metrics import EvalMetrics, evaluate_output, format_metrics_table
from app.baselines.prompts import (
    BASELINE_STRONG_PROMPT_SYSTEM,
    BASELINE_STRONG_PROMPT_USER,
    BASELINE_TRANSLATE_SYSTEM,
    BASELINE_TRANSLATE_USER,
)
from app.llm import LLMClient, LLMRequest
from app.schemas import StoryState
from app.skills import PARSE_STORY
from app.storage import MarketProfile
from app.workflow.engine import StoryBridgeWorkflow


@dataclass
class ExperimentResult:
    scenario_name: str
    metrics: list[EvalMetrics]
    scripts: dict[str, str]


class BaselineRunner:
    def __init__(self, workflow: StoryBridgeWorkflow, client: LLMClient) -> None:
        self.workflow = workflow
        self.client = client

    async def _reparse(self, script_text: str, market: str) -> StoryState:
        return await PARSE_STORY.run(
            self.client, script_text=script_text, target_market=market
        )

    @staticmethod
    def _ground_truth_scenes(original: StoryState, mechanism_ids: list[str]) -> list[str]:
        import re

        def norm(text: str) -> str:
            return re.sub(r"\s+", "", text)

        scene_ids: set[str] = set()
        for cm in original.culture_mechanisms:
            if cm.id not in mechanism_ids:
                continue
            probes = {cm.name, *cm.surface_text}
            for scene in original.scenes:
                text = norm(scene.text) + norm(scene.summary)
                if any(norm(p) in text for p in probes if p):
                    scene_ids.add(scene.id)
        return sorted(scene_ids)

    async def run_baseline_translate(
        self, script: str, market: str
    ) -> str:
        request = LLMRequest(
            step="baseline_translate",
            system_prompt=BASELINE_TRANSLATE_SYSTEM,
            user_prompt=BASELINE_TRANSLATE_USER.format(script=script),
        )
        response = await self.client.complete(request)
        return response.text

    async def run_baseline_strong_prompt(
        self, script: str, market: str, profile: dict | None = None, language: str = "English"
    ) -> str:
        request = LLMRequest(
            step="baseline_strong_prompt",
            system_prompt=BASELINE_STRONG_PROMPT_SYSTEM,
            user_prompt=BASELINE_STRONG_PROMPT_USER.format(
                script=script,
                market=market or "North America",
                profile=json.dumps(profile or {"market": market}, ensure_ascii=False),
                language=language,
            ),
        )
        response = await self.client.complete(request)
        return response.text

    async def run_experiment(
        self,
        scenario_name: str,
        script: str,
        mechanism_plans: list[tuple[str, str]],
        market_profile: MarketProfile | None = None,
    ) -> ExperimentResult:
        market = market_profile.market if market_profile else "United States"
        meta = await self.workflow.create_project(scenario_name, script, market_profile)
        original_state = await self.workflow.analyze(meta.id)

        adapted_mechanism_ids = [mid for mid, _ in mechanism_plans]
        expected_ids = self._ground_truth_scenes(original_state, adapted_mechanism_ids)

        for mechanism_id, option_label in mechanism_plans:
            await self.workflow.plan(meta.id, mechanism_id)
            result = await self.workflow.apply_adaptation(
                meta.id, mechanism_id, option_label
            )
            expected_ids = sorted(
                set(expected_ids)
                | {a.scene_id for a in result.applied.propagation.affected_scenes}
            )

        final_state = self.workflow.require_state(meta.id)
        bridge_script = "\n\n".join(s.text for s in final_state.scenes)

        translate_out = await self.run_baseline_translate(script, market)
        strong_out = await self.run_baseline_strong_prompt(script, market)

        metrics: list[EvalMetrics] = []
        translate_metrics = evaluate_output(
            original_state,
            None,
            translate_out,
            "A 直接翻译",
            expected_ids,
        )
        translate_metrics.stale_reference_count = -1
        translate_metrics.notes.append(
            "输出为英文，中文探针不适用；直接翻译不做改编，机制全部未本土化"
        )
        metrics.append(translate_metrics)

        strong_state = await self._reparse(strong_out, market)
        metrics.append(
            evaluate_output(
                original_state,
                strong_state,
                strong_out,
                "B 强Prompt一次性改写",
                expected_ids,
            )
        )

        report = await self.workflow.verify(meta.id)
        commitment_checks = [c.model_dump() for c in report.commitment_checks]
        metrics.append(
            evaluate_output(
                original_state,
                final_state,
                bridge_script,
                "C StoryBridge",
                expected_ids,
                commitment_checks=commitment_checks,
            )
        )

        return ExperimentResult(
            scenario_name=scenario_name,
            metrics=metrics,
            scripts={
                "original": script,
                "baseline_translate": translate_out,
                "baseline_strong_prompt": strong_out,
                "storybridge": bridge_script,
            },
        )


def save_experiment(result: ExperimentResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": result.scenario_name,
        "metrics": [m.__dict__ for m in result.metrics],
    }
    json_path = out_dir / f"{result.scenario_name}.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path = out_dir / f"{result.scenario_name}.md"
    lines = [
        f"# Baseline 对比：{result.scenario_name}",
        "",
        format_metrics_table(result.metrics),
        "",
    ]
    for m in result.metrics:
        if m.stale_details:
            lines.append(f"## {m.system_name} 残留明细")
            lines.extend(f"- {d}" for d in m.stale_details)
            lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    scripts_dir = out_dir / result.scenario_name
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name, text in result.scripts.items():
        (scripts_dir / f"{name}.txt").write_text(text, encoding="utf-8")
    return json_path
