from __future__ import annotations

import pytest

from app.llm import MockLLMClient
from app.schemas import StoryState, TargetScript, VerifyReport
from app.skills import all_skills, get_skill
from tests.fixtures import sample_story_state_dict

SKILL_NAMES = [
    "parse_story",
    "detect_frictions",
    "plan_adaptation",
    "rewrite_scene",
    "render_target_script",
    "verify_consistency",
]


def test_registry_contains_all_skills():
    assert [s.name for s in all_skills()] == SKILL_NAMES


def test_get_skill_unknown_raises():
    with pytest.raises(KeyError):
        get_skill("nope")


def test_skill_schemas_bound():
    assert get_skill("parse_story").schema is StoryState
    assert get_skill("verify_consistency").schema is VerifyReport
    assert get_skill("render_target_script").schema is TargetScript
    assert get_skill("parse_story").max_tokens == 8192


async def test_skill_run_uses_step_name_for_routing(tmp_path):
    client = MockLLMClient(responses={"parse_story": sample_story_state_dict()})
    skill = get_skill("parse_story")
    state = await skill.run(client, script_text="剧本", target_market="US")
    assert len(state.scenes) == 8
    assert client.calls["parse_story"]


async def test_skill_run_retries_on_invalid():

    client = MockLLMClient(responses={"parse_story": ["not json", sample_story_state_dict()]})
    skill = get_skill("parse_story")
    state = await skill.run(client, script_text="x", target_market="")
    assert state.scenes


def test_skill_step_routes_covered_by_config():
    from app.config import get_config

    routes = get_config().llm.step_routes
    for skill in all_skills():
        assert skill.name in routes or get_config().llm.default_profile
