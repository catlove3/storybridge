from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.schemas import (
    AdaptationPlan,
    DataPolicy,
    EdgeRelation,
    NodeKind,
    PropagationResult,
    Revision,
    StoryState,
    TargetScript,
    VerifyReport,
)
from app.storage import MarketProfile
from app.workflow.engine import ApplyResult


class JobKind(StrEnum):
    ANALYZE = "analyze"
    PLAN = "plan"
    APPLY = "apply"
    VERIFY = "verify"
    RENDER = "render"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: datetime


class ProjectCreated(BaseModel):
    id: str
    name: str


class ProjectDetail(ProjectCreated):
    market: MarketProfile
    analyzed: bool
    data_policy: DataPolicy


class GraphNode(BaseModel):
    id: str
    kind: NodeKind
    label: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: EdgeRelation
    evidence: str
    confidence: float


class StoryGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class JobSubmitted(BaseModel):
    job_id: str
    status: JobStatus


class JobResponse(BaseModel):
    id: str
    kind: JobKind
    project_id: str
    status: JobStatus
    created_at: float
    finished_at: float | None
    result: Any = None
    error: str | None
    idempotency_key: str | None
    progress: float
    cancel_requested: bool


class BibleResponse(BaseModel):
    content: str


class SceneDiffResponse(BaseModel):
    scene_id: str
    before: str
    after: str
    diff: list[str]


class DataExportResponse(BaseModel):
    project: ProjectDetail
    script: str
    state: StoryState | None
    plans: list[AdaptationPlan]
    revisions: list[Revision]
    adaptations: list[dict[str, Any]]
    target_script: TargetScript | None


class DeleteProjectResponse(BaseModel):
    deleted: bool
    project_id: str
    sft_samples_deleted: int


class RuntimePolicyResponse(BaseModel):
    authentication_required: bool
    provider_endpoint: str
    model: str
    sft_collection_enabled: bool
    sft_redaction_enabled: bool
    sft_retention_days: int
    max_script_chars: int


class StateSummaryResponse(BaseModel):
    version: int
    characters: int
    scenes: int
    events: int
    settings: int
    culture_mechanisms: list[dict[str, Any]]
    commitments: list[dict[str, Any]]
    dependencies: int
    high_friction_ids: list[str]


__all__ = [
    "ApplyResult",
    "BibleResponse",
    "DataExportResponse",
    "DeleteProjectResponse",
    "JobKind",
    "JobResponse",
    "JobStatus",
    "JobSubmitted",
    "ProjectCreated",
    "ProjectDetail",
    "ProjectSummary",
    "PropagationResult",
    "StateSummaryResponse",
    "SceneDiffResponse",
    "RuntimePolicyResponse",
    "StoryGraphResponse",
    "StoryState",
    "TargetScript",
    "VerifyReport",
]
