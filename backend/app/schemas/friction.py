from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Level
from .story_state import FunctionTags


class MechanismFriction(BaseModel):
    id: str
    friction_level: Level = Level.MEDIUM
    narrative_importance: Level = Level.MEDIUM
    functions: FunctionTags = Field(default_factory=FunctionTags)


class FrictionDetectionResult(BaseModel):
    mechanisms: list[MechanismFriction] = Field(default_factory=list)
