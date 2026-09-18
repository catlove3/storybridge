from __future__ import annotations

import re

from app.llm import LLMClient
from app.schemas import CultureRefreshResult, Dependency, EdgeRelation, StoryState
from app.skills import REFRESH_CULTURE, SkillSpec

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def culture_mechanism_is_current(state: StoryState, mechanism_id: str) -> bool:
    mechanism = next(
        (item for item in state.culture_mechanisms if item.id == mechanism_id),
        None,
    )
    if mechanism is None:
        return False
    scene_ids = set(mechanism.scene_ids)
    current_text = _compact(
        "\n".join(
            f"{scene.title}\n{scene.summary}\n{scene.text}"
            for scene in state.scenes
            if not scene_ids or scene.id in scene_ids
        )
    )
    probes = [mechanism.name, *mechanism.surface_text]
    return any(_compact(probe) in current_text for probe in probes if _compact(probe))


class CultureRefresher:
    """Re-extract cultural terms after a core-setting rewrite."""

    def __init__(self, client: LLMClient, skill: SkillSpec = REFRESH_CULTURE) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

    @staticmethod
    def _story_payload(state: StoryState) -> dict:
        return {
            "source_language": state.source_language,
            "applied_core_settings": [
                {
                    "id": item.id,
                    "name": item.name,
                    "current_definition": item.adapted_to or item.description,
                }
                for item in state.settings
                if item.adapted_to
            ],
            "scenes": [
                {
                    "id": scene.id,
                    "title": scene.title,
                    "summary": scene.summary,
                    "text": scene.text,
                }
                for scene in state.scenes
            ],
        }

    @staticmethod
    def _validate(state: StoryState, result: CultureRefreshResult) -> None:
        scenes = {scene.id: scene for scene in state.scenes}
        expected_ids = [f"CM{index:02d}" for index in range(1, len(result.culture_mechanisms) + 1)]
        actual_ids = [item.id for item in result.culture_mechanisms]
        if actual_ids != expected_ids:
            raise ValueError(
                "refreshed culture mechanisms must be numbered in first-appearance order: "
                + ", ".join(expected_ids)
            )

        for item in result.culture_mechanisms:
            if not _CJK_RE.search(item.name) or not _CJK_RE.search(item.description):
                raise ValueError(f"{item.id} name and description must use Simplified Chinese")
            if not item.surface_text:
                raise ValueError(f"{item.id} must include verbatim surface_text")
            if not item.scene_ids:
                raise ValueError(f"{item.id} must reference at least one current scene")
            unknown = set(item.scene_ids) - set(scenes)
            if unknown:
                raise ValueError(f"{item.id} references unknown scenes: {sorted(unknown)}")
            compact_phrases = [_compact(phrase) for phrase in item.surface_text if _compact(phrase)]
            if not compact_phrases:
                raise ValueError(f"{item.id} surface_text cannot be blank")
            for scene_id in item.scene_ids:
                scene = scenes[scene_id]
                haystack = _compact(f"{scene.title}\n{scene.summary}\n{scene.text}")
                if not any(phrase in haystack for phrase in compact_phrases):
                    raise ValueError(
                        f"{item.id} has no verbatim surface_text in claimed scene {scene_id}"
                    )

    async def apply(self, state: StoryState, target_market: str) -> StoryState:
        result = await self.skill.run(
            self.client,
            result_validator=lambda value: self._validate(state, value),
            current_story_json=self._story_payload(state),
            target_market=target_market,
        )

        refreshed = [item.model_copy(deep=True) for item in result.culture_mechanisms]
        for item in refreshed:
            item.adapted_to = None
            item.adapted_strategy = None

        # Every old CM edge refers to the pre-rewrite vocabulary. Rebuild only
        # evidence-backed scene references for the freshly extracted nodes.
        state.dependencies = [
            dependency
            for dependency in state.dependencies
            if not dependency.source_id.startswith("CM")
            and not dependency.target_id.startswith("CM")
        ]
        state.culture_mechanisms = refreshed
        scenes = {scene.id: scene for scene in state.scenes}
        for item in refreshed:
            for scene_id in item.scene_ids:
                scene = scenes[scene_id]
                haystack = _compact(f"{scene.title}\n{scene.summary}\n{scene.text}")
                evidence = next(
                    (phrase for phrase in item.surface_text if _compact(phrase) in haystack),
                    item.name,
                )
                state.dependencies.append(
                    Dependency(
                        source_id=scene_id,
                        target_id=item.id,
                        relation=EdgeRelation.REFERENCES,
                        evidence=evidence,
                        confidence=1.0,
                    )
                )
        return state
