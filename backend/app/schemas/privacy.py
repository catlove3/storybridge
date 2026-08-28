from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataPolicy(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sft_opt_in: bool = False
    content_source: str = Field(default="", max_length=200)
    license: str = Field(default="", max_length=200)
    consent_note: str = Field(default="", max_length=500)
    retention_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def _opt_in_requires_provenance(self) -> DataPolicy:
        if self.sft_opt_in and not (
            self.content_source and self.license and self.consent_note
        ):
            raise ValueError(
                "SFT opt-in requires content_source, license, and consent_note"
            )
        return self
