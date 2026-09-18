from __future__ import annotations

from app.prompts import (
    detect_frictions_system,
    detect_frictions_user,
    parse_story_system,
    parse_story_user,
    plan_adaptation_system,
    plan_adaptation_user,
    render_target_script_system,
    render_target_script_user,
    rewrite_scene_system,
    rewrite_scene_user,
    verify_consistency_system,
    verify_consistency_user,
)
from app.prompts.repair import REPAIR_PLAN_SYSTEM, repair_plan_user
from app.schemas import (
    AdaptationPlan,
    FrictionDetectionResult,
    RewrittenScene,
    StoryState,
    TargetScript,
    VerifyReport,
)
from app.schemas.repair import RepairPlan
from app.skills.base import SkillSpec

PARSE_STORY = SkillSpec(
    name="parse_story",
    schema=StoryState,
    system_prompt=parse_story_system(),
    user_prompt=parse_story_user,
    temperature=0.0,
)

DETECT_FRICTIONS = SkillSpec(
    name="detect_frictions",
    schema=FrictionDetectionResult,
    system_prompt=detect_frictions_system(),
    user_prompt=detect_frictions_user,
    temperature=0.0,
)

PLAN_ADAPTATION = SkillSpec(
    name="plan_adaptation",
    schema=AdaptationPlan,
    system_prompt=plan_adaptation_system(),
    user_prompt=plan_adaptation_user,
)

REWRITE_SCENE = SkillSpec(
    name="rewrite_scene",
    schema=RewrittenScene,
    system_prompt=rewrite_scene_system(),
    user_prompt=rewrite_scene_user,
)

PLAN_REPAIR = SkillSpec(
    name="plan_repair",
    schema=RepairPlan,
    system_prompt=REPAIR_PLAN_SYSTEM,
    user_prompt=repair_plan_user,
    temperature=0.0,
)

RENDER_TARGET_SCRIPT = SkillSpec(
    name="render_target_script",
    schema=TargetScript,
    system_prompt=render_target_script_system(),
    user_prompt=render_target_script_user,
    temperature=0.0,
)

VERIFY_CONSISTENCY = SkillSpec(
    name="verify_consistency",
    schema=VerifyReport,
    system_prompt=verify_consistency_system(),
    user_prompt=verify_consistency_user,
    temperature=0.0,
    frequency_penalty=0.3,
)

_REGISTRY: dict[str, SkillSpec] = {
    s.name: s
    for s in (
        PARSE_STORY,
        DETECT_FRICTIONS,
        PLAN_ADAPTATION,
        REWRITE_SCENE,
        PLAN_REPAIR,
        RENDER_TARGET_SCRIPT,
        VERIFY_CONSISTENCY,
    )
}


def get_skill(name: str) -> SkillSpec:
    return _REGISTRY[name]


def all_skills() -> list[SkillSpec]:
    return list(_REGISTRY.values())
