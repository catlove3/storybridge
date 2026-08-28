from __future__ import annotations

import json
import time
from pathlib import Path

from app.config import LLMConfig, ProfileConfig, get_config
from app.llm.base import LLMClient, LLMRequest, LLMResponse
from app.llm.openai_compat import OpenAICompatClient


class SFTCallLogger:
    def __init__(self, log_dir: Path, enabled: bool = True) -> None:
        self.log_dir = log_dir
        self.enabled = enabled
        if enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def record(self, request: LLMRequest, response: LLMResponse) -> None:
        if not self.enabled:
            return
        entry = {
            "run_id": request.run_id,
            "step": request.step,
            "attempt": request.attempt,
            "prompt_version": request.prompt_version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": response.model,
            "messages": request.to_messages(),
            "completion": response.text,
            "latency_ms": response.latency_ms,
            "http_attempts": response.http_attempts,
            "finish_reason": response.finish_reason,
            "usage": {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
            },
        }
        path = self.log_dir / f"{request.step}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class LLMRouter(LLMClient):
    def __init__(self, config: LLMConfig | None = None, logger: SFTCallLogger | None = None) -> None:
        self._config = config or get_config().llm
        self._logger = logger
        self._clients: dict[str, OpenAICompatClient] = {}

    @property
    def logger(self) -> SFTCallLogger | None:
        return self._logger

    def profile_for_step(self, step: str) -> tuple[str, ProfileConfig]:
        cfg = self._config
        profile_name = cfg.step_routes.get(step, cfg.default_profile)
        return profile_name, cfg.profiles[profile_name]

    def client_for_step(self, step: str) -> OpenAICompatClient:
        profile_name, profile = self.profile_for_step(step)
        if profile_name not in self._clients:
            self._clients[profile_name] = OpenAICompatClient(profile, profile_name)
        return self._clients[profile_name]

    async def complete(self, request: LLMRequest) -> LLMResponse:
        client = self.client_for_step(request.step)
        response = await client.complete(request)
        if self._logger is not None:
            self._logger.record(request, response)
        return response

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()


def build_router() -> LLMRouter:
    app_cfg = get_config()
    logger = SFTCallLogger(
        log_dir=app_cfg.logging.sft_log_dir,
        enabled=app_cfg.logging.sft_log_enabled,
    )
    return LLMRouter(config=app_cfg.llm, logger=logger)
