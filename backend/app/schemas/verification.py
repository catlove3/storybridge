from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    STALE_REFERENCE = "stale_reference"
    FACT_CONFLICT = "fact_conflict"
    MOTIVATION_BREAK = "motivation_break"
    COMMITMENT_VIOLATION = "commitment_violation"
    UNRESOLVED_PAYOFF = "unresolved_payoff"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class VerificationIssue(BaseModel):
    issue_type: IssueType
    severity: Severity
    scene_id: str | None = None
    description: str
    evidence: str = ""


class CommitmentCheck(BaseModel):
    commitment_id: str
    status: Literal["preserved", "violated", "needs_review"] = "preserved"
    explanation: str = ""


class VerifyReport(BaseModel):
    issues: list[VerificationIssue] = Field(default_factory=list)
    commitment_checks: list[CommitmentCheck] = Field(default_factory=list)
    checked_scene_ids: list[str] = Field(default_factory=list)
    static_checks_passed: int = Field(default=0, ge=0)
    static_checks_total: int = Field(default=0, ge=0)
    commitments_verified: int = Field(default=0, ge=0)
    commitments_total: int = Field(default=0, ge=0)
    scenes_checked: int = Field(default=0, ge=0)
    scenes_total: int = Field(default=0, ge=0)
    overall_status: Literal["not_run", "pass", "needs_review", "fail"] = "not_run"
    consistency_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="1.0 means no unresolved blocking issues",
    )

    @property
    def blocking_issues(self) -> list[VerificationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    def recompute_score(self) -> float:
        errors = len(self.blocking_issues)
        warnings = sum(1 for i in self.issues if i.severity == Severity.WARNING)
        violated = sum(1 for c in self.commitment_checks if c.status == "violated")
        needs_review = sum(1 for c in self.commitment_checks if c.status == "needs_review")
        scene_coverage_gap = (
            max(0.0, 1.0 - self.scenes_checked / self.scenes_total)
            if self.scenes_total
            else 0.0
        )
        penalty = (
            0.15 * errors
            + 0.05 * warnings
            + 0.2 * violated
            + 0.1 * needs_review
            + 0.2 * scene_coverage_gap
        )
        self.consistency_score = max(0.0, round(1.0 - penalty, 3))

        incomplete_coverage = (
            self.static_checks_passed < self.static_checks_total
            or self.commitments_verified < self.commitments_total
            or self.scenes_checked < self.scenes_total
        )
        if errors or violated:
            self.overall_status = "fail"
        elif warnings or needs_review or incomplete_coverage:
            self.overall_status = "needs_review"
        else:
            self.overall_status = "pass"
        return self.consistency_score
