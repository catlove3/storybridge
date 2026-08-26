from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

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


class AdaptationPlan(BaseModel):
    culture_mechanism_id: str
    original_name: str
    friction_level: Level = Level.MEDIUM
    options: list[AdaptationOption]

    def option_by_label(self, label: str) -> AdaptationOption | None:
        return next((o for o in self.options if o.option_label.upper() == label.upper()), None)


class AppliedAdaptation(BaseModel):
    plan_culture_mechanism_id: str
    chosen_option: AdaptationOption
    propagation: PropagationResult
    rewritten_scene_ids: list[str]
    notes: str = ""
