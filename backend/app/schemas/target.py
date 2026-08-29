from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TargetScene(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(pattern=r"^S\d+$")
    title: str = ""
    summary: str = ""
    text: str = Field(min_length=1)


class TargetScript(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_state_version: int = Field(default=0, ge=0)
    source_language: str = "zh-CN"
    target_language: str = Field(min_length=1)
    target_locale: str = ""
    scenes: list[TargetScene] = Field(min_length=1)

    @model_validator(mode="after")
    def _scene_ids_must_be_unique(self) -> TargetScript:
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("target script scene ids must be unique")
        return self

    @property
    def text(self) -> str:
        return "\n\n".join(f"【{scene.id}】\n{scene.text}" for scene in self.scenes)
