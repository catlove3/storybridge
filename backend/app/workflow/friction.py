from __future__ import annotations

from app.llm import LLMClient
from app.schemas import FrictionDetectionResult, StoryState
from app.skills import DETECT_FRICTIONS, SkillSpec


class FrictionDetector:
    def __init__(
        self,
        client: LLMClient,
        skill: SkillSpec = DETECT_FRICTIONS,
        *,
        batch_size: int = 20,
    ) -> None:
        self.client = client
        self.skill = skill
        self.batch_size = batch_size

    @property
    def step_name(self) -> str:
        return self.skill.name

    def _digest(self, state: StoryState, mechanism_ids: set[str]) -> dict:
        selected = [cm for cm in state.culture_mechanisms if cm.id in mechanism_ids]
        scene_ids = {scene_id for cm in selected for scene_id in cm.scene_ids}
        relevant_scenes = [scene for scene in state.scenes if scene.id in scene_ids]
        character_ids = {
            character_id for scene in relevant_scenes for character_id in scene.character_ids
        }
        relevant_events = [
            event for event in state.events if scene_ids.intersection(event.scene_ids)
        ]
        relevant_commitments = [
            commitment
            for commitment in state.commitments
            if commitment.established_at_scene_id in scene_ids
            or commitment.payoff_scene_id in scene_ids
        ]
        relevant_ids = {
            *mechanism_ids,
            *scene_ids,
            *character_ids,
            *(event.id for event in relevant_events),
            *(commitment.id for commitment in relevant_commitments),
        }
        return {
            "characters": [
                {"id": c.id, "name": c.name, "role": c.role}
                for c in state.characters
                if c.id in character_ids
            ],
            "scenes": [{"id": s.id, "summary": s.summary} for s in relevant_scenes],
            "events": [e.model_dump() for e in relevant_events],
            "settings": [
                setting.model_dump()
                for setting in state.settings
                if any(
                    dependency.source_id == setting.id
                    or dependency.target_id == setting.id
                    for dependency in state.dependencies
                    if dependency.source_id in relevant_ids
                    or dependency.target_id in relevant_ids
                )
            ],
            "culture_mechanisms": [
                {
                    "id": cm.id,
                    "name": cm.name,
                    "description": cm.description,
                    "surface_text": cm.surface_text,
                    "scene_ids": cm.scene_ids,
                }
                for cm in selected
            ],
            "commitments": [
                {
                    "id": nc.id,
                    "description": nc.description,
                    "established_at_scene_id": nc.established_at_scene_id,
                    "payoff_scene_id": nc.payoff_scene_id,
                }
                for nc in relevant_commitments
            ],
            "dependencies": [
                dependency.model_dump()
                for dependency in state.dependencies
                if dependency.source_id in relevant_ids
                or dependency.target_id in relevant_ids
            ],
        }

    async def apply(self, state: StoryState, target_market: str) -> StoryState:
        if not state.culture_mechanisms:
            return state

        mechanisms = state.culture_mechanisms
        results = []
        for start in range(0, len(mechanisms), self.batch_size):
            batch = mechanisms[start : start + self.batch_size]
            expected_ids = {mechanism.id for mechanism in batch}

            def validate_result(
                result: FrictionDetectionResult,
                expected: set[str] = expected_ids,
            ) -> None:
                returned_ids = {mechanism.id for mechanism in result.mechanisms}
                if returned_ids != expected:
                    missing = sorted(expected - returned_ids)
                    unknown = sorted(returned_ids - expected)
                    details: list[str] = []
                    if missing:
                        details.append(f"missing: {', '.join(missing)}")
                    if unknown:
                        details.append(f"unknown: {', '.join(unknown)}")
                    raise ValueError(
                        "friction result must cover every input mechanism ("
                        + "; ".join(details)
                        + ")"
                    )

            result = await self.skill.run(
                self.client,
                result_validator=validate_result,
                state_digest_json=self._digest(state, expected_ids),
                target_market=target_market,
            )
            results.extend(result.mechanisms)

        by_id = {mechanism.id: mechanism for mechanism in results}
        dropped = {mechanism.id for mechanism in results if mechanism.drop}
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
            found = by_id[cm.id]
            cm.friction_level = found.friction_level
            cm.narrative_importance = found.narrative_importance
            cm.functions = found.functions
        return state
