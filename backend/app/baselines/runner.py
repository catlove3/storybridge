from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.baselines.metrics import EvalMetrics, evaluate_output, format_metrics_table
from app.baselines.prompts import (
    BASELINE_STRONG_PROMPT_SYSTEM,
    BASELINE_STRONG_PROMPT_USER,
    BASELINE_TRANSLATE_SYSTEM,
    BASELINE_TRANSLATE_USER,
)
from app.llm import LLMClient
from app.llm.structured import generate_structured
from app.privacy import project_data_context
from app.schemas import StoryState, TargetScript
from app.storage import MarketProfile
from app.workflow.engine import StoryBridgeWorkflow


@dataclass
class ExperimentResult:
    scenario_name: str
    metrics: list[EvalMetrics]
    scripts: dict[str, str]
    target_language: str
    target_locale: str
    annotation_source: str
    run_manifest: dict


class EvalAnnotations(BaseModel):
    expected_affected_ids: list[str] = Field(min_length=1)
    forbidden_target_terms: dict[str, list[str]] = Field(default_factory=dict)
    source: str = "human"


class BaselineRunner:
    def __init__(self, workflow: StoryBridgeWorkflow, client: LLMClient) -> None:
        self.workflow = workflow
        self.client = client

    @staticmethod
    def _blake2b(text: str) -> str:
        return hashlib.blake2b(text.encode("utf-8"), digest_size=32).hexdigest()

    def _model_manifest(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for step in (
            "parse_story",
            "detect_frictions",
            "plan_adaptation",
            "rewrite_scene",
            "verify_consistency",
            "render_target_script",
            "baseline_translate",
            "baseline_strong_prompt",
        ):
            profile_for_step = getattr(self.client, "profile_for_step", None)
            if callable(profile_for_step):
                profile_name, profile = profile_for_step(step)
                result[step] = {
                    "profile": profile_name,
                    "model": profile.model,
                    "temperature": profile.temperature,
                    "max_tokens": profile.max_tokens,
                }
            else:
                result[step] = {
                    "profile": "mock" if hasattr(self.client, "model") else "unknown",
                    "model": getattr(self.client, "model", "unknown"),
                }
        return result

    @staticmethod
    def _state_with_target_text(state: StoryState, target: TargetScript) -> StoryState:
        candidate = state.model_copy(deep=True)
        target_by_id = {scene.id: scene for scene in target.scenes}
        for scene in candidate.scenes:
            rendered = target_by_id.get(scene.id)
            if rendered is not None:
                scene.title = rendered.title
                scene.summary = rendered.summary
                scene.text = rendered.text
        return candidate

    @staticmethod
    def _validate_scene_coverage(
        expected_ids: list[str], target_language: str, target_locale: str
    ):
        def validate(result: TargetScript) -> None:
            returned_ids = [scene.id for scene in result.scenes]
            if returned_ids != expected_ids:
                raise ValueError(
                    f"target script scene ids mismatch: expected {expected_ids}, got {returned_ids}"
                )
            if result.target_language.casefold() != target_language.casefold():
                raise ValueError(
                    "target script language mismatch: "
                    f"expected {target_language!r}, got {result.target_language!r}"
                )
            if result.target_locale.casefold() != target_locale.casefold():
                raise ValueError(
                    "target script locale mismatch: "
                    f"expected {target_locale!r}, got {result.target_locale!r}"
                )

        return validate

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
        self,
        script: str,
        profile: MarketProfile,
        expected_scene_ids: list[str],
    ) -> TargetScript:
        return await generate_structured(
            self.client,
            TargetScript,
            step="baseline_translate",
            system_prompt=BASELINE_TRANSLATE_SYSTEM,
            user_prompt=BASELINE_TRANSLATE_USER.format(
                script=script,
                source_language=profile.source_language,
                target_language=profile.target_language,
                target_locale=profile.target_locale,
            ),
            result_validator=self._validate_scene_coverage(
                expected_scene_ids, profile.target_language, profile.target_locale
            ),
        )

    async def run_baseline_strong_prompt(
        self,
        script: str,
        profile: MarketProfile,
        expected_scene_ids: list[str],
    ) -> TargetScript:
        return await generate_structured(
            self.client,
            TargetScript,
            step="baseline_strong_prompt",
            system_prompt=BASELINE_STRONG_PROMPT_SYSTEM,
            user_prompt=BASELINE_STRONG_PROMPT_USER.format(
                script=script,
                market=profile.market or "North America",
                profile=json.dumps(profile.model_dump(), ensure_ascii=False),
                language=profile.target_language,
                source_language=profile.source_language,
                target_locale=profile.target_locale,
            ),
            result_validator=self._validate_scene_coverage(
                expected_scene_ids, profile.target_language, profile.target_locale
            ),
        )

    async def run_experiment(
        self,
        scenario_name: str,
        script: str,
        mechanism_plans: list[tuple[str, str]],
        market_profile: MarketProfile | None = None,
        annotations: EvalAnnotations | None = None,
    ) -> ExperimentResult:
        profile = market_profile or MarketProfile(market="United States")
        meta = await self.workflow.create_project(scenario_name, script, profile)
        original_state = await self.workflow.analyze(meta.id)

        adapted_mechanism_ids = [mid for mid, _ in mechanism_plans]
        expected_ids = (
            sorted(set(annotations.expected_affected_ids))
            if annotations is not None
            else self._ground_truth_scenes(original_state, adapted_mechanism_ids)
        )
        annotation_source = annotations.source if annotations is not None else "lexical_fallback"

        for mechanism_id, option_label in mechanism_plans:
            await self.workflow.plan(meta.id, mechanism_id)
            await self.workflow.apply_adaptation(meta.id, mechanism_id, option_label)

        final_state = self.workflow.require_state(meta.id)
        bridge_target = await self.workflow.render_target_script(meta.id)

        scene_ids = [scene.id for scene in original_state.scenes]
        with project_data_context(meta.id, meta.data_policy):
            translate_out = await self.run_baseline_translate(script, profile, scene_ids)
            strong_out = await self.run_baseline_strong_prompt(script, profile, scene_ids)
        forbidden_terms = (
            {
                mechanism_id: annotations.forbidden_target_terms[mechanism_id]
                for mechanism_id in adapted_mechanism_ids
            }
            if annotations is not None
            and all(
                mechanism_id in annotations.forbidden_target_terms
                for mechanism_id in adapted_mechanism_ids
            )
            else None
        )

        async def commitment_checks(state: StoryState, target: TargetScript) -> list[dict]:
            with project_data_context(meta.id, meta.data_policy):
                report = await self.workflow.verifier.verify(
                    self._state_with_target_text(state, target)
                )
            return [check.model_dump() for check in report.commitment_checks]

        metrics: list[EvalMetrics] = []
        translate_metrics = evaluate_output(
            original_state,
            None,
            translate_out.text,
            "A 直接翻译",
            expected_ids,
            commitment_checks=await commitment_checks(original_state, translate_out),
            output_language=profile.target_language,
            source_language=profile.source_language,
            forbidden_terms=forbidden_terms,
            target_output=translate_out,
            target_reference=translate_out,
        )
        metrics.append(translate_metrics)

        metrics.append(
            evaluate_output(
                original_state,
                None,
                strong_out.text,
                "B 强Prompt一次性改写",
                expected_ids,
                commitment_checks=await commitment_checks(original_state, strong_out),
                output_language=profile.target_language,
                source_language=profile.source_language,
                forbidden_terms=forbidden_terms,
                target_output=strong_out,
                target_reference=translate_out,
            )
        )

        metrics.append(
            evaluate_output(
                original_state,
                None,
                bridge_target.text,
                "C StoryBridge",
                expected_ids,
                commitment_checks=await commitment_checks(final_state, bridge_target),
                output_language=profile.target_language,
                source_language=profile.source_language,
                forbidden_terms=forbidden_terms,
                target_output=bridge_target,
                target_reference=translate_out,
            )
        )
        if annotations is None:
            for metric in metrics:
                metric.notes.append(
                    "affected-scene truth uses lexical fallback; provide human annotations for claims"
                )

        scripts = {
            "original": script,
            "baseline_translate": translate_out.text,
            "baseline_strong_prompt": strong_out.text,
            "storybridge": bridge_target.text,
        }
        annotation_payload = annotations.model_dump(mode="json") if annotations else None
        run_manifest = {
            "schema_version": 1,
            "run_id": uuid.uuid4().hex,
            "generated_at": datetime.now(UTC).isoformat(),
            "code_revision": os.environ.get("STORYBRIDGE_COMMIT", "unrecorded"),
            "scenario": scenario_name,
            "input_blake2b": self._blake2b(script),
            "input_chars": len(script),
            "mechanism_plans": [
                {"culture_mechanism_id": mechanism_id, "option_label": option_label}
                for mechanism_id, option_label in mechanism_plans
            ],
            "localization": profile.model_dump(mode="json"),
            "annotation_source": annotation_source,
            "annotations_blake2b": (
                self._blake2b(
                    json.dumps(annotation_payload, ensure_ascii=False, sort_keys=True)
                )
                if annotation_payload is not None
                else None
            ),
            "models": self._model_manifest(),
            "prompt_version": "v1",
            "systems": ["baseline_translate", "baseline_strong_prompt", "storybridge"],
            "output_blake2b": {
                name: self._blake2b(text) for name, text in scripts.items()
            },
        }
        return ExperimentResult(
            scenario_name=scenario_name,
            metrics=metrics,
            scripts=scripts,
            target_language=profile.target_language,
            target_locale=profile.target_locale,
            annotation_source=annotation_source,
            run_manifest=run_manifest,
        )


def save_experiment(result: ExperimentResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": result.scenario_name,
        "target_language": result.target_language,
        "target_locale": result.target_locale,
        "annotation_source": result.annotation_source,
        "run_manifest": result.run_manifest,
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
        "## Run manifest",
        "",
        f"- Run ID: `{result.run_manifest['run_id']}`",
        f"- Code revision: `{result.run_manifest['code_revision']}`",
        f"- Input BLAKE2b: `{result.run_manifest['input_blake2b']}`",
        f"- Annotation source: `{result.annotation_source}`",
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
