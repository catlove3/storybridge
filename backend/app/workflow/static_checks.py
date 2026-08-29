from __future__ import annotations

import re

from app.schemas import StoryState, VerificationIssue
from app.schemas.verification import IssueType, Severity


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _variants(phrase: str) -> list[str]:
    variants = {phrase}
    stripped = phrase.strip("的了着有没")
    if stripped and len(stripped) >= 2:
        variants.add(stripped)
    return [v for v in variants if len(v) >= 2]


def check_stale_references(state: StoryState) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []

    for cm in state.culture_mechanisms:
        if not cm.adapted_to or cm.adapted_strategy == "preserve":
            continue
        probe = cm.name.strip("的了着有没")
        if len(probe) < 2:
            continue
        for scene in state.scenes:
            text = _normalize(scene.text) + _normalize(scene.summary)
            if probe in text:
                issues.append(
                    VerificationIssue(
                        issue_type=IssueType.STALE_REFERENCE,
                        severity=Severity.ERROR,
                        scene_id=scene.id,
                        description=f"场景仍残留已替换机制'{cm.name}'的表述：{probe}",
                        evidence=probe,
                    )
                )
    return issues


def check_uncovered_commitments(state: StoryState) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    scene_ids = {s.id for s in state.scenes}
    for nc in state.commitments:
        if not nc.must_preserve:
            continue
        if nc.payoff_scene_id and nc.payoff_scene_id not in scene_ids:
            issues.append(
                VerificationIssue(
                    issue_type=IssueType.UNRESOLVED_PAYOFF,
                    severity=Severity.ERROR,
                    scene_id=None,
                    description=f"承诺 {nc.id} 的回收场景 {nc.payoff_scene_id} 已不存在",
                    evidence=nc.description,
                )
            )
    return issues


def check_reconstructed_dependency_chains(state: StoryState) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    causal_relations = {"motivates", "causes", "depends_on", "sets_up", "pays_off"}
    for mechanism in state.culture_mechanisms:
        if mechanism.adapted_strategy != "plot_reconstruction":
            continue
        old_chain_edges = [
            dependency
            for dependency in state.dependencies
            if mechanism.id in (dependency.source_id, dependency.target_id)
            and dependency.relation.value in causal_relations
        ]
        if old_chain_edges:
            evidence = ", ".join(
                f"{edge.source_id}--{edge.relation.value}-->{edge.target_id}"
                for edge in old_chain_edges[:5]
            )
            issues.append(
                VerificationIssue(
                    issue_type=IssueType.MOTIVATION_BREAK,
                    severity=Severity.WARNING,
                    scene_id=None,
                    description=(
                        f"重构策略仍保留 {mechanism.id} 的旧因果依赖边，"
                        "需要人工确认因果链是否已同步重建"
                    ),
                    evidence=evidence,
                )
            )
    return issues


def run_static_checks(state: StoryState) -> list[VerificationIssue]:
    return [
        *check_stale_references(state),
        *check_uncovered_commitments(state),
        *check_reconstructed_dependency_chains(state),
    ]


def merge_reports(
    static_issues: list[VerificationIssue],
    llm_issues: list[VerificationIssue],
) -> list[VerificationIssue]:
    seen: set[tuple[str, str | None]] = set()
    merged: list[VerificationIssue] = []
    for issue in [*static_issues, *llm_issues]:
        key = (
            (issue.issue_type.value, issue.scene_id)
            if issue.issue_type == IssueType.STALE_REFERENCE and issue.scene_id
            else (issue.issue_type.value, issue.scene_id, issue.evidence[:30])
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(issue)
    return merged
