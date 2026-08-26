from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm import LLMClient
from app.llm.structured import generate_structured
from app.prompts import detect_frictions_system, detect_frictions_user
from app.schemas import FunctionTags, Level, StoryState


class MechanismFriction(BaseModel):
    id: str
    friction_level: Level = Level.MEDIUM
    narrative_importance: Level = Level.MEDIUM
    functions: FunctionTags = Field(default_factory=FunctionTags)


class FrictionDetectionResult(BaseModel):
    mechanisms: list[MechanismFriction] = Field(default_factory=list)


class FrictionDetector:
    step_name = "detect_frictions"

    def __init__(self, client: LLMClient) -> None:
        self.client = client

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

        result = await generate_structured(
            self.client,
            FrictionDetectionResult,
            step=self.step_name,
            system_prompt=detect_frictions_system(),
            user_prompt=detect_frictions_user(self._digest(state), target_market),
        )

        by_id = {m.id: m for m in result.mechanisms}
        for cm in state.culture_mechanisms:
            found = by_id.get(cm.id)
            if found is None:
                continue
            cm.friction_level = found.friction_level
            cm.narrative_importance = found.narrative_importance
            cm.functions = found.functions
        return state
