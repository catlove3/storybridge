from __future__ import annotations

from app.llm import LLMClient
from app.llm.structured import generate_structured
from app.prompts import parse_story_system, parse_story_user
from app.schemas import StoryState


class StoryParser:
    step_name = "parse_story"

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def parse(self, script_text: str, target_market: str = "") -> StoryState:
        return await generate_structured(
            self.client,
            StoryState,
            step=self.step_name,
            system_prompt=parse_story_system(),
            user_prompt=parse_story_user(script_text, target_market),
            max_tokens=8192,
        )
