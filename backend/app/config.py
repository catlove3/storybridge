from __future__ import annotations

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


class LLMConfig(BaseModel):
    default_profile: str = "general"
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    step_routes: dict[str, str] = Field(default_factory=dict)

    def profile_for_step(self, step: str) -> ProfileConfig:
        profile_name = self.step_routes.get(step, self.default_profile)
        return self.profiles[profile_name]


class LoggingConfig(BaseModel):
    sft_log_dir: Path = BACKEND_ROOT / "data" / "sft_logs"
    sft_log_enabled: bool = True


class StorageConfig(BaseModel):
    projects_dir: Path = BACKEND_ROOT / "data" / "projects"


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


@lru_cache
def get_config() -> AppConfig:
    config_path = BACKEND_ROOT / "config" / "models.yaml"
    raw: dict = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)


def api_key_for(profile: ProfileConfig) -> str:
    return os.environ.get(profile.api_key_env, "")
