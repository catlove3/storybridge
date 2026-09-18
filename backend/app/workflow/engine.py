from __future__ import annotations

import asyncio
import hashlib
import re
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import get_config
from app.llm import LLMClient
from app.privacy import project_data_context
from app.schemas import (
    AdaptationOption,
    AdaptationPlan,
    AdaptationStrategy,
    AppliedAdaptation,
    DataPolicy,
    IssueType,
    PropagationResult,
    StoryState,
    TargetScript,
    VerifyReport,
)
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile, ProjectMeta, ProjectStore
from app.workflow.friction import FrictionDetector
from app.workflow.parser import StoryParser
from app.workflow.planner import AdaptationPlanner
from app.workflow.renderer import TargetScriptRenderer
from app.workflow.rewriter import SceneRewriter
from app.workflow.verifier import Verifier


class ApplyResult(BaseModel):
    applied: AppliedAdaptation
    report: VerifyReport
    repair_rounds: int
    repaired_scene_ids: list[str]


class AdaptationSelection(BaseModel):
    culture_mechanism_id: str = Field(pattern=r"^(?:CM|SET)\d+$")
    option_label: Literal["A", "B", "C", "CUSTOM"]
    custom_instruction: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _validate_custom_instruction(self) -> AdaptationSelection:
        if self.custom_instruction is not None:
            self.custom_instruction = self.custom_instruction.strip() or None
        if self.option_label == "CUSTOM" and not self.custom_instruction:
            raise ValueError("custom option requires a non-empty custom instruction")
        return self


class BatchApplyResult(BaseModel):
    applied: list[AppliedAdaptation]
    report: VerifyReport
    repair_rounds: int
    repaired_scene_ids: list[str]
    from_version: int
    to_version: int


class AdaptationBatch(BaseModel):
    adaptations: list[AdaptationSelection] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _unique_mechanisms(self) -> AdaptationBatch:
        ids = [item.culture_mechanism_id for item in self.adaptations]
        if len(ids) != len(set(ids)):
            raise ValueError("each culture mechanism can only appear once in a batch")
        return self


class StateVersionConflict(RuntimeError):
    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"state version conflict: expected {expected}, current version is {actual}")


class DuplicateOperation(RuntimeError):
    pass


class VerificationBlocked(RuntimeError):
    pass


