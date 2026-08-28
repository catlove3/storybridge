from __future__ import annotations

import hashlib
import json
import logging
import re
import tempfile
import threading
import time
from pathlib import Path

from app.config import LLMConfig, ProfileConfig, get_config
from app.llm.base import LLMClient, LLMRequest, LLMResponse
from app.llm.openai_compat import OpenAICompatClient
from app.privacy import current_data_context

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?i)\b(?:sk|key)-[A-Za-z0-9_-]{12,}\b"),
)


def _blake2b(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=32).hexdigest()


def _redact(text: str) -> str:
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class SFTCallLogger:
    def __init__(
        self,
        log_dir: Path,
        enabled: bool = False,
        *,
        redact_pii: bool = True,
        retention_days: int = 30,
    ) -> None:
        self.log_dir = log_dir
        self.enabled = enabled
        self.redact_pii = redact_pii
        self.retention_days = retention_days
        if enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def record(self, request: LLMRequest, response: LLMResponse) -> None:
        context = current_data_context()
        policy = context.policy
        if not self.enabled or not policy.sft_opt_in or not context.project_id:
            return
        messages = request.to_messages()
        completion = response.text
        if self.redact_pii:
            messages = [
                {**message, "content": _redact(message["content"])}
                for message in messages
            ]
            completion = _redact(completion)
        entry = {
            "project_id": context.project_id,
            "run_id": request.run_id,
            "step": request.step,
            "attempt": request.attempt,
            "prompt_version": request.prompt_version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": response.model,
            "messages": messages,
            "completion": completion,
            "prompt_blake2b": _blake2b(
                json.dumps(request.to_messages(), ensure_ascii=False, sort_keys=True)
            ),
            "completion_blake2b": _blake2b(response.text),
            "provenance": {
                "content_source": policy.content_source,
                "license": policy.license,
                "consent_note": policy.consent_note,
            },
            "consent": True,
            "quality_status": "unreviewed",
            "redacted": self.redact_pii,
            "retention_days": min(policy.retention_days, self.retention_days),
            "created_at": time.time(),
            "latency_ms": response.latency_ms,
            "http_attempts": response.http_attempts,
            "finish_reason": response.finish_reason,
            "usage": {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
            },
        }
        safe_step = re.sub(r"[^a-zA-Z0-9_-]", "_", request.step)[:100] or "unknown"
        path = self.log_dir / f"{safe_step}.jsonl"
        self._prune(path)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _prune(self, path: Path) -> None:
        if not path.exists():
            return
        now = time.time()
        kept: list[str] = []
        changed = False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                retention_days = min(
                    int(entry.get("retention_days", self.retention_days)),
                    self.retention_days,
                )
                created_at = float(entry.get("created_at", now))
                if now - created_at <= retention_days * 86400:
                    kept.append(line)
                else:
                    changed = True
            except (TypeError, ValueError, json.JSONDecodeError):
                changed = True
        if changed:
            self._replace_lines(path, kept)

    @staticmethod
    def _replace_lines(path: Path, lines: list[str]) -> None:
        descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        temporary = Path(name)
        try:
            with open(descriptor, "w", encoding="utf-8", closefd=True) as handle:
                handle.write("\n".join(lines) + ("\n" if lines else ""))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def delete_project(self, project_id: str) -> int:
        if not self.log_dir.exists():
            return 0
        removed = 0
        for path in self.log_dir.glob("*.jsonl"):
            kept: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("project_id") == project_id:
                    removed += 1
                else:
                    kept.append(line)
            self._replace_lines(path, kept)
        return removed


class LLMBudgetExceeded(RuntimeError):
    pass


