from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")


class ProfileConfig(BaseModel):
    provider: str = "openai_compat"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    model: str
    temperature: float = 0.3
    max_tokens: int = 4096
    json_mode: bool = True
    stream: bool = False
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=8)
    retry_base_delay: float = Field(default=0.5, ge=0, le=30)
    input_cost_per_million_usd: float = Field(default=0.0, ge=0)
    output_cost_per_million_usd: float = Field(default=0.0, ge=0)
    extra_body: dict[str, object] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    default_profile: str = "general"
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    step_routes: dict[str, str] = Field(default_factory=dict)

    def profile_for_step(self, step: str) -> ProfileConfig:
        profile_name = self.step_routes.get(step, self.default_profile)
        return self.profiles[profile_name]


class LoggingConfig(BaseModel):
    sft_log_dir: Path = BACKEND_ROOT / "data" / "sft_logs"
    run_log_dir: Path = BACKEND_ROOT / "data" / "run_logs"
    sft_log_enabled: bool = False
    sft_redact_pii: bool = True
    sft_retention_days: int = Field(default=30, ge=1, le=365)


class SecurityConfig(BaseModel):
    api_keys_env: str = "STORYBRIDGE_API_KEYS"
    default_owner: str = "local"
    max_script_chars: int = Field(default=500_000, ge=1, le=500_000)
    max_active_jobs_per_owner: int = Field(default=4, ge=1, le=100)
    max_job_submissions_per_minute: int = Field(default=30, ge=1, le=10_000)
    max_project_llm_tokens: int = Field(default=1_000_000, ge=0)


class StorageConfig(BaseModel):
    database_file: Path = BACKEND_ROOT / "data" / "storybridge.sqlite3"
    projects_dir: Path = BACKEND_ROOT / "data" / "projects"
    jobs_file: Path = BACKEND_ROOT / "data" / "jobs.json"


class LongTextConfig(BaseModel):
    chunk_threshold_chars: int = Field(default=24_000, ge=1_000, le=500_000)
    chunk_chars: int = Field(default=16_000, ge=500, le=100_000)
    friction_batch_size: int = Field(default=20, ge=1, le=100)


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    long_text: LongTextConfig = Field(default_factory=LongTextConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


@lru_cache
def get_config() -> AppConfig:
    config_path = BACKEND_ROOT / "config" / "models.yaml"
    raw: dict = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(raw)

    for section, field_name in (
        (config.logging, "sft_log_dir"),
        (config.logging, "run_log_dir"),
        (config.storage, "database_file"),
        (config.storage, "projects_dir"),
        (config.storage, "jobs_file"),
    ):
        path = getattr(section, field_name)
        if not path.is_absolute():
            setattr(section, field_name, (BACKEND_ROOT / path).resolve())

    for env_name, section, field_name in (
        ("STORYBRIDGE_DATABASE_FILE", config.storage, "database_file"),
        ("STORYBRIDGE_PROJECTS_DIR", config.storage, "projects_dir"),
        ("STORYBRIDGE_JOBS_FILE", config.storage, "jobs_file"),
        ("STORYBRIDGE_SFT_LOG_DIR", config.logging, "sft_log_dir"),
        ("STORYBRIDGE_RUN_LOG_DIR", config.logging, "run_log_dir"),
    ):
        override = os.environ.get(env_name, "").strip()
        if override:
            setattr(section, field_name, Path(override).expanduser().resolve())

    if (
        "STORYBRIDGE_DATABASE_FILE" not in os.environ
        and os.environ.get("STORYBRIDGE_PROJECTS_DIR", "").strip()
    ):
        config.storage.database_file = (
            config.storage.projects_dir.parent / "storybridge.sqlite3"
        ).resolve()

    # The default profile is the normal runtime path for every current skill.
    # Keep advanced per-step profiles in YAML, while allowing one .env file to
    # switch the provider used by the complete workflow.
    profile = config.llm.profiles.get(config.llm.default_profile)
    if profile is not None:
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        if base_url:
            profile.base_url = base_url
        if model:
            profile.model = model
        profile.api_key_env = "LLM_API_KEY"

    return config


def api_key_for(profile: ProfileConfig) -> str:
    return os.environ.get(profile.api_key_env, "")


def api_key_owners(config: AppConfig | None = None) -> dict[str, str]:
    cfg = config or get_config()
    raw = os.environ.get(cfg.security.api_keys_env, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{cfg.security.api_keys_env} must be a JSON object") from exc
    if not isinstance(payload, dict) or not all(
        isinstance(token, str) and token and isinstance(owner, str) and owner
        for token, owner in payload.items()
    ):
        raise ValueError(
            f"{cfg.security.api_keys_env} must map non-empty API keys to owner IDs"
        )
    return payload
