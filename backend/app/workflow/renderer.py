from __future__ import annotations

from app.llm import LLMClient
from app.schemas import StoryState, TargetScript
from app.skills import RENDER_TARGET_SCRIPT, SkillSpec


class TargetScriptRenderer:
    def __init__(
        self,
        client: LLMClient,
        skill: SkillSpec = RENDER_TARGET_SCRIPT,
    ) -> None:
        self.client = client
        self.skill = skill

    async def render(self, state: StoryState) -> TargetScript:
        expected_scene_ids = [scene.id for scene in state.scenes]

        def validate_result(result: TargetScript) -> None:
            returned_scene_ids = [scene.id for scene in result.scenes]
            if returned_scene_ids != expected_scene_ids:
                raise ValueError(
                    "target script must preserve the exact scene id order: "
                    f"expected {expected_scene_ids}, got {returned_scene_ids}"
                )
            if result.target_language.casefold() != state.target_language.casefold():
                raise ValueError(
                    "target language mismatch: "
                    f"expected {state.target_language!r}, got {result.target_language!r}"
                )

        result = await self.skill.run(
            self.client,
            result_validator=validate_result,
            localized_state_json=state.model_dump(mode="json"),
            source_language=state.source_language,
            target_language=state.target_language,
            target_locale=state.target_locale,
            style_guide=state.style_guide,
            terminology_map=state.terminology_map,
        )
        result.source_state_version = state.version
        result.source_language = state.source_language
        result.target_language = state.target_language
        result.target_locale = state.target_locale
        return result
