from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import Level


class AdaptationStrategy(str, Enum):
    PRESERVE = "preserve"
    FUNCTIONAL_REPLACEMENT = "functional_replacement"
    PLOT_RECONSTRUCTION = "plot_reconstruction"


class ImpactKind(str, Enum):
    DIRECT_REFERENCE = "direct_reference"
    MOTIVATION = "motivation"
    CAUSAL = "causal"
    PAYOFF = "payoff"
    STRUCTURAL = "structural"


class AffectedScene(BaseModel):
    scene_id: str
    impact_kinds: list[ImpactKind]
    reason_path: list[str] = Field(
        default_factory=list,
        description="node ids traversed from the changed node to this scene",
    )
    evidence: str = ""
    path_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PropagationResult(BaseModel):
    changed_node_id: str
    affected_scenes: list[AffectedScene]
    related_commitment_ids: list[str] = Field(default_factory=list)
    summary: str = ""


class AdaptationOption(BaseModel):
    option_label: str = Field(description="A / B / C")
    strategy: AdaptationStrategy
    title: str
    replacement_definition: str = Field(
        description="what the culture mechanism becomes in the target culture",
    )
    rationale: str
    preserved_functions: list[str] = Field(default_factory=list)
    lost_functions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    @field_validator("option_label", mode="before")
    @classmethod
    def _normalize_option_label(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class AdaptationPlan(BaseModel):
    culture_mechanism_id: str
    original_name: str
    based_on_version: int = Field(default=0, ge=0)
    friction_level: Level = Level.MEDIUM
    options: list[AdaptationOption]

    @model_validator(mode="after")
    def _validate_option_matrix(self) -> AdaptationPlan:
        expected = {
            "A": AdaptationStrategy.PRESERVE,
            "B": AdaptationStrategy.FUNCTIONAL_REPLACEMENT,
            "C": AdaptationStrategy.PLOT_RECONSTRUCTION,
        }
        labels = [option.option_label for option in self.options]
        if len(labels) != 3 or set(labels) != set(expected):
            raise ValueError("options must contain exactly one option for each label A, B, and C")
        for option in self.options:
            required_strategy = expected[option.option_label]
            if option.strategy != required_strategy:
                raise ValueError(
                    f"option {option.option_label} must use strategy {required_strategy.value}"
                )
        self.options.sort(key=lambda option: option.option_label)
        return self

    def option_by_label(self, label: str) -> AdaptationOption | None:
        return next((o for o in self.options if o.option_label.upper() == label.upper()), None)


class AppliedAdaptation(BaseModel):
    plan_culture_mechanism_id: str
    state_version: int = Field(default=0, ge=0)
    operation_id: str | None = None
    chosen_option: AdaptationOption
    propagation: PropagationResult
    rewritten_scene_ids: list[str]
    notes: str = ""


class RewrittenScene(BaseModel):
    id: str
    title: str = ""
    summary: str = ""
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rewritten scene text must not be blank")
        return value
