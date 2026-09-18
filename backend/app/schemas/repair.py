from pydantic import BaseModel, Field

from .common import EdgeRelation


class RepairFact(BaseModel):
    timeline: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    value: str = Field(min_length=1)
    basis: str = Field(min_length=1, description="原文、用户建议或已选改编方案的依据；不能仅引用检查结论")


class RepairBaseline(BaseModel):
    facts: list[RepairFact] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


class SceneRepairInstruction(BaseModel):
    scene_id: str = Field(pattern=r"^S\d+$")
    instruction: str = Field(min_length=1)


class EventUpdate(BaseModel):
    event_id: str = Field(pattern=r"^E\d+$")
    description: str = Field(min_length=1)
    scene_ids: list[str] = Field(min_length=1)


class CommitmentUpdate(BaseModel):
    commitment_id: str = Field(pattern=r"^NC\d+$")
    description: str = Field(min_length=1)
    established_at_scene_id: str | None
    payoff_scene_id: str | None
    must_preserve: bool


class DependencyEvidenceUpdate(BaseModel):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relation: EdgeRelation
    evidence: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RepairPlan(BaseModel):
    baseline: RepairBaseline
    scene_repairs: list[SceneRepairInstruction] = Field(default_factory=list)
    event_updates: list[EventUpdate] = Field(default_factory=list)
    commitment_updates: list[CommitmentUpdate] = Field(default_factory=list)
    dependency_evidence_updates: list[DependencyEvidenceUpdate] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
