from __future__ import annotations

from collections import deque

import networkx as nx

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

        visited: set[str] = set()
        best_path: dict[str, list[str]] = {}
        best_relations: dict[str, list[str]] = {}
        kinds_seen: dict[str, set[ImpactKind]] = {}

        queue: deque[tuple[str, list[str], list[str], float]] = deque()
        queue.append((changed_node_id, [], [], 1.0))

        while queue:
            node_id, path, relations, conf = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            if len(path) >= self.max_depth:
                continue
            for _, nxt, data in g.out_edges(node_id, data=True):
                edge_conf = float(data.get("confidence", 1.0))
                new_conf = conf * edge_conf
                if new_conf < self.min_confidence:
                    continue
                new_path = [*path, nxt]
                new_relations = [*relations, data.get("relation", "structural")]
                if nxt not in best_path:
                    best_path[nxt] = new_path
                    best_relations[nxt] = new_relations
                kinds_seen.setdefault(nxt, set()).update(_kinds_for_path(new_relations))
                if nxt not in visited:
                    queue.append((nxt, new_path, new_relations, new_conf))

        affected: dict[str, AffectedScene] = {}
        related_commitments: set[str] = set()

        for node_id, relations in best_relations.items():
            kind = self.graph.state.node_kind(node_id)
            if node_id == changed_node_id or kind is None:
                continue
            if kind.value == "scene":
                affected[node_id] = AffectedScene(
                    scene_id=node_id,
                    impact_kinds=sorted(kinds_seen.get(node_id, set()), key=lambda k: k.value),
                    reason_path=[changed_node_id, *best_path[node_id]],
                    evidence=self._evidence(changed_node_id, best_path[node_id]),
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

    def _evidence(self, changed_node_id: str, path: list[str]) -> str:
        fragments: list[str] = []
        prev = changed_node_id
        for node_id in path:
            data = self.graph.graph.get_edge_data(prev, node_id) or {}
            relation = data.get("relation", "?")
            evidence = data.get("evidence") or ""
            fragment = f"{prev} --{relation}--> {node_id}"
            if evidence:
                fragment += f' ("{evidence}")'
            fragments.append(fragment)
            prev = node_id
        return "; ".join(fragments)

    def _mechanism_name(self, node_id: str) -> str:
        node = self.graph.state.node(node_id)
        if isinstance(node, CultureMechanism):
            return node.name
        if isinstance(node, Commitment):
            return node.description[:40]
        return node_id


def build_engine(graph: StoryGraph) -> PropagationEngine:
    return PropagationEngine(graph)
