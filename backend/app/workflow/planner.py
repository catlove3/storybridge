from __future__ import annotations

from app.graph import StoryGraph
from app.llm import LLMClient
from app.llm.structured import generate_structured
from app.prompts import plan_adaptation_system, plan_adaptation_user
from app.schemas import AdaptationPlan, CultureMechanism, StoryState


class AdaptationPlanner:
    step_name = "plan_adaptation"

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def _related_context(self, state: StoryState, mechanism: CultureMechanism) -> dict:
        graph = StoryGraph(state)
        neighbors = (
            list(graph.graph.successors(mechanism.id)) + list(graph.graph.predecessors(mechanism.id))
            if graph.has_node(mechanism.id)
            else []
        )

        scene_summaries = [
            {"id": s.id, "summary": s.summary}
            for s in state.scenes
            if s.id in set(mechanism.scene_ids) | {n for n in neighbors if n.startswith("S")}
        ]
        events = [
            {"id": e.id, "description": e.description}
            for e in state.events
            if e.id in neighbors
        ]
        commitments = [
            {"id": nc.id, "description": nc.description}
            for nc in state.commitments
            if nc.id in neighbors or nc.must_preserve
        ]
        dependency_edges = [
            d.model_dump()
            for d in state.dependencies
            if mechanism.id in (d.source_id, d.target_id)
        ]
        return {
            "touching_scenes": scene_summaries,
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
        mechanism = next((m for m in state.culture_mechanisms if m.id == mechanism_id), None)
        if mechanism is None:
            raise KeyError(f"unknown culture mechanism: {mechanism_id}")

        profile = target_market_profile or {
            "market": state.target_market,
            "audience": state.audience,
            "format": state.format,
            "genre": state.genre,
        }
        context = self._related_context(state, mechanism)

        return await generate_structured(
            self.client,
            AdaptationPlan,
            step=self.step_name,
            system_prompt=plan_adaptation_system(),
            user_prompt=plan_adaptation_user(
                mechanism.model_dump(),
                context,
                profile,
            ),
        )
