from __future__ import annotations

import json

import httpx
from pydantic import BaseModel

from app.config import ProfileConfig, api_key_for, get_config
from app.llm.base import LLMRequest
from app.llm.openai_compat import OpenAICompatClient
from app.llm.structured import generate_structured


def test_default_profile_is_overridden_by_llm_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-secret")
    monkeypatch.setenv("LLM_MODEL", "example-model")
    get_config.cache_clear()
    try:
        config = get_config()
        profile = config.llm.profiles[config.llm.default_profile]
        assert profile.base_url == "https://llm.example.test/v1"
        assert profile.model == "example-model"
        assert profile.api_key_env == "LLM_API_KEY"
        assert api_key_for(profile) == "test-secret"
    finally:
        get_config.cache_clear()


async def test_openai_compatible_request_uses_bearer_and_text_parts():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "served-model",
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "{\"ok\":"},
                                {"type": "text", "text": "true}"},
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            },
        )

    profile = ProfileConfig(
        base_url="https://llm.example.test/v1",
        api_key_env="TEST_LLM_KEY",
        model="requested-model",
        json_mode=True,
    )
    client = OpenAICompatClient(
        profile,
        "test",
        transport=httpx.MockTransport(handler),
    )

    import os

    old_key = os.environ.get("TEST_LLM_KEY")
    os.environ["TEST_LLM_KEY"] = "secret"
    try:
        response = await client.complete(
            LLMRequest(
                step="parse_story",
                system_prompt="Return JSON.",
                user_prompt="Go",
                json_mode=True,
                temperature=0.0,
            )
        )
    finally:
        if old_key is None:
            os.environ.pop("TEST_LLM_KEY", None)
        else:
            os.environ["TEST_LLM_KEY"] = old_key

    assert response.text == '{"ok":true}'
    assert response.model == "served-model"
    assert response.prompt_tokens == 7
    assert requests[0].headers["authorization"] == "Bearer secret"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "requested-model"
    assert payload["temperature"] == 0.01
    assert payload["response_format"] == {"type": "json_object"}


async def test_streaming_request_uses_extra_body_and_retries_one_gateway_error():
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return httpx.Response(504, text="gateway timeout")
        body = "\n\n".join(
            [
                'data: {"model":"glm-test","choices":[{"delta":{"content":"{\\"ok\\":"}}]}',
                'data: {"choices":[{"delta":{"content":"true}"},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(
            200,
            text=body,
            headers={"content-type": "text/event-stream"},
        )

    profile = ProfileConfig(
        base_url="https://llm.example.test/v1",
        api_key_env="NO_KEY",
        model="glm-test",
        stream=True,
        extra_body={"thinking": {"type": "disabled"}},
    )
    client = OpenAICompatClient(
        profile,
        "test",
        transport=httpx.MockTransport(handler),
    )

    response = await client.complete(
        LLMRequest(
            step="parse_story",
            system_prompt="Return JSON.",
            user_prompt="Go",
            json_mode=True,
        )
    )

    assert response.text == '{"ok":true}'
    assert response.model == "glm-test"
    assert response.prompt_tokens == 5
    assert response.completion_tokens == 2
    assert len(payloads) == 2
    assert payloads[0]["stream"] is True
    assert payloads[0]["thinking"] == {"type": "disabled"}


async def test_unsupported_extra_body_is_removed_and_cached():
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if "thinking" in payload:
            return httpx.Response(
                422,
                json={"error": {"message": "thinking is not supported"}},
            )
        return httpx.Response(
            200,
            json={
                "model": "compat-model",
                "choices": [{"message": {"content": '{"ok":true}'}}],
            },
        )

    profile = ProfileConfig(
        base_url="https://llm.example.test/v1",
        api_key_env="NO_KEY",
        model="compat-model",
        extra_body={"thinking": {"type": "disabled"}},
    )
    client = OpenAICompatClient(
        profile,
        "test",
        transport=httpx.MockTransport(handler),
    )
    request = LLMRequest(
        step="parse_story",
        system_prompt="Return JSON.",
        user_prompt="Go",
    )

    assert (await client.complete(request)).text == '{"ok":true}'
    assert (await client.complete(request)).text == '{"ok":true}'
    assert len(payloads) == 3
    assert "thinking" in payloads[0]
    assert "thinking" not in payloads[1]
    assert "thinking" not in payloads[2]


class _StructuredResult(BaseModel):
    value: int


async def test_structured_output_unwraps_provider_result_envelope():
    from app.llm import MockLLMClient

    client = MockLLMClient({"wrapped": {"result": {"value": 42}}})
    result = await generate_structured(
        client,
        _StructuredResult,
        step="wrapped",
        system_prompt="Return JSON.",
        user_prompt="Return value 42.",
    )

    assert result.value == 42


async def test_structured_output_falls_back_when_json_mode_is_rejected():
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if "frequency_penalty" in payload:
            return httpx.Response(
                422,
                json={"error": {"message": "frequency_penalty is not supported"}},
            )
        if "response_format" in payload:
            return httpx.Response(
                422,
                json={"error": {"message": "response_format is not supported"}},
            )
        return httpx.Response(
            200,
            json={
                "model": "compat-model",
                "choices": [
                    {
                        "message": {
                            "content": "Result:\n```json\n{\"value\": 42}\n```"
                        }
                    }
                ],
            },
        )

    profile = ProfileConfig(
        base_url="https://llm.example.test/v1",
        api_key_env="NO_KEY",
        model="compat-model",
        json_mode=True,
    )
    client = OpenAICompatClient(
        profile,
        "test",
        transport=httpx.MockTransport(handler),
    )

    result = await generate_structured(
        client,
        _StructuredResult,
        step="test_structured",
        system_prompt="Return JSON.",
        user_prompt="Return value 42.",
        frequency_penalty=0.3,
    )

    assert result.value == 42
    assert len(payloads) == 3
    assert payloads[0]["frequency_penalty"] == 0.3
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert "frequency_penalty" not in payloads[1]
    assert payloads[1]["response_format"] == {"type": "json_object"}
    assert "response_format" not in payloads[2]
