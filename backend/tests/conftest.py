from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.llm import MockLLMClient
from tests.fixtures import sample_story_state_dict  # noqa: E402


@pytest.fixture
def state_dict() -> dict:
    return sample_story_state_dict()


def _rewrite_handler(request) -> str:
    match = re.search(r'"id": "(S\d+)"', request.user_prompt)
    scene_id = match.group(1)
    return json.dumps(
        {
            "id": scene_id,
            "title": f"{scene_id} adapted",
            "summary": f"[REWRITTEN-SUMMARY {scene_id}]",
            "text": f"[REWRITTEN {scene_id}] career-stability conflict resolved",
        },
        ensure_ascii=False,
    )


@pytest.fixture
def mock_client() -> MockLLMClient:
    client = MockLLMClient(handler=_rewrite_handler)
    client.set_response("parse_story", sample_story_state_dict())
    client.set_response(
        "detect_frictions",
        {
            "mechanisms": [
                {
                    "id": "CM01",
                    "friction_level": "high",
                    "narrative_importance": "high",
                    "functions": {
                        "plot": ["conflict", "foreshadowing"],
                        "social": ["status", "economic_security"],
                        "emotional": ["humiliation"],
                    },
                },
                {
                    "id": "CM02",
                    "friction_level": "high",
                    "narrative_importance": "high",
                    "functions": {"plot": ["conflict"], "social": ["obligation"]},
                },
                {
                    "id": "CM03",
                    "friction_level": "medium",
                    "narrative_importance": "medium",
                    "functions": {"social": ["status"]},
                },
            ]
        },
    )
    client.set_response(
        "plan_adaptation",
        {
            "culture_mechanism_id": "CM01",
            "original_name": "编制",
            "friction_level": "high",
            "options": [
                {
                    "option_label": "A",
                    "strategy": "preserve",
                    "title": "保留并加注",
                    "replacement_definition": "保留'体制内职位'概念并加脚注",
                    "rationale": "最小改动",
                    "preserved_functions": ["status"],
                    "lost_functions": [],
                    "risks": ["观众理解成本高"],
                },
                {
                    "option_label": "B",
                    "strategy": "functional_replacement",
                    "replacement_definition": (
                        "男主在一家没有前景的传统公司做底层职员，"
                        "女方家庭要求他在有养老金和晋升通道的大机构工作"
                    ),
                    "title": "职业稳定性机制等效替换",
                    "rationale": "保留社会地位与经济安全功能",
                    "preserved_functions": ["status", "economic_security", "humiliation"],
                    "lost_functions": [],
                    "risks": ["需同步修改多处台词"],
                },
                {
                    "option_label": "C",
                    "strategy": "plot_reconstruction",
                    "replacement_definition": "重构为男主背负家庭债务被女方家庭否定",
                    "title": "冲突机制重构",
                    "rationale": "彻底本土化但改动大",
                    "preserved_functions": ["conflict"],
                    "lost_functions": ["institutional_access"],
                    "risks": ["后续剧情需要连锁调整"],
                },
            ],
        },
    )
    client.set_response(
        "verify_consistency",
        [
            {
                "issues": [
                    {
                        "issue_type": "fact_conflict",
                        "severity": "error",
                        "scene_id": "S05",
                        "description": "S05 仍引用旧设定'编制'，与改编决定冲突",
                        "evidence": "没有编制、没有存款的人，给不了安全感。",
                    }
                ],
                "commitment_checks": [
                    {"commitment_id": "NC01", "status": "preserved", "explanation": ""},
                    {"commitment_id": "NC02", "status": "preserved", "explanation": ""},
                    {"commitment_id": "NC03", "status": "needs_review", "explanation": "彩礼线未动"},
                ],
            },
            {
                "issues": [],
                "commitment_checks": [
                    {"commitment_id": "NC01", "status": "preserved", "explanation": ""},
                    {"commitment_id": "NC02", "status": "preserved", "explanation": ""},
                    {"commitment_id": "NC03", "status": "preserved", "explanation": ""},
                ],
            },
        ],
    )
    return client
