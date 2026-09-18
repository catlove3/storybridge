from __future__ import annotations

import re

from app.graph import StoryGraph
from app.llm import LLMClient
from app.schemas import AdaptationPlan, CultureMechanism, Setting, StoryState
from app.skills import PLAN_ADAPTATION, SkillSpec
from app.workflow.targets import adaptation_target, linked_commitments, target_scene_ids

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def _require_chinese_decision_copy(plan: AdaptationPlan) -> None:
    for option in plan.options:
        fields = {
            "title": option.title,
            "replacement_definition": option.replacement_definition,
            "rationale": option.rationale,
        }
        fields.update(
            {f"risks[{index}]": risk for index, risk in enumerate(option.risks)}
        )
        missing = [name for name, value in fields.items() if not _CJK_RE.search(value)]
        if missing:
            raise ValueError(
                f"option {option.option_label} fields must contain Simplified Chinese "
                f"decision copy (English proper nouns are allowed): {', '.join(missing)}"
            )


class AdaptationPlanner:
    def __init__(self, client: LLMClient, skill: SkillSpec = PLAN_ADAPTATION) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

    @staticmethod
    def _target(state: StoryState, target_id: str) -> CultureMechanism | Setting:
        return adaptation_target(state, target_id)

    def _related_context(
        self, state: StoryState, target: CultureMechanism | Setting
    ) -> dict:
        graph = StoryGraph(state)
        neighbors = (
            list(graph.graph.successors(target.id)) + list(graph.graph.predecessors(target.id))
            if graph.has_node(target.id)
            else []
        )

        related_commitments = linked_commitments(state, target.id)
        touching_scene_ids = target_scene_ids(state, target)
        for commitment in related_commitments:
            touching_scene_ids.update(
                scene_id
                for scene_id in (
                    commitment.established_at_scene_id,
                    commitment.payoff_scene_id,
                )
                if scene_id
            )

        scene_summaries = [
            {
                "id": s.id,
                "summary": s.summary,
                "current_text_excerpt": s.text[:1600],
            }
            for s in state.scenes
            if s.id in touching_scene_ids | {n for n in neighbors if n.startswith("S")}
        ]
        events = [
            {"id": e.id, "description": e.description}
            for e in state.events
            if e.id in neighbors
        ]
        commitments = [
            {"id": nc.id, "description": nc.description}
            for nc in state.commitments
            if nc in related_commitments or nc.must_preserve
        ]
        dependency_edges = [
            d.model_dump()
            for d in state.dependencies
            if target.id in (d.source_id, d.target_id)
        ]
        return {
            "touching_scenes": scene_summaries,
            "applied_core_settings": [
                {
                    "id": setting.id,
                    "name": setting.name,
                    "current_definition": setting.adapted_to,
                    "strategy": setting.adapted_strategy,
                }
                for setting in state.settings
                if setting.adapted_to
            ],
            "related_events": events,
            "related_commitments": commitments,
            "dependency_edges": dependency_edges,
        }

    async def plan(
        self,
        state: StoryState,
        mechanism_id: str,
        target_market_profile: dict | None = None,
    ) -> AdaptationPlan:
        target = self._target(state, mechanism_id)

        profile = target_market_profile or {
            "market": state.target_market,
            "audience": state.audience,
            "format": state.format,
            "genre": state.genre,
        }
        context = self._related_context(state, target)

        def validate_result(plan: AdaptationPlan) -> None:
            if plan.culture_mechanism_id != target.id:
                raise ValueError(
                    "adaptation plan mechanism id mismatch: "
                    f"expected {target.id}, got {plan.culture_mechanism_id}"
                )
            if plan.original_name != target.name:
                raise ValueError(
                    "adaptation plan mechanism name mismatch: "
                    f"expected {target.name!r}, got {plan.original_name!r}"
                )
            _require_chinese_decision_copy(plan)

        plan = await self.skill.run(
            self.client,
            result_validator=validate_result,
            mechanism_json={
                **target.model_dump(),
                "target_kind": (
                    "culture_mechanism"
                    if isinstance(target, CultureMechanism)
                    else "core_setting"
                ),
            },
            related_context_json=context,
            target_market_profile=profile,
        )
        return plan
