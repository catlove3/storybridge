from __future__ import annotations

import time

import httpx

from app.config import ProfileConfig, api_key_for
from app.llm.base import LLMRequest, LLMResponse


class OpenAICompatClient:
    def __init__(self, profile: ProfileConfig, profile_name: str) -> None:
        self.profile = profile
        self.profile_name = profile_name

    async def complete(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.profile.model,
            "messages": request.to_messages(),
            "temperature": request.temperature if request.temperature is not None else self.profile.temperature,
            "max_tokens": request.max_tokens or self.profile.max_tokens,
        }
        if request.frequency_penalty is not None:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.json_mode and self.profile.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        api_key = api_key_for(self.profile)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = f"{self.profile.base_url.rstrip('/')}/chat/completions"
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 400 and "response_format" in payload:
                payload.pop("response_format", None)
                response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        latency_ms = int((time.monotonic() - started) * 1000)

        data = response.json()
        usage = data.get("usage") or {}
        text = data["choices"][0]["message"]["content"] or ""
        return LLMResponse(
            text=text,
            model=data.get("model", self.profile.model),
            profile_name=self.profile_name,
            step=request.step,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=latency_ms,
        )
