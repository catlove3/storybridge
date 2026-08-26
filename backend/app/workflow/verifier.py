from __future__ import annotations

import re

from app.llm import LLMClient
from app.schemas import CommitmentCheck, IssueType, StoryState, VerificationIssue, VerifyReport
from app.skills import VERIFY_CONSISTENCY, SkillSpec
from app.workflow.static_checks import check_stale_references, merge_reports, run_static_checks


def _norm(text: str) -> str:
    return re.sub(r"[\s，。？！、''""：；,.?!\"':;]", "", text)


class Verifier:
    def __init__(self, client: LLMClient, skill: SkillSpec = VERIFY_CONSISTENCY) -> None:
        self.client = client
        self.skill = skill

    @property
    def step_name(self) -> str:
        return self.skill.name

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
            "events": [
                {"id": e.id, "description": e.description, "_note": "结构元数据，非场景文本"}
                for e in state.events
            ],
            "settings": [
                {"id": st.id, "description": st.description, "_note": "结构元数据，非场景文本"}
                for st in state.settings
            ],
            "culture_mechanisms": [
                {
                    "id": cm.id,
                    "name": cm.name,
                    "adapted_to": cm.adapted_to,
                    "adapted_strategy": cm.adapted_strategy,
                }
                for cm in state.culture_mechanisms
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
        report.issues = Verifier._cross_check_stale_refs(state, report.issues)
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
    def _cross_check_stale_refs(
        state: StoryState, issues: list[VerificationIssue]
    ) -> list[VerificationIssue]:
        static_stale_scenes = {i.scene_id for i in check_stale_references(state)}
        kept: list[VerificationIssue] = []
        for issue in issues:
            if issue.issue_type != IssueType.STALE_REFERENCE or not issue.scene_id:
                kept.append(issue)
                continue
            scene = next((s for s in state.scenes if s.id == issue.scene_id), None)
            if scene is None:
                continue
            scene_text = _norm(scene.text) + _norm(scene.summary)
            if issue.scene_id in static_stale_scenes:
                kept.append(issue)
                continue

            probes: set[str] = set()
            for cm in state.culture_mechanisms:
                if not cm.adapted_to:
                    continue
                for phrase in (cm.name, *cm.surface_text):
                    probe = phrase.strip("的了着有没")
                    if len(probe) >= 2:
                        probes.add(_norm(probe))

            evidence_text = _norm(issue.evidence or "")
            evidence_has_old_term = any(p in evidence_text for p in probes)
            scene_has_old_term = any(p in scene_text for p in probes)
            if evidence_has_old_term and scene_has_old_term:
                kept.append(issue)
        return kept

    async def verify(
        self,
        state: StoryState,
        changed_scene_ids: list[str] | None = None,
        applied_adaptations_summary: str = "",
    ) -> VerifyReport:
        report = await self.skill.run(
            self.client,
            state_digest_json=self._digest(state),
            changed_scene_ids=changed_scene_ids or [],
            applied_adaptations_summary=applied_adaptations_summary,
        )
        report = self.sanitize(state, report)
        report.issues = merge_reports(run_static_checks(state), report.issues)
        report.recompute_score()
        return report
