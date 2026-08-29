from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.llm.base import LLMRequest, LLMResponse
from app.llm.mock import MockLLMClient
from app.schemas import StoryState
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile
from app.workflow.friction import FrictionDetector
from app.workflow.long_text import merge_story_chunks, split_script
from app.workflow.parser import StoryParser


def test_real_corpus_is_split_stably_without_losing_text():
    corpus_path = (
        Path(__file__).resolve().parents[1] / "data" / "scripts" / "corpus_urban.md"
    )
    script = corpus_path.read_text(encoding="utf-8")

    first = split_script(script, max_chars=160)
    second = split_script(script, max_chars=160)

    assert len(first) >= 3
    assert "".join(chunk.text for chunk in first) == script
    assert [(chunk.start, chunk.end, chunk.fingerprint) for chunk in first] == [
        (chunk.start, chunk.end, chunk.fingerprint) for chunk in second
    ]
    assert all(len(chunk.text) <= 160 for chunk in first)
    assert [chunk.start for chunk in first] == sorted(chunk.start for chunk in first)


def test_merge_remaps_entities_and_links_cross_chunk_commitment():
    first = StoryState.model_validate(
        {
            "characters": [{"id": "C01", "name": "林夏", "role": "protagonist"}],
            "scenes": [
                {
                    "id": "S01",
                    "summary": "父亲许下承诺",
                    "text": "父亲承诺在婚礼前归还戒指。",
                    "character_ids": ["C01"],
                    "event_ids": ["E01"],
                }
            ],
            "events": [
                {"id": "E01", "description": "许诺归还戒指", "scene_ids": ["S01"]}
            ],
            "culture_mechanisms": [
                {
                    "id": "CM01",
                    "name": "彩礼",
                    "surface_text": ["彩礼"],
                    "scene_ids": ["S01"],
                }
            ],
            "commitments": [
                {
                    "id": "NC01",
                    "description": "父亲承诺在婚礼前归还戒指",
                    "established_at_scene_id": "S01",
                }
            ],
            "dependencies": [
                {
                    "source_id": "NC01",
                    "target_id": "E01",
                    "relation": "sets_up",
                }
            ],
        }
    )
    second = StoryState.model_validate(
        {
            "characters": [{"id": "C01", "name": "林夏", "goals": ["完成婚礼"]}],
            "scenes": [
                {
                    "id": "S01",
                    "summary": "承诺兑现",
                    "text": "婚礼前，父亲终于归还戒指。",
                    "character_ids": ["C01"],
                    "event_ids": ["E01"],
                }
            ],
            "events": [
                {"id": "E01", "description": "归还戒指", "scene_ids": ["S01"]}
            ],
            "culture_mechanisms": [
                {
                    "id": "CM01",
                    "name": "婚前礼金",
                    "surface_text": ["彩礼"],
                    "scene_ids": ["S01"],
                }
            ],
            "commitments": [
                {
                    "id": "NC01",
                    "description": "婚礼前归还戒指的承诺终于兑现",
                    "payoff_scene_id": "S01",
                }
            ],
            "dependencies": [
                {
                    "source_id": "NC01",
                    "target_id": "E01",
                    "relation": "pays_off",
                }
            ],
        }
    )

    merged = merge_story_chunks([first, second])

    assert [scene.id for scene in merged.scenes] == ["S01", "S02"]
    assert len(merged.characters) == 1
    assert merged.characters[0].goals == ["完成婚礼"]
    assert len(merged.culture_mechanisms) == 1
    assert merged.culture_mechanisms[0].scene_ids == ["S01", "S02"]
    assert len(merged.commitments) == 1
    assert merged.commitments[0].established_at_scene_id == "S01"
    assert merged.commitments[0].payoff_scene_id == "S02"
    assert {(edge.source_id, edge.target_id) for edge in merged.dependencies} == {
        ("NC01", "E01"),
        ("NC01", "E02"),
    }


class InterruptOnceClient:
    def __init__(self) -> None:
        self.calls = 0
        self.interrupted = False

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls == 2 and not self.interrupted:
            self.interrupted = True
            raise RuntimeError("simulated provider interruption")
        payload = {
            "characters": [{"id": "C01", "name": "贯穿人物"}],
            "scenes": [
                {
                    "id": "S01",
                    "summary": f"chunk call {self.calls}",
                    "text": "分块解析结果",
                    "character_ids": ["C01"],
                    "event_ids": [],
                }
            ],
            "events": [],
            "settings": [],
            "culture_mechanisms": [],
            "commitments": [],
            "dependencies": [],
        }
        return LLMResponse(
            text=json.dumps(payload, ensure_ascii=False),
            model="checkpoint-test",
            profile_name="test",
            step=request.step,
        )


async def test_chunk_checkpoint_resumes_after_interruption(tmp_path):
    script = "".join(
        f"第{index}场：测试\n" + (f"第{index}场内容。" * 90) + "\n"
        for index in range(1, 4)
    )
    store = SQLiteProjectStore(tmp_path / "storybridge.sqlite3", tmp_path / "artifacts")
    meta = store.create_project("long", script, MarketProfile())
    client = InterruptOnceClient()
    parser = StoryParser(client, chunk_threshold_chars=600, chunk_chars=700)
    expected_chunks = split_script(script, max_chars=700)

    with pytest.raises(RuntimeError, match="simulated provider interruption"):
        await parser.parse(
            script,
            project_id=meta.id,
            checkpoint_store=store,
        )

    merged = await parser.parse(
        script,
        project_id=meta.id,
        checkpoint_store=store,
    )
    calls_after_resume = client.calls
    cached = await parser.parse(
        script,
        project_id=meta.id,
        checkpoint_store=store,
    )

    assert len(merged.scenes) == len(expected_chunks)
    assert len(merged.characters) == 1
    assert cached.model_dump() == merged.model_dump()
    assert client.calls == calls_after_resume
    assert calls_after_resume == len(expected_chunks) + 1


async def test_friction_detection_batches_large_mechanism_sets():
    state = StoryState.model_validate(
        {
            "culture_mechanisms": [
                {"id": f"CM{index:02d}", "name": f"机制{index}"}
                for index in range(1, 46)
            ]
        }
    )

    def respond(request: LLMRequest) -> str:
        digest = request.user_prompt.rsplit("故事状态：\n", 1)[1]
        mechanism_ids = list(
            dict.fromkeys(re.findall(r'"id": "(CM\d+)"', digest))
        )
        return json.dumps(
            {
                "mechanisms": [
                    {
                        "id": mechanism_id,
                        "friction_level": "high",
                        "narrative_importance": "medium",
                        "functions": {},
                        "drop": False,
                    }
                    for mechanism_id in mechanism_ids
                ]
            }
        )

    client = MockLLMClient(handler=respond)
    result = await FrictionDetector(client, batch_size=20).apply(
        state, target_market="United States"
    )

    assert len(client.calls["detect_frictions"]) == 3
    assert len(result.culture_mechanisms) == 45
    assert all(item.friction_level.value == "high" for item in result.culture_mechanisms)