class RunMetadataLogger:
    """Persistent per-project LLM accounting without prompt or completion text."""

    def __init__(
        self,
        log_dir: Path,
        *,
        max_tokens_per_project: int = 1_000_000,
    ) -> None:
        self.log_dir = log_dir
        self.max_tokens_per_project = max_tokens_per_project
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, project_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)[:200]
        if not safe_id:
            raise ValueError("project_id is required for run metadata")
        return self.log_dir / f"{safe_id}.jsonl"

    @staticmethod
    def _estimated_tokens(text: str) -> int:
        # A character-per-token upper estimate avoids undercounting CJK input.
        return max(1, len(text))

    def entries(self, project_id: str) -> list[dict]:
        path = self._path(project_id)
        if not path.exists():
            return []
        result: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and entry.get("project_id") == project_id:
                result.append(entry)
        return result

    def tokens_used(self, project_id: str) -> int:
        total = 0
        for entry in self.entries(project_id):
            usage = entry.get("usage")
            if not isinstance(usage, dict):
                continue
            try:
                total += max(0, int(usage.get("total_tokens", 0)))
            except (TypeError, ValueError):
                continue
        return total

    def ensure_budget(self, project_id: str) -> None:
        if self.max_tokens_per_project <= 0:
            return
        used = self.tokens_used(project_id)
        if used >= self.max_tokens_per_project:
            raise LLMBudgetExceeded(
                f"project LLM token budget exhausted ({used}/{self.max_tokens_per_project})"
            )

    def record(
        self,
        request: LLMRequest,
        response: LLMResponse,
        *,
        input_cost_per_million_usd: float = 0.0,
        output_cost_per_million_usd: float = 0.0,
    ) -> None:
        context = current_data_context()
        if not context.project_id:
            return
        prompt_text = json.dumps(request.to_messages(), ensure_ascii=False, sort_keys=True)
        prompt_tokens = response.prompt_tokens or self._estimated_tokens(prompt_text)
        completion_tokens = response.completion_tokens or self._estimated_tokens(response.text)
        estimated_cost_usd = (
            prompt_tokens * input_cost_per_million_usd
            + completion_tokens * output_cost_per_million_usd
        ) / 1_000_000
        profile = getattr(response, "profile_name", "")
        entry = {
            "project_id": context.project_id,
            "run_id": request.run_id,
            "step": request.step,
            "attempt": request.attempt,
            "prompt_version": request.prompt_version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": response.model,
            "profile": profile,
            "prompt_blake2b": _blake2b(prompt_text),
            "completion_blake2b": _blake2b(response.text),
            "latency_ms": response.latency_ms,
            "http_attempts": response.http_attempts,
            "finish_reason": response.finish_reason,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "provider_reported": bool(
                    response.prompt_tokens or response.completion_tokens
                ),
            },
            "estimated_cost_usd": round(estimated_cost_usd, 8),
        }
        path = self._path(context.project_id)
        with self._lock, path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def delete_project(self, project_id: str) -> int:
        path = self._path(project_id)
        with self._lock:
            count = len(self.entries(project_id))
            path.unlink(missing_ok=True)
        return count


class LLMRouter(LLMClient):
    def __init__(
        self,
        config: LLMConfig | None = None,
        logger: SFTCallLogger | None = None,
        run_logger: RunMetadataLogger | None = None,
    ) -> None:
        self._config = config or get_config().llm
        self._logger = logger
        self._run_logger = run_logger
        self._clients: dict[str, OpenAICompatClient] = {}

    @property
    def logger(self) -> SFTCallLogger | None:
        return self._logger

    @property
    def run_logger(self) -> RunMetadataLogger | None:
        return self._run_logger

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
        context = current_data_context()
        if self._run_logger is not None and context.project_id:
            self._run_logger.ensure_budget(context.project_id)
        client = self.client_for_step(request.step)
        response = await client.complete(request)
        if self._run_logger is not None:
            _, profile = self.profile_for_step(request.step)
            self._run_logger.record(
                request,
                response,
                input_cost_per_million_usd=profile.input_cost_per_million_usd,
                output_cost_per_million_usd=profile.output_cost_per_million_usd,
            )
        if self._logger is not None:
            self._logger.record(request, response)
        logger.info(
            "llm_call step=%s model=%s run_id=%s attempts=%d latency_ms=%d "
            "prompt_tokens=%d completion_tokens=%d prompt_blake2b=%s completion_blake2b=%s",
            request.step,
            response.model,
            request.run_id,
            response.http_attempts,
            response.latency_ms,
            response.prompt_tokens,
            response.completion_tokens,
            _blake2b(json.dumps(request.to_messages(), ensure_ascii=False, sort_keys=True)),
            _blake2b(response.text),
        )
        return response

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()


def build_router() -> LLMRouter:
    app_cfg = get_config()
    logger = SFTCallLogger(
        log_dir=app_cfg.logging.sft_log_dir,
        enabled=app_cfg.logging.sft_log_enabled,
        redact_pii=app_cfg.logging.sft_redact_pii,
        retention_days=app_cfg.logging.sft_retention_days,
    )
    run_logger = RunMetadataLogger(
        log_dir=app_cfg.logging.run_log_dir,
        max_tokens_per_project=app_cfg.security.max_project_llm_tokens,
    )
    return LLMRouter(config=app_cfg.llm, logger=logger, run_logger=run_logger)
