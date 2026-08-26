from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    CHARACTER = "character"
    SCENE = "scene"
    EVENT = "event"
    SETTING = "setting"
    CULTURE_MECHANISM = "culture_mechanism"
    COMMITMENT = "commitment"


class EdgeRelation(str, Enum):
    APPEARS_IN = "appears_in"
    MOTIVATES = "motivates"
    CAUSES = "causes"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    REVEALS = "reveals"
    CONFLICTS_WITH = "conflicts_with"
    SETS_UP = "sets_up"
    PAYS_OFF = "pays_off"


class Level(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PlotFunction(str, Enum):
    MOTIVATION = "motivation"
    CONSTRAINT = "constraint"
    CONFLICT = "conflict"
    REVELATION = "revelation"
    FORESHADOWING = "foreshadowing"
    PAYOFF = "payoff"
    REVERSAL = "reversal"


class SocialFunction(str, Enum):
    STATUS = "status"
    POWER = "power"
    OBLIGATION = "obligation"
    KINSHIP = "kinship"
    REPUTATION = "reputation"
    INSTITUTIONAL_ACCESS = "institutional_access"
    ECONOMIC_SECURITY = "economic_security"


class EmotionalFunction(str, Enum):
    HUMILIATION = "humiliation"
    ASPIRATION = "aspiration"
    FEAR = "fear"
    SYMPATHY = "sympathy"
    SUSPENSE = "suspense"
    SATISFACTION = "satisfaction"


EDGE_RELATIONS_REQUIRING_RECHECK = {
    EdgeRelation.REFERENCES,
    EdgeRelation.DEPENDS_ON,
    EdgeRelation.MOTIVATES,
    EdgeRelation.CAUSES,
    EdgeRelation.SETS_UP,
    EdgeRelation.PAYS_OFF,
}
