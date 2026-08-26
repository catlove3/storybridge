from __future__ import annotations

from pydantic import BaseModel

from app.config import StorageConfig, get_config
from app.llm import LLMClient
from app.schemas import (
    AdaptationPlan,
    AppliedAdaptation,
    PropagationResult,
    StoryState,
    VerificationIssue,
    VerifyReport,
)
from app.storage import MarketProfile, ProjectMeta, ProjectStore
from app.workflow.friction import FrictionDetector
from app.workflow.parser import StoryParser
from app.workflow.planner import AdaptationPlanner
from app.workflow.rewriter import SceneRewriter
from app.workflow.verifier import Verifier


class ApplyResult(BaseModel):
    applied: AppliedAdaptation
    report: VerifyReport
    repair_rounds: int
    repaired_scene_ids: list[str]


class StoryBridgeWorkflow:
    def __init__(self, store: ProjectStore, client: LLMClient, max_repair_rounds: int = 2) -> None:
        self.store = store
        self.max_repair_rounds = max_repair_rounds
        self.parser = StoryParser(client)
        self.detector = FrictionDetector(client)
        self.planner = AdaptationPlanner(client)
        self.rewriter = SceneRewriter(client)
        self.verifier = Verifier(client)

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
    ) -> ProjectMeta:
        return self.store.create_project(name, script_text, market or MarketProfile())

    async def analyze(self, project_id: str) -> StoryState:
        meta = self.store.load_meta(project_id)
        if meta is None:
            raise KeyError(f"unknown project: {project_id}")

        state = await self.parser.parse(meta.script_text, target_market=meta.market.market)
        state.target_market = meta.market.market
        state.audience = meta.market.audience
        state.format = meta.market.format
        state.genre = meta.market.genre

        state = await self.detector.apply(state, target_market=meta.market.market)
        self.store.save_state(
            project_id,
            state,
            kind="initial_parse",
            description="Story Parser + Culture Friction Detection",
        )
        return state

    async def plan(self, project_id: str, mechanism_id: str) -> AdaptationPlan:
        state = self.require_state(project_id)
        cached = self.store.load_plan(project_id, mechanism_id)
        if cached is not None:
            return cached
        meta = self.store.load_meta(project_id)
        profile = meta.market.model_dump() if meta else {}
        plan = await self.planner.plan(state, mechanism_id, target_market_profile=profile)
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
    ) -> ApplyResult:
        state = self.require_state(project_id)
        plan = await self.plan(project_id, mechanism_id)
        option = plan.option_by_label(option_label)
        if option is None:
            raise KeyError(
                f"option '{option_label}' not found for {mechanism_id}; "
                f"available: {[o.option_label for o in plan.options]}"
            )

        propagation = SceneRewriter.build_propagation(state, mechanism_id)
        applied = await self.rewriter.apply(state, mechanism_id, option, propagation)

        self.store.save_state(
            project_id,
            state,
            kind="adaptation_applied",
            description=(
                f"applied option {option.option_label} ({option.strategy.value}) "
                f"for {mechanism_id}: {option.title}"
            ),
            changed_scene_ids=applied.rewritten_scene_ids,
            applied_option=option.model_dump(mode="json"),
        )
        self.store.append_applied(project_id, applied)

        report = VerifyReport()
        repaired_scene_ids: list[str] = []
        rounds = 0

        if auto_verify_and_repair:
            summary = f"{plan.original_name} -> {option.replacement_definition}"
            report = await self.verifier.verify(
                state,
                changed_scene_ids=applied.rewritten_scene_ids,
                applied_adaptations_summary=summary,
            )

            while report.blocking_issues and rounds < self.max_repair_rounds:
                issues = [
                    (i.scene_id, i.description) for i in report.blocking_issues if i.scene_id
                ]
                if not issues:
                    break
                rounds += 1
                brief = f"{plan.original_name} -> {option.replacement_definition}"
                repaired_scene_ids.extend(await self.rewriter.repair(state, issues, brief))
                self.store.save_state(
                    project_id,
                    state,
                    kind="repair",
                    description=f"repair round {rounds}: {len(repaired_scene_ids)} scene(s)",
                    changed_scene_ids=repaired_scene_ids,
                )
                report = await self.verifier.verify(
                    state,
                    changed_scene_ids=repaired_scene_ids,
                    applied_adaptations_summary=summary,
                )

        return ApplyResult(
            applied=applied,
            report=report,
            repair_rounds=rounds,
            repaired_scene_ids=repaired_scene_ids,
        )

    async def verify(self, project_id: str) -> VerifyReport:
        state = self.require_state(project_id)
        applied = self.store.load_applied(project_id)
        summary = "; ".join(
            f"{a.plan_culture_mechanism_id} -> {a.chosen_option.replacement_definition}"
            for a in applied
        )
        return await self.verifier.verify(state, applied_adaptations_summary=summary)


def build_default_workflow(client: LLMClient) -> StoryBridgeWorkflow:
    cfg = get_config()
    store = ProjectStore(cfg.storage.projects_dir)
    return StoryBridgeWorkflow(store, client)