class StoryBridgeWorkflow:
    def __init__(self, store: ProjectStore, client: LLMClient, max_repair_rounds: int = 2) -> None:
        self.store = store
        self.max_repair_rounds = max_repair_rounds
        long_text = get_config().long_text
        self.parser = StoryParser(
            client,
            chunk_threshold_chars=long_text.chunk_threshold_chars,
            chunk_chars=long_text.chunk_chars,
        )
        self.detector = FrictionDetector(
            client,
            batch_size=long_text.friction_batch_size,
        )
        self.planner = AdaptationPlanner(client)
        self.rewriter = SceneRewriter(client)
        self.renderer = TargetScriptRenderer(client)
        self.verifier = Verifier(client)
        self._project_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._verification_reports: dict[str, tuple[int, VerifyReport]] = {}

    def require_state(self, project_id: str) -> StoryState:
        state = self.store.load_state(project_id)
        if state is None:
            raise KeyError(f"project '{project_id}' has no analyzed state; run analyze first")
        return state

    async def create_project(
        self,
        name: str,
        script_text: str,
        market: MarketProfile | None = None,
        *,
        owner_id: str = "local",
        data_policy: DataPolicy | None = None,
    ) -> ProjectMeta:
        return self.store.create_project(
            name,
            script_text,
            market or MarketProfile(),
            owner_id=owner_id,
            data_policy=data_policy,
        )

    async def analyze(self, project_id: str) -> StoryState:
        async with self._project_locks[project_id]:
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                return await self._analyze_locked(project_id)

    async def _analyze_locked(self, project_id: str) -> StoryState:
        meta = self.store.load_meta(project_id)
        if meta is None:
            raise KeyError(f"unknown project: {project_id}")

        state = await self.parser.parse(
            meta.script_text,
            target_market=meta.market.market,
            project_id=project_id,
            checkpoint_store=self.store,
        )
        state.target_market = meta.market.market
        state.audience = meta.market.audience
        state.format = meta.market.format
        state.genre = meta.market.genre
        state.source_language = meta.market.source_language
        state.target_language = meta.market.target_language
        state.target_locale = meta.market.target_locale
        state.style_guide = meta.market.style_guide
        state.terminology_map = meta.market.terminology_map

        state = await self.detector.apply(state, target_market=meta.market.market)
        self.store.save_state(
            project_id,
            state,
            kind="initial_parse",
            description="Story Parser + Culture Friction Detection",
        )
        return state

    async def plan(self, project_id: str, mechanism_id: str) -> AdaptationPlan:
        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                return await self._plan_locked(project_id, state, mechanism_id)

    async def plan_many(
        self, project_id: str, mechanism_ids: list[str]
    ) -> list[AdaptationPlan]:
        unique_ids = list(dict.fromkeys(mechanism_ids))
        if not unique_ids:
            raise ValueError("at least one culture mechanism is required")
        if len(unique_ids) != len(mechanism_ids):
            raise ValueError("culture mechanism ids must be unique")
        if len(unique_ids) > 20:
            raise ValueError("at most 20 culture mechanisms can be planned together")

        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                return [
                    await self._plan_locked(project_id, state, mechanism_id)
                    for mechanism_id in unique_ids
                ]

    async def _plan_locked(
        self,
        project_id: str,
        state: StoryState,
        mechanism_id: str,
    ) -> AdaptationPlan:
        cached = self.store.load_plan(project_id, mechanism_id)
        if cached is not None and cached.based_on_version == state.version:
            return cached
        meta = self.store.load_meta(project_id)
        profile = meta.market.model_dump() if meta else {}
        plan = await self.planner.plan(state, mechanism_id, target_market_profile=profile)
        plan.based_on_version = state.version
        self.store.save_plan(project_id, plan)
        return plan

    def propagate(self, project_id: str, mechanism_id: str) -> PropagationResult:
        state = self.require_state(project_id)
        return SceneRewriter.build_propagation(state, mechanism_id)

    async def apply_adaptation(
        self,
        project_id: str,
        mechanism_id: str,
        option_label: str,
        auto_verify_and_repair: bool = False,
        based_on_version: int | None = None,
        operation_id: str | None = None,
        custom_instruction: str | None = None,
    ) -> ApplyResult:
        async with self._project_locks[project_id]:
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                return await self._apply_locked(
                    project_id,
                    mechanism_id,
                    option_label,
                    auto_verify_and_repair,
                    based_on_version,
                    operation_id,
                    custom_instruction,
                )

    async def apply_adaptations(
        self,
        project_id: str,
        adaptations: list[AdaptationSelection],
        auto_verify_and_repair: bool = False,
        based_on_version: int | None = None,
        operation_id: str | None = None,
    ) -> BatchApplyResult:
        batch = AdaptationBatch(adaptations=adaptations)
        async with self._project_locks[project_id]:
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                return await self._apply_many_locked(
                    project_id,
                    batch.adaptations,
                    auto_verify_and_repair,
                    based_on_version,
                    operation_id,
                )

    async def _apply_locked(
        self,
        project_id: str,
        mechanism_id: str,
        option_label: str,
        auto_verify_and_repair: bool,
        based_on_version: int | None,
        operation_id: str | None,
        custom_instruction: str | None = None,
    ) -> ApplyResult:
        option_label = option_label.upper()
        if option_label not in {"A", "B", "C", "CUSTOM"}:
            raise KeyError(f"unknown adaptation option: {option_label}")
        batch_result = await self._apply_many_locked(
            project_id,
            [
                AdaptationSelection(
                    culture_mechanism_id=mechanism_id,
                    option_label=option_label,
                    custom_instruction=custom_instruction,
                )
            ],
            auto_verify_and_repair,
            based_on_version,
            operation_id,
        )
        return ApplyResult(
            applied=batch_result.applied[0],
            report=batch_result.report,
            repair_rounds=batch_result.repair_rounds,
            repaired_scene_ids=batch_result.repaired_scene_ids,
        )

    async def _apply_many_locked(
        self,
        project_id: str,
        adaptations: list[AdaptationSelection],
        auto_verify_and_repair: bool,
        based_on_version: int | None,
        operation_id: str | None,
    ) -> BatchApplyResult:
        current_state = self.require_state(project_id)
        if operation_id and any(
            applied.operation_id == operation_id
            for applied in self.store.load_applied(project_id)
        ):
            raise DuplicateOperation(f"operation {operation_id!r} has already been committed")
        if based_on_version is not None and based_on_version != current_state.version:
            raise StateVersionConflict(based_on_version, current_state.version)

        plans_and_options = []
        for selection in adaptations:
            plan = await self._plan_locked(
                project_id, current_state, selection.culture_mechanism_id
            )
            if plan.based_on_version != current_state.version:
                raise StateVersionConflict(plan.based_on_version, current_state.version)
            option = (
                AdaptationOption(
                    option_label="CUSTOM",
                    strategy=AdaptationStrategy.CUSTOM,
                    title="自定义方案",
                    replacement_definition=selection.custom_instruction or "",
                    rationale="按照创作者填写的自定义要求调整，并保留相关人物动机、因果与伏笔。",
                    preserved_functions=["由创作者指定，改写后统一检查"],
                    risks=["自定义要求可能扩大改写范围，需要检查前后场景一致性"],
                )
                if selection.option_label == "CUSTOM"
                else plan.option_by_label(selection.option_label)
            )
            if option is None:
                raise KeyError(
                    f"option '{selection.option_label}' not found for "
                    f"{selection.culture_mechanism_id}; "
                    f"available: {[o.option_label for o in plan.options]}"
                )
            plans_and_options.append((selection, plan, option))

        candidate = current_state.model_copy(deep=True)
        applied_items: list[AppliedAdaptation] = []
        for selection, _plan, option in plans_and_options:
            propagation = SceneRewriter.build_propagation(
                candidate, selection.culture_mechanism_id
            )
            applied = await self.rewriter.apply(
                candidate,
                selection.culture_mechanism_id,
                option,
                propagation,
            )
            applied.operation_id = operation_id
            applied_items.append(applied)

        report = VerifyReport()
        repaired_scene_ids: list[str] = []
        rounds = 0

        if auto_verify_and_repair:
            summary = "; ".join(
                f"{plan.original_name} -> {option.replacement_definition}"
                for _selection, plan, option in plans_and_options
            )
            rewritten_scene_ids = list(
                dict.fromkeys(
                    scene_id
                    for applied in applied_items
                    for scene_id in applied.rewritten_scene_ids
                )
            )
            report = await self.verifier.verify(
                candidate,
                changed_scene_ids=rewritten_scene_ids,
                applied_adaptations_summary=summary,
            )

            while report.blocking_issues and rounds < self.max_repair_rounds:
                issues = [
                    (i.scene_id, i.description) for i in report.blocking_issues if i.scene_id
                ]
                if not issues:
                    break
                rounds += 1
                meta = self.store.load_meta(project_id)
                issues = await self.rewriter.prepare_repair(
                    candidate, issues, summary,
                    source_script=meta.script_text if meta else "",
                )
                repaired_scene_ids.extend(
                    await self.rewriter.repair(candidate, issues, summary)
                )
                report = await self.verifier.verify(
                    candidate,
                    changed_scene_ids=list(
                        dict.fromkeys([*rewritten_scene_ids, *repaired_scene_ids])
                    ),
                    applied_adaptations_summary=summary,
                )

        changed_scene_ids = list(
            dict.fromkeys(
                [
                    *(
                        scene_id
                        for applied in applied_items
                        for scene_id in applied.rewritten_scene_ids
                    ),
                    *repaired_scene_ids,
                ]
            )
        )
        self.store.save_state(
            project_id,
            candidate,
            kind="adaptation_applied",
            description=(
                f"applied {len(applied_items)} adaptation(s): "
                + ", ".join(
                    f"{selection.culture_mechanism_id}/{option.option_label}"
                    for selection, _plan, option in plans_and_options
                )
                + f"; repair rounds={rounds}"
            ),
            changed_scene_ids=changed_scene_ids,
            applied_option={
                "adaptations": [
                    {
                        "culture_mechanism_id": selection.culture_mechanism_id,
                        "option": option.model_dump(mode="json"),
                    }
                    for selection, _plan, option in plans_and_options
                ]
            },
            applied=applied_items,
        )
        if auto_verify_and_repair:
            self._remember_report(project_id, candidate.version, report)

        return BatchApplyResult(
            applied=applied_items,
            report=report,
            repair_rounds=rounds,
            repaired_scene_ids=repaired_scene_ids,
            from_version=current_state.version,
            to_version=candidate.version,
        )

    async def verify(self, project_id: str) -> VerifyReport:
        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            applied = list({
                item.plan_culture_mechanism_id: item
                for item in self.store.load_applied(project_id)
            }.values())
            summary = "; ".join(
                f"{a.plan_culture_mechanism_id} -> {a.chosen_option.replacement_definition}"
                for a in applied
            )
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                report = await self.verifier.verify(
                    state, applied_adaptations_summary=summary
                )
            self._remember_report(project_id, state.version, report)
            return report

    async def confirm_verification_review(
        self, project_id: str, based_on_report: str,
        kept_issue_indexes: list[int], kept_commitment_ids: list[str],
    ) -> VerifyReport:
        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            report = self.latest_report(project_id)
            if report is None or report.review_token != based_on_report:
                raise ValueError("检查结果已更新，请刷新后重新确认")
            if any(index < 0 or index >= len(report.issues) for index in kept_issue_indexes):
                raise ValueError("选中的检查项不存在")
            if set(kept_commitment_ids) - {item.commitment_id for item in report.commitment_checks}:
                raise ValueError("选中的叙事承诺不存在")
            report.kept_issue_indexes = sorted(set(kept_issue_indexes))
            report.kept_commitment_ids = sorted(set(kept_commitment_ids))
            report.recompute_score()
            self._remember_report(project_id, state.version, report)
            return report

    async def repair_from_verification(
        self, project_id: str, *,
        review_issue_indexes: list[int] | None = None,
        review_commitment_ids: list[str] | None = None,
        based_on_report: str | None = None,
        repair_suggestion: str = "",
        repair_scene_ids: list[str] | None = None,
    ) -> VerifyReport:
        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            report = self.latest_report(project_id)
            if report is None:
                raise ValueError("没有可用于修复的检查结果，请先检查剧本")

            selected_indexes = set(review_issue_indexes or [])
            selected_commitments = set(review_commitment_ids or [])
            suggestion = repair_suggestion.strip()
            if len(repair_suggestion) > 4000:
                raise ValueError("补充建议不能超过 4000 字符")
            suggested_scene_ids = set(repair_scene_ids or [])
            if suggested_scene_ids - {scene.id for scene in state.scenes}:
                raise ValueError("建议指定的场景不存在，请刷新后重新选择")
            if suggested_scene_ids and not suggestion:
                raise ValueError("请填写补充问题或改进建议")
            if (selected_indexes or selected_commitments or based_on_report or suggestion) and based_on_report != report.review_token:
                raise ValueError("检查结果已更新，请刷新后重新确认需要修改的项目")
            if any(index < 0 or index >= len(report.issues) for index in selected_indexes):
                raise ValueError("选中的检查项不存在")
            if selected_commitments - {item.commitment_id for item in report.commitment_checks}:
                raise ValueError("选中的叙事承诺不存在")
            selected_issues = [
                issue for index, issue in enumerate(report.issues)
                if index not in report.kept_issue_indexes
                and (issue.severity.value == "error" or index in selected_indexes)
            ]

            issues: list[tuple[str, str]] = []
            for issue in selected_issues:
                detail = issue.description
                if issue.evidence:
                    detail += f"；检查证据：{issue.evidence}"
                scene_ids = {issue.scene_id} if issue.scene_id else set()
                if not scene_ids:
                    for node_id in re.findall(r"\b(?:CM|SET|NC|S|E)\d+\b", detail):
                        if state.scene_by_id(node_id):
                            scene_ids.add(node_id)
                        elif state.node(node_id):
                            propagation = self.propagate(project_id, node_id)
                            scene_ids.update(item.scene_id for item in propagation.affected_scenes)
                    # A confirmed global issue must be addressed even without a scene id.
                    if not scene_ids:
                        scene_ids = {scene.id for scene in state.scenes}
                issues.extend((scene.id, detail) for scene in state.scenes if scene.id in scene_ids)
            commitments = {item.id: item for item in state.commitments}
            required_payoff_commitment_ids: set[str] = set()
            for check in report.commitment_checks:
                if check.commitment_id in report.kept_commitment_ids:
                    continue
                if check.status != "violated" and not (
                    check.status == "needs_review" and check.commitment_id in selected_commitments
                ):
                    continue
                commitment = commitments.get(check.commitment_id)
                if commitment is None:
                    continue
                if check.status == "violated":
                    required_payoff_commitment_ids.add(commitment.id)
                scene_id = commitment.payoff_scene_id or commitment.established_at_scene_id
                if scene_id:
                    issues.append(
                        (
                            scene_id,
                            f"修复叙事承诺 {commitment.id}：{commitment.description}；"
                            f"检查结论：{check.explanation or check.status}",
                        )
                    )
            if suggestion:
                if not suggested_scene_ids:
                    suggested_scene_ids = {scene.id for scene in state.scenes}
                issues.extend(
                    (scene.id, f"用户补充的问题或改进建议：{suggestion}")
                    for scene in state.scenes if scene.id in suggested_scene_ids
                )
            issues = list(dict.fromkeys(issues))
            if not issues:
                raise ValueError("检查结果中没有可自动修复的具体场景")

            applied = list({
                item.plan_culture_mechanism_id: item
                for item in self.store.load_applied(project_id)
            }.values())
            adaptation_summary = "; ".join(
                f"{item.plan_culture_mechanism_id} -> "
                f"{item.chosen_option.replacement_definition}"
                for item in applied
            )
            full_check_context = "\n".join(
                f"- {item.scene_id or '全局'}：{item.description}"
                + (f"；证据：{item.evidence}" if item.evidence else "")
                for item in selected_issues
            )
            repair_brief = adaptation_summary
            if suggestion:
                scope = "、".join(scene.id for scene in state.scenes if scene.id in suggested_scene_ids)
                feedback = (
                    f"\n本轮用户明确指令（最高优先级，适用场景：{scope}）：\n{suggestion}"
                )
                repair_brief += (
                    feedback
                    + "\n落实用户指令；若它明确统一或替换了历史方案，以本轮指令为准。"
                    "同时保持未被指令改变的事实和情节衔接一致。"
                )
                adaptation_summary += feedback
            if full_check_context:
                repair_brief += (
                    "\n本轮需要解决的错误及用户确认需要修改的项目如下。各场景必须采用同一套人物、分数、"
                    "规则和因果事实，不能只修当前一句：\n" + full_check_context
                )
            candidate = state.model_copy(deep=True)
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                kept_items = [
                    "用户确认当前正文无需因此修改；如旧结构元数据与当前正文冲突，"
                    "应更新元数据而非改回正文："
                    + report.issues[index].description
                    + (
                        f"；当前正文证据：{report.issues[index].evidence}"
                        if report.issues[index].evidence else ""
                    )
                    for index in report.kept_issue_indexes
                    if 0 <= index < len(report.issues)
                ] + [
                    f"用户接受当前正文对 {check.commitment_id} 的处理；"
                    f"需要时同步更新该承诺的旧描述：{check.explanation}"
                    for check in report.commitment_checks
                    if check.commitment_id in report.kept_commitment_ids
                ]
                # A global fact baseline is valuable for identity, timeline and
                # numeric conflicts. Editorial notes and stale terminology have
                # explicit scene-level targets; planning a new global canon for
                # those adds cost and can manufacture ambiguity from historical
                # adaptation options.
                if any(
                    item.issue_type == IssueType.FACT_CONFLICT
                    for item in selected_issues
                ):
                    issues = await self.rewriter.prepare_repair(
                        candidate, issues, repair_brief,
                        source_script=meta.script_text,
                        kept_items=kept_items,
                        required_payoff_commitment_ids=required_payoff_commitment_ids,
                    )
                repaired_scene_ids = await self.rewriter.repair(
                    candidate,
                    issues,
                    repair_brief,
                )
                next_report = await self.verifier.verify(
                    candidate,
                    changed_scene_ids=repaired_scene_ids,
                    applied_adaptations_summary=adaptation_summary,
                )
            self.store.save_state(
                project_id,
                candidate,
                kind="repair",
                description="按一致性检查结果修复场景并重新检查",
                changed_scene_ids=repaired_scene_ids,
                applied_option=(
                    {"repair_suggestion": suggestion, "repair_scene_ids": [
                        scene.id for scene in state.scenes if scene.id in suggested_scene_ids
                    ]}
                    if suggestion else None
                ),
            )
            self._remember_report(project_id, candidate.version, next_report)
            return next_report

    def _remember_report(self, project_id: str, version: int, report: VerifyReport) -> None:
        self._set_review_token(version, report)
        self._verification_reports[project_id] = (version, report.model_copy(deep=True))
        database = getattr(self.store, "database", None)
        if database is not None:
            with database.transaction(immediate=True) as connection:
                connection.execute(
                    """INSERT INTO verification_reports VALUES(?,?,?)
                    ON CONFLICT(project_id) DO UPDATE SET state_version=excluded.state_version,
                    payload_json=excluded.payload_json""",
                    (project_id, version, report.model_dump_json()),
                )

    def latest_report(self, project_id: str) -> VerifyReport | None:
        state = self.store.load_state(project_id)
        cached = self._verification_reports.get(project_id)
        if state is not None and cached is not None and cached[0] == state.version:
            return cached[1].model_copy(deep=True)
        database = getattr(self.store, "database", None)
        if database is None:
            return None
        with database.transaction() as connection:
            row = connection.execute(
                """SELECT v.payload_json FROM verification_reports v JOIN states s
                ON v.project_id=s.project_id AND v.state_version=s.version WHERE v.project_id=?""",
                (project_id,),
            ).fetchone()
        if not row or state is None:
            return None
        report = VerifyReport.model_validate_json(row[0])
        self._set_review_token(state.version, report)
        return report

    @staticmethod
    def _set_review_token(version: int, report: VerifyReport) -> None:
        payload = f"{version}:" + report.model_dump_json(exclude={
            "review_token", "kept_issue_indexes", "kept_commitment_ids",
            "overall_status", "consistency_score",
        })
        report.review_token = hashlib.sha256(payload.encode()).hexdigest()

    async def render_target_script(self, project_id: str) -> TargetScript:
        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            cached = self.store.load_target_script(project_id)
            if cached is not None:
                return cached
            if get_config().share.enabled:
                report = self.latest_report(project_id)
                if report is None or report.overall_status in {"not_run", "fail"}:
                    raise VerificationBlocked("当前剧本尚未通过检查，请先完成检查并处理阻塞问题。")
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy, meta.owner_id):
                target_script = await self.renderer.render(state)
            self.store.save_target_script(project_id, target_script)
            return target_script


def build_default_workflow(client: LLMClient) -> StoryBridgeWorkflow:
    cfg = get_config()
    store = SQLiteProjectStore(
        cfg.storage.database_file,
        artifacts_dir=cfg.storage.projects_dir,
    )
    store.import_legacy_projects(cfg.storage.projects_dir)
    return StoryBridgeWorkflow(store, client)
