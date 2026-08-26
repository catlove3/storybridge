from __future__ import annotations

from app.llm import LLMClient
from app.schemas import StoryState
from app.skills import PARSE_STORY, SkillSpec


class StoryParser:
    def __init__(self, client: LLMClient, skill: SkillSpec = PARSE_STORY) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

    async def parse(self, script_text: str, target_market: str = "") -> StoryState:
        return await self.skill.run(
            self.client, script_text=script_text, target_market=target_market
        )
