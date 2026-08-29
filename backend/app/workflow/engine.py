from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import get_config
from app.llm import LLMClient
from app.privacy import project_data_context
from app.schemas import (
    AdaptationPlan,
    AppliedAdaptation,
    DataPolicy,
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
    culture_mechanism_id: str = Field(pattern=r"^CM\d+$")
    option_label: Literal["A", "B", "C"]


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


class StoryBridgeWorkflow:
    def __init__(self, store: ProjectStore, client: LLMClient, max_repair_rounds: int = 2) -> None:
        self.store = store
        self.max_repair_rounds = max_repair_rounds
        self.parser = StoryParser(client)
        self.detector = FrictionDetector(client)
        self.planner = AdaptationPlanner(client)
        self.rewriter = SceneRewriter(client)
        self.renderer = TargetScriptRenderer(client)
        self.verifier = Verifier(client)
        self._project_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

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
            with project_data_context(project_id, meta.data_policy):
                return await self._analyze_locked(project_id)

    async def _analyze_locked(self, project_id: str) -> StoryState:
        meta = self.store.load_meta(project_id)
        if meta is None:
            raise KeyError(f"unknown project: {project_id}")

        state = await self.parser.parse(meta.script_text, target_market=meta.market.market)
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
            with project_data_context(project_id, meta.data_policy):
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
            with project_data_context(project_id, meta.data_policy):
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
        auto_verify_and_repair: bool = True,
        based_on_version: int | None = None,
        operation_id: str | None = None,
    ) -> ApplyResult:
        async with self._project_locks[project_id]:
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy):
                return await self._apply_locked(
                    project_id,
                    mechanism_id,
                    option_label,
                    auto_verify_and_repair,
                    based_on_version,
                    operation_id,
                )

    async def apply_adaptations(
        self,
        project_id: str,
        adaptations: list[AdaptationSelection],
        auto_verify_and_repair: bool = True,
        based_on_version: int | None = None,
        operation_id: str | None = None,
    ) -> BatchApplyResult:
        batch = AdaptationBatch(adaptations=adaptations)
        async with self._project_locks[project_id]:
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy):
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
    ) -> ApplyResult:
        batch_result = await self._apply_many_locked(
            project_id,
            [
                AdaptationSelection.model_construct(
                    culture_mechanism_id=mechanism_id,
                    option_label=option_label,
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
            option = plan.option_by_label(selection.option_label)
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
            applied = self.store.load_applied(project_id)
            summary = "; ".join(
                f"{a.plan_culture_mechanism_id} -> {a.chosen_option.replacement_definition}"
                for a in applied
            )
            with project_data_context(project_id, meta.data_policy):
                return await self.verifier.verify(
                    state, applied_adaptations_summary=summary
                )

    async def render_target_script(self, project_id: str) -> TargetScript:
        async with self._project_locks[project_id]:
            state = self.require_state(project_id)
            cached = self.store.load_target_script(project_id)
            if cached is not None:
                return cached
            meta = self.store.load_meta(project_id)
            if meta is None:
                raise KeyError(f"unknown project: {project_id}")
            with project_data_context(project_id, meta.data_policy):
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
