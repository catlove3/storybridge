from __future__ import annotations

from app.graph import PropagationEngine, StoryGraph
from app.llm import LLMClient
from app.schemas import (
    AdaptationOption,
    AffectedScene,
    AppliedAdaptation,
    CultureMechanism,
    ImpactKind,
    PropagationResult,
    Scene,
    Setting,
    StoryState,
)
from app.schemas import RewrittenScene as RewrittenScene
from app.schemas.repair import RepairPlan
from app.skills import REWRITE_SCENE, SkillSpec
from app.skills.registry import PLAN_REPAIR
from app.workflow.language_checks import foreign_language_fragments
from app.workflow.targets import adaptation_target, linked_commitments, target_scene_ids


class RepairNeedsInput(ValueError):
    """The repair plan is safe to resume after the author answers a question."""


class SceneRewriter:
    def __init__(self, client: LLMClient, skill: SkillSpec = REWRITE_SCENE) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

    @staticmethod
    def _target(state: StoryState, target_id: str) -> CultureMechanism | Setting:
        return adaptation_target(state, target_id)

    def _adaptation_brief(
        self,
        state: StoryState,
        target: CultureMechanism | Setting,
        option: AdaptationOption,
    ) -> str:
        functions = (
            target.functions.model_dump(exclude_none=True)
            if isinstance(target, CultureMechanism)
            else {"story_world_rule": target.description}
        )
        frozen_settings = [
            f"- {setting.id} {setting.name}：{setting.adapted_to}"
            for setting in state.settings
            if setting.adapted_to and setting.id != target.id
        ]
        frozen_context = (
            "\n已生效的核心设定（必须服从，不得恢复其改写前版本）：\n"
            + "\n".join(frozen_settings)
            if frozen_settings
            else ""
        )
        return (
            f"原改编对象：{target.name}（{target.description}）\n"
            f"其叙事功能：{functions}\n"
            f"选定方案 {option.option_label}（{option.strategy.value}）：{option.title}\n"
            f"替换定义：{option.replacement_definition}\n"
            f"改编理由：{option.rationale}"
            f"{frozen_context}"
        )

    def _neighbor_summaries(self, state: StoryState, scene_id: str) -> list[str]:
        index_by_id = {s.id: i for i, s in enumerate(state.scenes)}
        target_index = index_by_id.get(scene_id)
        if target_index is None:
            return []
        summaries: list[str] = []
        for i, scene in enumerate(state.scenes):
            if abs(i - target_index) <= 1 and scene.id != scene_id:
                summaries.append(f"{scene.id} {scene.title}: {scene.summary}")
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
    def _validate_rewrite(
        scene: Scene,
        rewritten: RewrittenScene,
        source_language: str = "zh-CN",
    ) -> None:
        if rewritten.id != scene.id:
            raise ValueError(
                f"rewritten scene id mismatch: expected {scene.id}, got {rewritten.id}"
            )
        if source_language.lower().startswith("zh"):
            fields = {
                "title": rewritten.title,
                "summary": rewritten.summary,
                "text": rewritten.text,
            }
            drift = {
                name: fragments
                for name, value in fields.items()
                if (fragments := foreign_language_fragments(value))
            }
            if drift:
                raise ValueError(
                    "Chinese structure draft contains target-language passages; "
                    "rewrite title, summary, and dialogue in Simplified Chinese: "
                    + ", ".join(drift)
                )

    async def apply(
        self,
        state: StoryState,
        mechanism_id: str,
        option: AdaptationOption,
        propagation: PropagationResult,
    ) -> AppliedAdaptation:
        target = self._target(state, mechanism_id)
        # A new adaptation may intentionally change previously fixed facts.
        state.repair_baseline = None

        brief = self._adaptation_brief(state, target, option)
        commitments = self._commitments_to_preserve(state, propagation)

        rewritten_ids: list[str] = []
        for affected in propagation.affected_scenes:
            scene = state.scene_by_id(affected.scene_id)
            if scene is None:
                continue
            rewritten = await self.skill.run(
                self.client,
                result_validator=lambda result: self._validate_rewrite(
                    scene, result, state.source_language
                ),
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

        target.adapted_to = option.replacement_definition
        target.adapted_strategy = option.strategy.value

        return AppliedAdaptation(
            plan_culture_mechanism_id=mechanism_id,
            chosen_option=option,
            propagation=propagation,
            rewritten_scene_ids=rewritten_ids,
        )

    async def prepare_repair(
        self,
        state: StoryState,
        issues: list[tuple[str, str]],
        adaptation_brief: str,
        *,
        source_script: str,
        kept_items: list[str] | None = None,
        required_payoff_commitment_ids: set[str] | None = None,
    ) -> list[tuple[str, str]]:
        required_payoffs = required_payoff_commitment_ids or set()

        def validate(plan: RepairPlan) -> None:
            ids = [item.scene_id for item in plan.scene_repairs]
            if len(ids) != len(set(ids)) or set(ids) - {s.id for s in state.scenes}:
                raise ValueError("修复计划包含重复或不存在的场景")
            keys = [(f.timeline, f.subject, f.attribute, f.phase) for f in plan.baseline.facts]
            if len(keys) != len(set(keys)):
                raise ValueError("同一时间线、人物、属性和阶段只能有一个事实值")
            if plan.scene_repairs and not (plan.baseline.facts or plan.baseline.rules):
                raise ValueError("修复前必须明确全篇事实或规则基准")
            event_ids = [item.event_id for item in plan.event_updates]
            known_events = {item.id for item in state.events}
            commitment_ids = [item.commitment_id for item in plan.commitment_updates]
            known_commitments = {item.id for item in state.commitments}
            known_scenes = {item.id for item in state.scenes}
            if len(event_ids) != len(set(event_ids)) or set(event_ids) - known_events:
                raise ValueError("修复计划包含重复或不存在的事件")
            if len(commitment_ids) != len(set(commitment_ids)) or set(commitment_ids) - known_commitments:
                raise ValueError("修复计划包含重复或不存在的叙事承诺")
            commitment_updates = {
                item.commitment_id: item for item in plan.commitment_updates
            }
            missing_payoffs = [
                commitment_id for commitment_id in required_payoffs
                if commitment_id not in commitment_updates
                or not commitment_updates[commitment_id].payoff_scene_id
            ]
            if missing_payoffs:
                raise ValueError(
                    "本轮确认修复的叙事承诺必须更新并指定实际回收场景："
                    + "、".join(sorted(missing_payoffs))
                )
            referenced_scenes = {
                scene_id for item in plan.event_updates for scene_id in item.scene_ids
            } | {
                scene_id
                for item in plan.commitment_updates
                for scene_id in (item.established_at_scene_id, item.payoff_scene_id)
                if scene_id
            }
            if referenced_scenes - known_scenes:
                raise ValueError("修复计划的结构更新引用了不存在的场景")
            existing_dependencies = {
                (item.source_id, item.target_id, item.relation)
                for item in state.dependencies
            }
            update_dependencies = [
                (item.source_id, item.target_id, item.relation)
                for item in plan.dependency_evidence_updates
            ]
            if (
                len(update_dependencies) != len(set(update_dependencies))
                or set(update_dependencies) - existing_dependencies
            ):
                raise ValueError("修复计划只能更新现有且不重复的依赖关系")

        plan = await PLAN_REPAIR.run(
            self.client,
            result_validator=validate,
            source_script=source_script,
            current_story=state.model_dump(mode="json"),
            selected_issues=issues,
            adaptation_and_user_instructions=adaptation_brief,
            user_kept_items=kept_items or [],
            required_payoff_commitment_ids=sorted(required_payoffs),
        )
        if plan.unresolved_questions:
            raise RepairNeedsInput(
                "暂未修改剧本。请在补充建议中确认以下事实后重试："
                + "；".join(plan.unresolved_questions)
            )
        events = {item.id: item for item in state.events}
        for update in plan.event_updates:
            event = events[update.event_id]
            event.description = update.description
            event.scene_ids = update.scene_ids
        commitments = {item.id: item for item in state.commitments}
        for update in plan.commitment_updates:
            commitment = commitments[update.commitment_id]
            commitment.description = update.description
            commitment.established_at_scene_id = update.established_at_scene_id
            commitment.payoff_scene_id = update.payoff_scene_id
            commitment.must_preserve = update.must_preserve
        dependencies = {
            (item.source_id, item.target_id, item.relation): item
            for item in state.dependencies
        }
        for update in plan.dependency_evidence_updates:
            dependency = dependencies[(update.source_id, update.target_id, update.relation)]
            dependency.evidence = update.evidence
            dependency.confidence = update.confidence
        state.repair_baseline = plan.baseline
        return [(item.scene_id, item.instruction) for item in plan.scene_repairs]

    async def repair(
        self,
        state: StoryState,
        issues: list[tuple[str, str]],
        adaptation_brief: str = "",
    ) -> list[str]:
        repaired_ids: list[str] = []
        scene_issues: dict[str, list[str]] = {}
        timeline_context = "\n".join(
            f"{scene.id} {scene.title}：{scene.summary}" for scene in state.scenes
        )
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
                + ("全篇统一修复基准（本场不得重新推断或颠倒归属；同步修改正文和摘要）：\n"
                   + state.repair_baseline.model_dump_json() + "\n"
                   if state.repair_baseline else "")
                + "全篇场景顺序与时间线线索：\n" + timeline_context + "\n"
                + "先核实问题是否成立。区分前世、重生后、回忆及原始/交换后状态，"
                "不要把不同时间线或不同状态的分数、身份、行为结果统一。"
                "检查意见可能误判；若差异可由时间线或既定规则解释，应保留该差异，必要时补充交代，"
                "只修正同一时间线和状态下的真实矛盾。\n"
                + "\n".join(f"- {d}" for d in descriptions)
            )
            rewritten = await self.skill.run(
                self.client,
                result_validator=lambda result: self._validate_rewrite(
                    scene, result, state.source_language
                ),
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
        result = engine.find_affected_scenes(mechanism_id)
        setting = next((item for item in state.settings if item.id == mechanism_id), None)
        if setting is None:
            return result

        scene_ids = target_scene_ids(state, setting)
        related_commitments = set(result.related_commitment_ids)
        for commitment in linked_commitments(state, mechanism_id):
            related_commitments.add(commitment.id)

        affected = {item.scene_id: item for item in result.affected_scenes}
        for scene_id in scene_ids:
            affected.setdefault(
                scene_id,
                AffectedScene(
                    scene_id=scene_id,
                    impact_kinds=[ImpactKind.STRUCTURAL],
                    reason_path=[mechanism_id, scene_id],
                    evidence=f"该场景承载核心设定“{setting.name}”或其叙事承诺。",
                ),
            )
        ordered = sorted(
            affected.values(),
            key=lambda item: int(item.scene_id.removeprefix("S")),
        )
        return PropagationResult(
            changed_node_id=result.changed_node_id,
            affected_scenes=ordered,
            related_commitment_ids=sorted(related_commitments),
            summary=(
                f"调整“{setting.name}”会联动 {len(ordered)} 个场景："
                + "、".join(item.scene_id for item in ordered)
            ),
        )
