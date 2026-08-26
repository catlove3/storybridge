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
        penalty = 0.15 * errors + 0.05 * warnings + 0.2 * violated
        self.consistency_score = max(0.0, round(1.0 - penalty, 3))
        return self.consistency_score
