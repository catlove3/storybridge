from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas import StoryState, TargetScript


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


@dataclass
class AdaptationEvalCase:
    name: str
    mechanism_ids: list[str]
    note: str = ""


@dataclass
class SystemOutput:
    system_name: str
    output_script: str


@dataclass
class EvalMetrics:
    system_name: str
    stale_reference_count: int | None = None
    stale_details: list[str] = field(default_factory=list)
    affected_scene_recall: float | None = None
    changed_scene_ids: list[str] = field(default_factory=list)
    expected_scene_ids: list[str] = field(default_factory=list)
    collateral_scene_ids: list[str] = field(default_factory=list)
    commitment_preserved: int = 0
    commitment_total: int = 0
    commitment_details: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def collateral_count(self) -> int:
        return len(set(self.collateral_scene_ids))


def count_stale_references(original: StoryState, adapted_script: str) -> tuple[int, list[str]]:
    adapted_text = _normalize(adapted_script)
    count = 0
    details: list[str] = []
    for cm in original.culture_mechanisms:
        if not cm.adapted_to:
            continue
        probes: set[str] = set()
        for phrase in (cm.name, *cm.surface_text):
            probe = phrase.strip("的了着有没")
            if len(probe) < 2:
                probe = phrase
            if probe:
                probes.add(probe)
        for probe in sorted(probes):
            if probe in adapted_text:
                count += 1
                details.append(f"{cm.id}({cm.name}): 残留'{probe}'")
    return count, details


def count_forbidden_target_terms(
    adapted_script: str,
    forbidden_terms: dict[str, list[str]],
) -> tuple[int, list[str]]:
    adapted_text = adapted_script.casefold()
    count = 0
    details: list[str] = []
    for mechanism_id, terms in forbidden_terms.items():
        for term in sorted(set(terms)):
            if term and term.casefold() in adapted_text:
                count += 1
                details.append(f"{mechanism_id}: forbidden target-language term '{term}'")
    return count, details


def compute_scene_recall(
    expected_ids: list[str],
    output_state: StoryState,
    original_state: StoryState,
) -> tuple[float, list[str]]:
    changed: list[str] = []
    for out_scene in output_state.scenes:
        orig = next((s for s in original_state.scenes if s.id == out_scene.id), None)
        if orig is None:
            continue
        if _normalize(orig.text) != _normalize(out_scene.text):
            changed.append(out_scene.id)
    if not expected_ids:
        return 1.0, changed
    hit = sum(1 for sid in expected_ids if sid in changed)
    return round(hit / len(expected_ids), 3), changed


def compute_target_scene_recall(
    expected_ids: list[str],
    output_script: TargetScript,
    reference_script: TargetScript,
) -> tuple[float, list[str]]:
    reference_by_id = {scene.id: scene for scene in reference_script.scenes}
    changed = [
        scene.id
        for scene in output_script.scenes
        if scene.id in reference_by_id
        and _normalize(scene.text) != _normalize(reference_by_id[scene.id].text)
    ]
    if not expected_ids:
        return 1.0, changed
    hit = sum(scene_id in changed for scene_id in expected_ids)
    return round(hit / len(expected_ids), 3), changed


def evaluate_output(
    original_state: StoryState,
    adapted_state: StoryState | None,
    adapted_script: str,
    system_name: str,
    expected_affected_ids: list[str],
    commitment_checks: list[dict] | None = None,
    *,
    output_language: str = "",
    source_language: str = "",
    forbidden_terms: dict[str, list[str]] | None = None,
    target_output: TargetScript | None = None,
    target_reference: TargetScript | None = None,
) -> EvalMetrics:
    metrics = EvalMetrics(system_name=system_name)

    if forbidden_terms is not None:
        metrics.stale_reference_count, metrics.stale_details = count_forbidden_target_terms(
            adapted_script, forbidden_terms
        )
    elif output_language and source_language and output_language != source_language:
        metrics.notes.append(
            "target-language forbidden-term annotations missing; stale references are N/A"
        )
    else:
        metrics.stale_reference_count, metrics.stale_details = count_stale_references(
            original_state, adapted_script
        )
    metrics.expected_scene_ids = expected_affected_ids

    if target_output is not None and target_reference is not None:
        metrics.affected_scene_recall, metrics.changed_scene_ids = (
            compute_target_scene_recall(
                expected_affected_ids,
                target_output,
                target_reference,
            )
        )
        metrics.collateral_scene_ids = sorted(
            set(metrics.changed_scene_ids) - set(expected_affected_ids)
        )
    elif adapted_state is not None:
        metrics.affected_scene_recall, metrics.changed_scene_ids = compute_scene_recall(
            expected_affected_ids, adapted_state, original_state
        )
        metrics.collateral_scene_ids = sorted(
            set(metrics.changed_scene_ids) - set(expected_affected_ids)
        )
    else:
        metrics.notes.append("no structured state; scene recall not computable")

    if commitment_checks:
        metrics.commitment_total = len(commitment_checks)
        metrics.commitment_preserved = sum(
            1 for c in commitment_checks if c.get("status") == "preserved"
        )
        metrics.commitment_details = commitment_checks
    return metrics


def format_metrics_table(metrics_list: list[EvalMetrics]) -> str:
    header = (
        f"| {'系统':<22} | {'残留引用数':>10} | {'场景覆盖率':>10} | "
        f"{'无关场景改动':>12} | {'承诺保持':>10} |"
    )
    sep = "|" + "-" * 24 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 14 + "|" + "-" * 12 + "|"
    rows = []
    for m in metrics_list:
        recall = f"{m.affected_scene_recall:.0%}" if m.affected_scene_recall is not None else "N/A"
        commitment = (
            f"{m.commitment_preserved}/{m.commitment_total}"
            if m.commitment_total
            else "N/A"
        )
        stale = "N/A" if m.stale_reference_count is None else str(m.stale_reference_count)
        collateral = str(m.collateral_count) if m.affected_scene_recall is not None else "N/A"
        rows.append(
            f"| {m.system_name:<22} | {stale:>10} | {recall:>10} | {collateral:>12} | {commitment:>10} |"
        )
    return "\n".join([header, sep, *rows])
