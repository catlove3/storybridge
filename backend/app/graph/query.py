from __future__ import annotations

import heapq
from itertools import count

from app.graph.build import StoryGraph
from app.schemas import (
    AffectedScene,
    Commitment,
    CultureMechanism,
    ImpactKind,
    PropagationResult,
)


def _impact_kind_for_edge(relation: str) -> ImpactKind:
    if relation in ("references", "appears_in"):
        return ImpactKind.DIRECT_REFERENCE
    if relation == "motivates":
        return ImpactKind.MOTIVATION
    if relation in ("causes", "depends_on", "reveals"):
        return ImpactKind.CAUSAL
    if relation in ("sets_up", "pays_off"):
        return ImpactKind.PAYOFF
    return ImpactKind.STRUCTURAL


def _kinds_for_path(relations: list[str]) -> set[ImpactKind]:
    kinds: set[ImpactKind] = set()
    for relation in relations:
        if relation == "motivates":
            kinds.add(ImpactKind.MOTIVATION)
        elif relation in ("causes", "depends_on", "reveals"):
            kinds.add(ImpactKind.CAUSAL)
        elif relation in ("sets_up", "pays_off"):
            kinds.add(ImpactKind.PAYOFF)
    if len(relations) == 1 and relations[0] in ("references", "appears_in"):
        kinds.add(ImpactKind.DIRECT_REFERENCE)
    return kinds or {ImpactKind.STRUCTURAL}


def _natural_key(node_id: str):
    head = node_id.rstrip("0123456789")
    tail = node_id[len(head) :]
    return (head, int(tail) if tail else -1)


class PropagationEngine:
    def __init__(self, graph: StoryGraph, min_confidence: float = 0.0, max_depth: int = 6) -> None:
        self.graph = graph
        self.min_confidence = min_confidence
        self.max_depth = max_depth

    def find_affected_scenes(self, changed_node_id: str) -> PropagationResult:
        g = self.graph.graph
        if changed_node_id not in g:
            raise KeyError(f"unknown node id: {changed_node_id}")

        best_path: dict[str, list[str]] = {}
        best_evidence: dict[str, list[str]] = {}
        best_rank: dict[str, tuple[float, int]] = {}
        kinds_seen: dict[str, set[ImpactKind]] = {}

        sequence = count()
        queue: list[tuple[float, int, int, str, list[str], list[str], list[str]]] = []
        heapq.heappush(
            queue,
            (-1.0, 0, next(sequence), changed_node_id, [], [], []),
        )
        best_states: dict[tuple[str, frozenset[ImpactKind]], tuple[float, int]] = {
            (changed_node_id, frozenset()): (1.0, 0)
        }

        while queue:
            neg_conf, depth, _, node_id, path, relations, evidence_path = heapq.heappop(
                queue
            )
            conf = -neg_conf
            state_key = (node_id, frozenset(_kinds_for_path(relations)) if relations else frozenset())
            if best_states.get(state_key) != (conf, depth):
                continue
            if depth >= self.max_depth:
                continue
            for _, nxt, _, data in g.out_edges(node_id, keys=True, data=True):
                edge_conf = float(data.get("confidence", 1.0))
                new_conf = conf * edge_conf
                if new_conf < self.min_confidence:
                    continue
                new_path = [*path, nxt]
                new_relations = [*relations, data.get("relation", "structural")]
                new_depth = depth + 1
                fragment = f"{node_id} --{data.get('relation', '?')}--> {nxt}"
                edge_evidence = data.get("evidence") or ""
                if edge_evidence:
                    fragment += f' ("{edge_evidence}")'
                new_evidence = [*evidence_path, fragment]

                rank = (new_conf, -new_depth)
                if rank > best_rank.get(nxt, (-1.0, -self.max_depth - 1)):
                    best_rank[nxt] = rank
                    best_path[nxt] = new_path
                    best_evidence[nxt] = new_evidence
                kinds_seen.setdefault(nxt, set()).update(_kinds_for_path(new_relations))

                path_kinds = frozenset(_kinds_for_path(new_relations))
                next_state_key = (nxt, path_kinds)
                previous_state = best_states.get(next_state_key)
                if previous_state is None or rank > (previous_state[0], -previous_state[1]):
                    best_states[next_state_key] = (new_conf, new_depth)
                    heapq.heappush(
                        queue,
                        (
                            -new_conf,
                            new_depth,
                            next(sequence),
                            nxt,
                            new_path,
                            new_relations,
                            new_evidence,
                        ),
                    )

        affected: dict[str, AffectedScene] = {}
        related_commitments: set[str] = set()

        for node_id in best_path:
            kind = self.graph.state.node_kind(node_id)
            if node_id == changed_node_id or kind is None:
                continue
            if kind.value == "scene":
                affected[node_id] = AffectedScene(
                    scene_id=node_id,
                    impact_kinds=sorted(kinds_seen.get(node_id, set()), key=lambda k: k.value),
                    reason_path=[changed_node_id, *best_path[node_id]],
                    evidence="; ".join(best_evidence[node_id]),
                    path_confidence=best_rank[node_id][0],
                )
            elif kind.value == "commitment":
                related_commitments.add(node_id)

        ordered = sorted(affected.values(), key=lambda a: _natural_key(a.scene_id))
        mechanism = self._mechanism_name(changed_node_id)
        summary = (
            f"Changing '{changed_node_id}' ({mechanism}) affects "
            f"{len(ordered)} scene(s): {', '.join(a.scene_id for a in ordered)}"
            if ordered
            else f"No downstream scenes depend on '{changed_node_id}'."
        )
        return PropagationResult(
            changed_node_id=changed_node_id,
            affected_scenes=ordered,
            related_commitment_ids=sorted(related_commitments),
            summary=summary,
        )

    def _mechanism_name(self, node_id: str) -> str:
        node = self.graph.state.node(node_id)
        if isinstance(node, CultureMechanism):
            return node.name
        if isinstance(node, Commitment):
            return node.description[:40]
        return node_id


def build_engine(graph: StoryGraph) -> PropagationEngine:
    return PropagationEngine(graph)
