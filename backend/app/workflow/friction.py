from __future__ import annotations

from app.llm import LLMClient
from app.schemas import StoryState
from app.skills import DETECT_FRICTIONS, SkillSpec


class FrictionDetector:
    def __init__(self, client: LLMClient, skill: SkillSpec = DETECT_FRICTIONS) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

    def _digest(self, state: StoryState) -> dict:
        return {
            "characters": [{"id": c.id, "name": c.name, "role": c.role} for c in state.characters],
            "scenes": [{"id": s.id, "summary": s.summary} for s in state.scenes],
            "events": [e.model_dump() for e in state.events],
            "settings": [st.model_dump() for st in state.settings],
            "culture_mechanisms": [
                {
                    "id": cm.id,
                    "name": cm.name,
                    "description": cm.description,
                    "surface_text": cm.surface_text,
                    "scene_ids": cm.scene_ids,
                }
                for cm in state.culture_mechanisms
            ],
            "commitments": [
                {
                    "id": nc.id,
                    "description": nc.description,
                    "established_at_scene_id": nc.established_at_scene_id,
                    "payoff_scene_id": nc.payoff_scene_id,
                }
                for nc in state.commitments
            ],
            "dependencies": [d.model_dump() for d in state.dependencies],
        }

    async def apply(self, state: StoryState, target_market: str) -> StoryState:
        if not state.culture_mechanisms:
            return state

        result = await self.skill.run(
            self.client,
            state_digest_json=self._digest(state),
            target_market=target_market,
        )

        by_id = {m.id: m for m in result.mechanisms}
        dropped = {m.id for m in result.mechanisms if m.drop}
        if dropped:
            state.dependencies = [
                d
                for d in state.dependencies
                if d.source_id not in dropped and d.target_id not in dropped
            ]
            state.culture_mechanisms = [
                cm for cm in state.culture_mechanisms if cm.id not in dropped
            ]
        for cm in state.culture_mechanisms:
            found = by_id.get(cm.id)
            if found is None:
                continue
            cm.friction_level = found.friction_level
            cm.narrative_importance = found.narrative_importance
            cm.functions = found.functions
        return state
