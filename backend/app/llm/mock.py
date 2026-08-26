from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable

from app.llm.base import LLMRequest, LLMResponse

ResponseSpec = str | dict | list


class MockLLMClient:
    def __init__(
        self,
        responses: dict[str, ResponseSpec] | None = None,
        handler: Callable[[LLMRequest], str] | None = None,
        model: str = "mock-model",
    ) -> None:
        self.responses: dict[str, ResponseSpec] = responses or {}
        self.handler = handler
        self.model = model
        self.calls: dict[str, list[LLMRequest]] = defaultdict(list)
        self._counters: dict[str, int] = defaultdict(int)

    def set_response(self, step: str, payload: ResponseSpec) -> None:
        self.responses[step] = payload

    def _resolve(self, step: str) -> str:
        payload = self.responses.get(step)
        if payload is None:
            if self.handler is not None:
                return ""
            raise RuntimeError(f"MockLLMClient has no canned response for step '{step}'")
        if isinstance(payload, list):
            index = min(self._counters[step], len(payload) - 1)
            self._counters[step] += 1
            payload = payload[index]
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=False)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls[request.step].append(request)
        if request.step not in self.responses and self.handler is not None:
            text = self.handler(request)
        else:
            text = self._resolve(request.step)
        return LLMResponse(
            text=text,
            model=self.model,
            profile_name="mock",
            step=request.step,
        )
