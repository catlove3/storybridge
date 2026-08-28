from __future__ import annotations

import networkx as nx

from app.schemas import EdgeRelation, StoryState

IMPACT_FORWARD_RELATIONS = {
    EdgeRelation.MOTIVATES,
    EdgeRelation.CAUSES,
    EdgeRelation.SETS_UP,
    EdgeRelation.APPEARS_IN,
}

IMPACT_BACKWARD_RELATIONS = {
    EdgeRelation.DEPENDS_ON,
    EdgeRelation.REFERENCES,
    EdgeRelation.REVEALS,
    EdgeRelation.PAYS_OFF,
}

IMPACT_SYMMETRIC_RELATIONS = {
    EdgeRelation.CONFLICTS_WITH,
}


def _impact_edges(dep_relation: EdgeRelation, source_id: str, target_id: str) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    if dep_relation in IMPACT_FORWARD_RELATIONS:
        edges.append((source_id, target_id))
    if dep_relation in IMPACT_BACKWARD_RELATIONS:
        edges.append((target_id, source_id))
    if dep_relation in IMPACT_SYMMETRIC_RELATIONS:
        edges.append((source_id, target_id))
        edges.append((target_id, source_id))
    return edges


class StoryGraph:
    def __init__(self, state: StoryState) -> None:
        self.state = state
        self.graph = nx.MultiDiGraph()
        self._build()

    def _build(self) -> None:
        collections = self.state.node_collections()
        for kind, members in collections.items():
            for node_id in members:
                self.graph.add_node(node_id, kind=kind)

        for dep in self.state.dependencies:
            dependency_key = f"{dep.source_id}->{dep.target_id}:{dep.relation.value}"
            impact_edges = dict.fromkeys(
                _impact_edges(dep.relation, dep.source_id, dep.target_id)
            )
            for direction_index, (src, dst) in enumerate(impact_edges):
                self.graph.add_edge(
                    src,
                    dst,
                    key=f"{dependency_key}:{direction_index}",
                    relation=dep.relation.value,
                    evidence=dep.evidence,
                    confidence=dep.confidence,
                    dependency_key=dependency_key,
                )

    def has_node(self, node_id: str) -> bool:
        return node_id in self.graph

    def display_subgraph(
        self, focus_ids: list[str] | None = None, depth: int = 2
    ) -> nx.MultiDiGraph:
        if not focus_ids:
            return self.graph.copy()
        nodes: set[str] = set()
        for focus in focus_ids:
            if focus in self.graph:
                nodes |= nx.single_source_shortest_path_length(
                    self.graph.to_undirected(as_view=True), focus, cutoff=depth
                ).keys()
        return self.graph.subgraph(nodes).copy()
