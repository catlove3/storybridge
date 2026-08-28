from __future__ import annotations

import json
import time

import httpx

from app.config import ProfileConfig, api_key_for
from app.llm.base import LLMRequest, LLMResponse


class OpenAICompatClient:
    _TRANSIENT_GATEWAY_STATUSES = {502, 503, 504}

    def __init__(
        self,
        profile: ProfileConfig,
        profile_name: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.profile = profile
        self.profile_name = profile_name
        self._transport = transport
        self._unsupported_extra_keys: set[str] = set()

    @staticmethod
    def _content_text(content: object) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            if text_parts:
                return "".join(text_parts)
            return json.dumps(content, ensure_ascii=False)
        return str(content)

    @staticmethod
    def _message_text(data: dict) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("OpenAI-compatible response has no choices")
        message = choices[0].get("message") or {}
        return OpenAICompatClient._content_text(message.get("content"))

    @classmethod
    async def _stream_response_data(cls, response: httpx.Response) -> dict:
        content_parts: list[str] = []
        model = ""
        usage: dict = {}
        finish_reason = None

        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            raw_event = line[5:].strip()
            if not raw_event or raw_event == "[DONE]":
                continue
            event = json.loads(raw_event)
            if isinstance(event.get("error"), dict):
                raise RuntimeError(
                    f"OpenAI-compatible stream error: {event['error']}"
                )
            model = event.get("model") or model
            usage = event.get("usage") or usage
            choices = event.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or choice.get("message") or {}
            content_parts.append(cls._content_text(delta.get("content")))
            finish_reason = choice.get("finish_reason") or finish_reason

        return {
            "model": model,
            "choices": [
                {
                    "message": {"content": "".join(content_parts)},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage,
        }

    def _drop_unsupported_optional(self, payload: dict, error_text: str) -> bool:
        candidates = ["frequency_penalty", "response_format"]
        candidates.extend(
            key for key in self.profile.extra_body if key in payload
        )
        if "stream" in payload:
            candidates.append("stream")

        for key in candidates:
            if key in payload and key.lower() in error_text:
                payload.pop(key, None)
                if key in self.profile.extra_body:
                    self._unsupported_extra_keys.add(key)
                return True

        for key in candidates:
            if key in payload:
                payload.pop(key, None)
                if key in self.profile.extra_body:
                    self._unsupported_extra_keys.add(key)
                return True
        return False

    async def complete(self, request: LLMRequest) -> LLMResponse:
        temperature = (
            request.temperature
            if request.temperature is not None
            else self.profile.temperature
        )
        # Some compatible APIs (including current GLM docs) reject exactly 0.
        # 0.01 preserves near-deterministic analytical steps without changing
        # the workflow-level generation settings.
        if temperature <= 0:
            temperature = 0.01

        payload: dict = {
            "model": self.profile.model,
            "messages": request.to_messages(),
            "temperature": temperature,
            "max_tokens": request.max_tokens or self.profile.max_tokens,
        }
        if request.frequency_penalty is not None:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.json_mode and self.profile.json_mode:
            payload["response_format"] = {"type": "json_object"}
        for key, value in self.profile.extra_body.items():
            if key not in self._unsupported_extra_keys:
                payload[key] = value
        if self.profile.stream:
            payload["stream"] = True

        headers = {"Content-Type": "application/json"}
        api_key = api_key_for(self.profile)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = f"{self.profile.base_url.rstrip('/')}/chat/completions"
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=120, transport=self._transport) as client:
            # Not every OpenAI-compatible implementation supports JSON mode.
            # Validation failures are commonly reported as either 400 or 422;
            # retry without unsupported optional parameters. The JSON fallback
            # still relies on the existing strict prompt, extractor, Pydantic
            # validation and correction loop.
            gateway_retries = 0
            while True:
                if payload.get("stream"):
                    async with client.stream(
                        "POST", url, json=payload, headers=headers
                    ) as response:
                        if (
                            response.status_code in self._TRANSIENT_GATEWAY_STATUSES
                            and gateway_retries < 1
                        ):
                            await response.aread()
                            gateway_retries += 1
                            continue
                        if response.status_code in {400, 422}:
                            error_text = (await response.aread()).decode(
                                errors="replace"
                            ).lower()
                            if self._drop_unsupported_optional(payload, error_text):
                                continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "")
                        if "text/event-stream" in content_type:
                            data = await self._stream_response_data(response)
                        else:
                            await response.aread()
                            data = response.json()
                        break

                response = await client.post(url, json=payload, headers=headers)
                if (
                    response.status_code in self._TRANSIENT_GATEWAY_STATUSES
                    and gateway_retries < 1
                ):
                    gateway_retries += 1
                    continue
                if response.status_code in {400, 422}:
                    if self._drop_unsupported_optional(
                        payload, response.text.lower()
                    ):
                        continue
                response.raise_for_status()
                data = response.json()
                break
        latency_ms = int((time.monotonic() - started) * 1000)

        usage = data.get("usage") or {}
        text = self._message_text(data)
        return LLMResponse(
            text=text,
            model=data.get("model") or self.profile.model,
            profile_name=self.profile_name,
            step=request.step,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=latency_ms,
        )
