from __future__ import annotations

from app.graph import PropagationEngine, StoryGraph
from app.llm import LLMClient
from app.schemas import (
    AdaptationOption,
    AppliedAdaptation,
    CultureMechanism,
    PropagationResult,
    Scene,
    StoryState,
)
from app.schemas import RewrittenScene as RewrittenScene
from app.skills import REWRITE_SCENE, SkillSpec


class SceneRewriter:
    def __init__(self, client: LLMClient, skill: SkillSpec = REWRITE_SCENE) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

    def _adaptation_brief(self, mechanism: CultureMechanism, option: AdaptationOption) -> str:
        functions = mechanism.functions.model_dump(exclude_none=True)
        return (
            f"原文化机制：{mechanism.name}（{mechanism.description}）\n"
            f"其叙事功能：{functions}\n"
            f"选定方案 {option.option_label}（{option.strategy.value}）：{option.title}\n"
            f"替换定义：{option.replacement_definition}\n"
            f"改编理由：{option.rationale}"
        )

    def _neighbor_summaries(self, state: StoryState, scene_id: str) -> list[str]:
        index_by_id = {s.id: i for i, s in enumerate(state.scenes)}
        target_index = index_by_id.get(scene_id)
        if target_index is None:
            return []
        summaries: list[str] = []
        for i, scene in enumerate(state.scenes):
            if abs(i - target_index) <= 1 and scene.id != scene_id:
                summaries.append(f"{scene.id}: {scene.summary}")
        return summaries

    def _character_sheet(self, state: StoryState, scene: Scene) -> str:
        lines: list[str] = []
        for cid in scene.character_ids:
            character = next((c for c in state.characters if c.id == cid), None)
            if character is not None:
                goals = "、".join(character.goals) if character.goals else "未记录"
                lines.append(f"{character.id} {character.name}（{character.role}）：{character.description}；目标：{goals}")
        return "\n".join(lines) or "无人物记录"

    def _commitments_to_preserve(
        self,
        state: StoryState,
        propagation: PropagationResult,
    ) -> list[str]:
        related = set(propagation.related_commitment_ids)
        return [
            f"{nc.id}: {nc.description}"
            for nc in state.commitments
            if nc.must_preserve or nc.id in related
        ]

    @staticmethod
    def _validate_rewrite(scene: Scene, rewritten: RewrittenScene) -> None:
        if rewritten.id != scene.id:
            raise ValueError(
                f"rewritten scene id mismatch: expected {scene.id}, got {rewritten.id}"
            )

    async def apply(
        self,
        state: StoryState,
        mechanism_id: str,
        option: AdaptationOption,
        propagation: PropagationResult,
    ) -> AppliedAdaptation:
        mechanism = next((m for m in state.culture_mechanisms if m.id == mechanism_id), None)
        if mechanism is None:
            raise KeyError(f"unknown culture mechanism: {mechanism_id}")

        brief = self._adaptation_brief(mechanism, option)
        commitments = self._commitments_to_preserve(state, propagation)

        rewritten_ids: list[str] = []
        for affected in propagation.affected_scenes:
            scene = state.scene_by_id(affected.scene_id)
            if scene is None:
                continue
            rewritten = await self.skill.run(
                self.client,
                result_validator=lambda result: self._validate_rewrite(scene, result),
                scene_json=scene.model_dump(),
                adaptation_brief=brief,
                must_preserve_commitments=commitments,
                neighbor_summaries=self._neighbor_summaries(state, scene.id),
                character_sheet=self._character_sheet(state, scene),
            )
            scene.title = rewritten.title or scene.title
            scene.summary = rewritten.summary or scene.summary
            scene.text = rewritten.text
            rewritten_ids.append(scene.id)

        mechanism.adapted_to = option.replacement_definition
        mechanism.adapted_strategy = option.strategy.value

        return AppliedAdaptation(
            plan_culture_mechanism_id=mechanism_id,
            chosen_option=option,
            propagation=propagation,
            rewritten_scene_ids=rewritten_ids,
        )

    async def repair(
        self,
        state: StoryState,
        issues: list[tuple[str, str]],
        adaptation_brief: str = "",
    ) -> list[str]:
        repaired_ids: list[str] = []
        scene_issues: dict[str, list[str]] = {}
        for scene_id, description in issues:
            if scene_id is None:
                continue
            scene_issues.setdefault(scene_id, []).append(description)

        for scene_id, descriptions in scene_issues.items():
            scene = state.scene_by_id(scene_id)
            if scene is None:
                continue
            brief = (
                "修复以下一致性问题的同时，保持既定改编方向不变：\n"
                + (adaptation_brief + "\n" if adaptation_brief else "")
                + "\n".join(f"- {d}" for d in descriptions)
            )
            rewritten = await self.skill.run(
                self.client,
                result_validator=lambda result: self._validate_rewrite(scene, result),
                scene_json=scene.model_dump(),
                adaptation_brief=brief,
                must_preserve_commitments=[
                    f"{nc.id}: {nc.description}" for nc in state.commitments if nc.must_preserve
                ],
                neighbor_summaries=self._neighbor_summaries(state, scene.id),
                character_sheet=self._character_sheet(state, scene),
            )
            scene.title = rewritten.title or scene.title
            scene.summary = rewritten.summary or scene.summary
            scene.text = rewritten.text
            repaired_ids.append(scene.id)
        return repaired_ids

    @staticmethod
    def build_propagation(state: StoryState, mechanism_id: str) -> PropagationResult:
        graph = StoryGraph(state)
        engine = PropagationEngine(graph)
        return engine.find_affected_scenes(mechanism_id)
