from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class Message:
    role: str
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class LLMRequest:
    step: str
    system_prompt: str
    user_prompt: str
    history: list[Message] = field(default_factory=list)
    json_mode: bool = False
    temperature: float | None = None
    max_tokens: int | None = None

    def to_messages(self) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(m.as_dict() for m in self.history)
        messages.append({"role": "user", "content": self.user_prompt})
        return messages


@dataclass(slots=True)
class LLMResponse:
    text: str
    model: str
    profile_name: str
    step: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class LLMClient(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
