from __future__ import annotations

import re

from app.llm import LLMClient
from app.llm.structured import generate_structured
from app.prompts import verify_consistency_system, verify_consistency_user
from app.schemas import CommitmentCheck, IssueType, StoryState, VerificationIssue, VerifyReport
from app.workflow.static_checks import merge_reports, run_static_checks


def _norm(text: str) -> str:
    return re.sub(r"[\s，。？！、''""：；,.?!\"':;]", "", text)


class Verifier:
    step_name = "verify_consistency"

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def _digest(self, state: StoryState) -> dict:
        return {
            "characters": [c.model_dump() for c in state.characters],
            "scenes": [
                {
                    "id": s.id,
                    "summary": s.summary,
                    "text": s.text,
                }
                for s in state.scenes
            ],
            "events": [e.model_dump() for e in state.events],
            "settings": [st.model_dump() for st in state.settings],
            "culture_mechanisms": [
                cm.model_dump(exclude={"functions"}) for cm in state.culture_mechanisms
            ],
            "commitments": [nc.model_dump() for nc in state.commitments],
        }

    @staticmethod
    def sanitize(state: StoryState, report: VerifyReport) -> VerifyReport:
        known_scene_ids = {s.id for s in state.scenes}
        known_commitment_ids = {nc.id for nc in state.commitments}
        report.issues = [
            i for i in report.issues if i.scene_id is None or i.scene_id in known_scene_ids
        ]
        report.issues = Verifier._drop_hallucinated_stale_refs(state, report.issues)
        report.commitment_checks = [
            c for c in report.commitment_checks if c.commitment_id in known_commitment_ids
        ]
        checked = {c.commitment_id for c in report.commitment_checks}
        for nc in state.commitments:
            if nc.must_preserve and nc.id not in checked:
                report.commitment_checks.append(
                    CommitmentCheck(
                        commitment_id=nc.id,
                        status="needs_review",
                        explanation="LLM 未覆盖该承诺，保守标记",
                    )
                )
        report.recompute_score()
        return report

    @staticmethod
    def _drop_hallucinated_stale_refs(
        state: StoryState, issues: list[VerificationIssue]
    ) -> list[VerificationIssue]:
        adapted_names = [
            cm.name.strip()
            for cm in state.culture_mechanisms
            if cm.adapted_to and len(cm.name.strip()) >= 2
        ]
        kept: list[VerificationIssue] = []
        for issue in issues:
            if issue.issue_type != IssueType.STALE_REFERENCE or not issue.scene_id:
                kept.append(issue)
                continue
            scene = next((s for s in state.scenes if s.id == issue.scene_id), None)
            if scene is None:
                continue
            scene_text = _norm(scene.text) + _norm(scene.summary)
            evidence_present = _norm(issue.evidence) in scene_text if issue.evidence else False
            name_present = any(_norm(name) in scene_text for name in adapted_names)
            if evidence_present or name_present:
                kept.append(issue)
        return kept

    async def verify(
        self,
        state: StoryState,
        changed_scene_ids: list[str] | None = None,
        applied_adaptations_summary: str = "",
    ) -> VerifyReport:
        report = await generate_structured(
            self.client,
            VerifyReport,
            step=self.step_name,
            system_prompt=verify_consistency_system(),
            user_prompt=verify_consistency_user(
                self._digest(state),
                changed_scene_ids or [],
                applied_adaptations_summary,
            ),
        )
        report = self.sanitize(state, report)
        report.issues = merge_reports(run_static_checks(state), report.issues)
        report.recompute_score()
        return report
