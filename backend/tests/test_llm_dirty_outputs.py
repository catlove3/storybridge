from __future__ import annotations

import pytest

from app.llm import MockLLMClient
from app.llm.structured import StructuredGenerationError, extract_json_payload, generate_structured
from app.prompts import parse_story_system, parse_story_user
from app.schemas import AdaptationPlan, StoryState
from app.storage import MarketProfile, ProjectStore
from app.workflow.engine import StoryBridgeWorkflow
from tests.fixtures import sample_story_state_dict


def _wf(tmp_path, responses=None):
    from app.cli import _load_default_mock_fixtures

    client = MockLLMClient()
    _load_default_mock_fixtures(client)
    for step, payload in (responses or {}).items():
        client.set_response(step, payload)
    return StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client), client


async def test_llm_returns_garbage_not_json(tmp_path):
    wf, client = _wf(tmp_path, {"parse_story": "抱歉我不知道怎么输出"})
    meta = await wf.create_project("g", "script", MarketProfile())
    with pytest.raises(StructuredGenerationError):
        await wf.analyze(meta.id)
    assert wf.store.load_state(meta.id) is None


async def test_llm_returns_markdown_wrapped_json_with_prose(tmp_path):
    state_dict = sample_story_state_dict()
    import json

    client = MockLLMClient()
    client.set_response(
        "parse_story",
        "好的，以下是分析结果：\n```json\n"
        + json.dumps(state_dict, ensure_ascii=False)
        + "\n```\n希望对你有帮助！",
    )
    client.set_response("detect_frictions", {"mechanisms": []})
    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)
    meta = await wf.create_project("md", "script", MarketProfile())
    state = await wf.analyze(meta.id)
    assert len(state.scenes) == 8


async def test_llm_retry_recovers_from_invalid_then_valid(tmp_path):
    import json

    bad = {"characters": [{"id": "XX99", "name": "bad id prefix"}]}
    good = sample_story_state_dict()
    client = MockLLMClient()
    client.set_response("parse_story", [json.dumps(bad), json.dumps(good)])
    client.set_response("detect_frictions", {"mechanisms": []})
    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)
    meta = await wf.create_project("retry", "script", MarketProfile())
    state = await wf.analyze(meta.id)
    assert len(state.scenes) == 8
    assert len(client.calls["parse_story"]) == 2


async def test_llm_malformed_relations_dropped(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["dependencies"] = [
        {"source_id": "CM01", "target_id": "E01", "relation": "wtf_relation"},
        {"source_id": "CM01", "target_id": "E01", "relation": "motivates", "confidence": 5.0},
    ]
    wf, _ = _wf(tmp_path, {"parse_story": state_dict})
    meta = await wf.create_project("badrel", "script", MarketProfile())
    with pytest.raises(Exception):
        await wf.analyze(meta.id)


async def test_llm_unicode_and_case_weird_ids(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["characters"][0]["id"] = "c01"
    state_dict["scenes"][0]["id"] = "s1"
    wf, _ = _wf(tmp_path, {"parse_story": state_dict})
    meta = await wf.create_project("caseids", "script", MarketProfile())
    with pytest.raises(Exception):
        await wf.analyze(meta.id)


async def test_plan_option_label_lowercase(tmp_path):
    wf, _ = _wf(tmp_path)
    meta = await wf.create_project("lower", "script", MarketProfile())
    await wf.analyze(meta.id)
    result = await wf.apply_adaptation(meta.id, "CM01", "b")
    assert result.applied.chosen_option.option_label == "B"


async def test_plan_missing_option_label_b(tmp_path):
    plan = {
        "culture_mechanism_id": "CM01",
        "original_name": "编制",
        "options": [
            {
                "option_label": "A",
                "strategy": "preserve",
                "title": "t",
                "replacement_definition": "d",
                "rationale": "r",
            }
        ],
    }
    wf, _ = _wf(tmp_path, {"plan_adaptation": plan})
    meta = await wf.create_project("noB", "script", MarketProfile())
    await wf.analyze(meta.id)
    with pytest.raises(KeyError):
        await wf.apply_adaptation(meta.id, "CM01", "B")


async def test_rewritten_scene_returns_wrong_id(tmp_path):
    import json
    import re

    def wrong_id_handler(request) -> str:
        match = re.search(r'"id": "(S\d+)"', request.user_prompt)
        real_id = match.group(1) if match else "S01"
        return json.dumps(
            {"id": "S99", "summary": "x", "text": f"rewritten for {real_id}"}
        )

    client = MockLLMClient(handler=wrong_id_handler)
    from app.cli import _load_default_mock_fixtures

    _load_default_mock_fixtures(client)
    wf = StoryBridgeWorkflow(ProjectStore(tmp_path / "p"), client)
    meta = await wf.create_project("wrongid", "script", MarketProfile())
    await wf.analyze(meta.id)
    result = await wf.apply_adaptation(meta.id, "CM01", "B")
    state = wf.require_state(meta.id)
    s01 = state.scene_by_id("S01")
    assert "rewritten for S01" in s01.text or s01.text.startswith("[REWRITTEN") or s01.text


async def test_verify_issues_with_null_scene_ids(tmp_path):
    wf, client = _wf(tmp_path)
    meta = await wf.create_project("nullscene", "script", MarketProfile())
    await wf.analyze(meta.id)
    client.set_response(
        "verify_consistency",
        {
            "issues": [
                {
                    "issue_type": "fact_conflict",
                    "severity": "warning",
                    "scene_id": None,
                    "description": "全局性小问题",
                    "evidence": "",
                }
            ],
            "commitment_checks": [],
        },
    )
    report = await wf.verify(meta.id)
    assert len(report.issues) == 1
    assert report.issues[0].scene_id is None


async def test_duplicate_ids_in_llm_output(tmp_path):
    state_dict = sample_story_state_dict()
    state_dict["characters"].append(dict(state_dict["characters"][0]))
    state_dict["dependencies"].append(dict(state_dict["dependencies"][0]))
    wf, _ = _wf(tmp_path, {"parse_story": state_dict})
    meta = await wf.create_project("dupids", "script", MarketProfile())
    state = await wf.analyze(meta.id)
    ids = [c.id for c in state.characters]
    assert len(ids) == len(set(ids)) == 4
    edge_keys = {(d.source_id, d.target_id, d.relation) for d in state.dependencies}
    assert len(edge_keys) == len(state.dependencies)


def test_extract_json_nested_arrays_with_braces():
    text = 'x [{"a": [{"b": "}"}]}] y'
    payload = extract_json_payload(text)
    import json

    parsed = json.loads(payload)
    assert parsed[0]["a"][0]["b"] == "}"
