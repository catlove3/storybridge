from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .common import (
    EdgeRelation,
    EmotionalFunction,
    Level,
    NodeKind,
    PlotFunction,
    SocialFunction,
)

ID_PATTERN_DESCRIPTION = "id must start with the node kind prefix, e.g. C01/S01/E01/SET01/CM01/NC01"


class FunctionTags(BaseModel):
    plot: list[PlotFunction] = Field(default_factory=list)
    social: list[SocialFunction] = Field(default_factory=list)
    emotional: list[EmotionalFunction] = Field(default_factory=list)


class Character(BaseModel):
    id: str = Field(pattern=r"^C\d+$", description=ID_PATTERN_DESCRIPTION)
    name: str
    role: Literal["protagonist", "antagonist", "supporting", "minor"] = "supporting"
    description: str = ""
    goals: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    id: str = Field(pattern=r"^S\d+$", description=ID_PATTERN_DESCRIPTION)
    title: str = ""
    summary: str
    text: str
    character_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)


class Event(BaseModel):
    id: str = Field(pattern=r"^E\d+$", description=ID_PATTERN_DESCRIPTION)
    description: str
    scene_ids: list[str] = Field(default_factory=list)


class Setting(BaseModel):
    id: str = Field(pattern=r"^SET\d+$", description=ID_PATTERN_DESCRIPTION)
    name: str
    description: str


class CultureMechanism(BaseModel):
    id: str = Field(pattern=r"^CM\d+$", description=ID_PATTERN_DESCRIPTION)
    name: str
    description: str = ""
    surface_text: list[str] = Field(
        default_factory=list,
        description="verbatim phrases from the script that reference this mechanism",
    )
    scene_ids: list[str] = Field(default_factory=list)
    friction_level: Level = Level.MEDIUM
    narrative_importance: Level = Level.MEDIUM
    functions: FunctionTags = Field(default_factory=FunctionTags)
    adapted_to: str | None = Field(
        default=None,
        description="replacement definition after an adaptation has been applied",
    )
    adapted_strategy: str | None = None


class Commitment(BaseModel):
    id: str = Field(pattern=r"^NC\d+$", description=ID_PATTERN_DESCRIPTION)
    description: str
    established_at_scene_id: str | None = None
    payoff_scene_id: str | None = None
    must_preserve: bool = True


class Dependency(BaseModel):
    source_id: str
    target_id: str
    relation: EdgeRelation
    evidence: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class StoryState(BaseModel):
    target_market: str = ""
    audience: str = ""
    format: str = ""
    genre: str = ""

    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    settings: list[Setting] = Field(default_factory=list)
    culture_mechanisms: list[CultureMechanism] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dedupe_and_reindex(self) -> StoryState:
        seen_nodes: set[str] = set()
        for attr in (
            "characters",
            "scenes",
            "events",
            "settings",
            "culture_mechanisms",
            "commitments",
        ):
            items = getattr(self, attr)
            unique: list = []
            for item in items:
                if item.id not in seen_nodes:
                    seen_nodes.add(item.id)
                    unique.append(item)
            setattr(self, attr, unique)

        seen_edges: set[tuple[str, str, str]] = set()
        unique_deps: list[Dependency] = []
        for dep in self.dependencies:
            key = (dep.source_id, dep.target_id, dep.relation.value)
            if key not in seen_edges:
                seen_edges.add(key)
                unique_deps.append(dep)
        self.dependencies = unique_deps
        return self

    def node(self, node_id: str) -> BaseModel | None:
        for collection in self.node_collections().values():
            if node_id in collection:
                return collection[node_id]
        return None

    def node_kind(self, node_id: str) -> NodeKind | None:
        prefix_map = {
            "C": NodeKind.CHARACTER,
            "S": NodeKind.SCENE,
            "E": NodeKind.EVENT,
            "SET": NodeKind.SETTING,
            "CM": NodeKind.CULTURE_MECHANISM,
            "NC": NodeKind.COMMITMENT,
        }
        for prefix in sorted(prefix_map, key=len, reverse=True):
            if node_id.startswith(prefix):
                return prefix_map[prefix]
        return None

    def node_collections(
        self,
    ) -> dict[str, dict[str, BaseModel]]:
        return {
            "characters": {c.id: c for c in self.characters},
            "scenes": {s.id: s for s in self.scenes},
            "events": {e.id: e for e in self.events},
            "settings": {st.id: st for st in self.settings},
            "culture_mechanisms": {cm.id: cm for cm in self.culture_mechanisms},
            "commitments": {nc.id: nc for nc in self.commitments},
        }

    def scene_by_id(self, scene_id: str) -> Scene | None:
        return next((s for s in self.scenes if s.id == scene_id), None)


class Revision(BaseModel):
    revision_id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: Literal[
        "initial_parse",
        "friction_detection",
        "adaptation_applied",
        "repair",
    ]
    description: str = ""
    changed_scene_ids: list[str] = Field(default_factory=list)
    applied_option: dict | None = None
