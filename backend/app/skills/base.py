from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from app.llm import LLMClient
from app.llm.structured import generate_structured

T = TypeVar("T", bound=BaseModel)

PromptFactory = Callable[..., str]


@dataclass(frozen=True, slots=True)
class SkillSpec:
    name: str
    schema: type[BaseModel]
    system_prompt: str
    user_prompt: PromptFactory
    max_tokens: int | None = None
    temperature: float | None = None
    max_retries: int = 2
    frequency_penalty: float | None = None
    postprocessors: tuple[Callable[..., object], ...] = ()

    async def run(
        self,
        client: LLMClient,
        *,
        result_validator: Callable[[BaseModel], None] | None = None,
        **prompt_kwargs,
    ) -> BaseModel:
        return await generate_structured(
            client,
            self.schema,
            step=self.name,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt(**prompt_kwargs),
            max_retries=self.max_retries,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            frequency_penalty=self.frequency_penalty,
            result_validator=result_validator,
        )

    def sft_log_name(self) -> str:
        return f"{self.name}.jsonl"
