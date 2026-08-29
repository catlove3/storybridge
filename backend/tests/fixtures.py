from __future__ import annotations

import json
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def sample_story_state_dict() -> dict:
    return {
        "target_market": "United States",
        "audience": "18-30",
        "format": "Vertical Drama",
        "genre": "Romance / Revenge",
        "characters": [
            {"id": "C01", "name": "林晓东", "role": "protagonist", "description": "男主，创业公司职员后成为创始人", "goals": ["娶苏婉", "证明自己"]},
            {"id": "C02", "name": "苏婉", "role": "protagonist", "description": "女主，事业单位职员"},
            {"id": "C03", "name": "苏父", "role": "antagonist", "description": "女方父亲，重视编制和保障"},
            {"id": "C04", "name": "赵子昂", "role": "antagonist", "description": "985毕业的情敌，大厂中层"},
        ],
        "scenes": [
            {"id": f"S0{i}", "summary": summary, "text": text, "character_ids": chars}
            for i, (summary, text, chars) in enumerate(
                [
                    ("相亲饭局，苏母质疑林晓东没有编制", "包间。苏母：没个稳定编制，这日子怎么过？", ["C01", "C02", "C03"]),
                    ("苏父单独谈话：没编制拿什么给未来", "苏父：你连编制都没有，拿什么给婉儿未来？", ["C01", "C03"]),
                    ("彩礼摊牌三十八万八，男主开始借钱", "苏父母提出彩礼三十八万八。", ["C01"]),
                    ("男主为筹钱放弃晋升机会，女主误会", "他推掉了核心岗位邀请：我要快钱。", ["C01", "C02"]),
                    ("分手：没有编制没有存款给不了安全感", "苏婉：没有编制、没有存款的人，给不了安全感。", ["C01", "C02"]),
                    ("三年后男主创业成功，女主被安排相亲", "相亲对象有编制有房。", ["C01", "C02"]),
                    ("同学会被985情敌当众羞辱", "赵子昂：晓东当年连个正经单位都进不去吧？", ["C01", "C02", "C04"]),
                    ("会议室身份反转，男主打脸情敌", "创始人：林晓东。", ["C01", "C02", "C04"]),
                ],
                start=1,
            )
        ],
        "events": [
            {"id": "E01", "description": "苏父以无编制为由反对婚事", "scene_ids": ["S02"]},
            {"id": "E02", "description": "女方提出高额彩礼", "scene_ids": ["S03"]},
            {"id": "E03", "description": "男主为筹彩礼放弃机会疯狂兼职", "scene_ids": ["S03", "S04"]},
            {"id": "E04", "description": "女主误解并提分手", "scene_ids": ["S05"]},
            {"id": "E05", "description": "三年后男主创业成功", "scene_ids": ["S06"]},
            {"id": "E06", "description": "同学会上被情敌羞辱学历与职业", "scene_ids": ["S07"]},
            {"id": "E07", "description": "身份反转，男主收购情敌客户公司", "scene_ids": ["S08"]},
        ],
        "settings": [
            {"id": "SET01", "name": "当代中国都市", "description": "当代一线城市背景，体制内文化浓厚"},
        ],
        "culture_mechanisms": [
            {
                "id": "CM01",
                "name": "编制",
                "description": "体制内终身职位的稳定保障，婚姻市场硬通货",
                "surface_text": ["稳定编制", "没有编制", "有编制有房"],
                "scene_ids": ["S01", "S02", "S05", "S06"],
                "friction_level": "high",
                "narrative_importance": "high",
            },
            {
                "id": "CM02",
                "name": "彩礼",
                "description": "婚姻中男方家庭向女方家庭支付的大额礼金",
                "surface_text": ["彩礼三十八万八"],
                "scene_ids": ["S03", "S04", "S05"],
                "friction_level": "high",
                "narrative_importance": "high",
            },
            {
                "id": "CM03",
                "name": "985",
                "description": "中国精英大学联盟标签，社会地位符号",
                "surface_text": ["考上985"],
                "scene_ids": ["S07"],
                "friction_level": "medium",
                "narrative_importance": "medium",
            },
        ],
        "commitments": [
            {
                "id": "NC01",
                "description": "女方家庭认为男主缺乏职业稳定性与社会地位",
                "established_at_scene_id": "S02",
                "payoff_scene_id": "S08",
                "must_preserve": True,
            },
            {
                "id": "NC02",
                "description": "结局必须通过男主事业成功完成身份反转并回收前期羞辱",
                "established_at_scene_id": "S01",
                "payoff_scene_id": "S08",
                "must_preserve": True,
            },
            {
                "id": "NC03",
                "description": "分手的直接原因是男方短期内无法满足经济保障要求",
                "established_at_scene_id": "S03",
                "payoff_scene_id": "S05",
                "must_preserve": True,
            },
        ],
        "dependencies": [
            {"source_id": "CM01", "target_id": "E01", "relation": "motivates", "evidence": "没个稳定编制，这日子怎么过", "confidence": 0.95},
            {"source_id": "S01", "target_id": "CM01", "relation": "references", "evidence": "稳定编制", "confidence": 0.9},
            {"source_id": "S02", "target_id": "CM01", "relation": "references", "evidence": "你连编制都没有", "confidence": 0.9},
            {"source_id": "S05", "target_id": "CM01", "relation": "references", "evidence": "没有编制的人给不了安全感", "confidence": 0.9},
            {"source_id": "S06", "target_id": "CM01", "relation": "references", "evidence": "相亲对象有编制有房", "confidence": 0.85},
            {"source_id": "CM02", "target_id": "E02", "relation": "causes", "evidence": "提出彩礼三十八万八", "confidence": 0.95},
            {"source_id": "E02", "target_id": "E03", "relation": "causes", "evidence": "为凑彩礼开始借钱兼职", "confidence": 0.9},
            {"source_id": "E03", "target_id": "E04", "relation": "causes", "evidence": "神秘行为导致误会加深", "confidence": 0.85},
            {"source_id": "E04", "target_id": "E05", "relation": "causes", "evidence": "分手后各自发展", "confidence": 0.8},
            {"source_id": "S03", "target_id": "CM02", "relation": "references", "evidence": "彩礼摊牌", "confidence": 0.9},
            {"source_id": "S04", "target_id": "CM02", "relation": "references", "evidence": "为筹钱放弃机会", "confidence": 0.85},
            {"source_id": "E01", "target_id": "S02", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E02", "target_id": "S03", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E03", "target_id": "S03", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E03", "target_id": "S04", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E04", "target_id": "S05", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E05", "target_id": "S06", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E06", "target_id": "S07", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "E07", "target_id": "S08", "relation": "appears_in", "evidence": "", "confidence": 1.0},
            {"source_id": "CM01", "target_id": "E07", "relation": "sets_up", "evidence": "无编制之辱由事业成功回收", "confidence": 0.75},
            {"source_id": "CM02", "target_id": "E07", "relation": "sets_up", "evidence": "彩礼压力在反转中兑现", "confidence": 0.7},
            {"source_id": "NC01", "target_id": "CM01", "relation": "depends_on", "evidence": "承诺内容即编制问题", "confidence": 0.9},
            {"source_id": "NC02", "target_id": "CM01", "relation": "depends_on", "evidence": "反转动机源自编制羞辱", "confidence": 0.85},
            {"source_id": "NC03", "target_id": "CM02", "relation": "depends_on", "evidence": "分手原因即彩礼压力", "confidence": 0.9},
            {"source_id": "CM03", "target_id": "E06", "relation": "causes", "evidence": "985身份支撑羞辱台词", "confidence": 0.85},
        ],
    }


def sample_state_json() -> str:
    return json.dumps(sample_story_state_dict(), ensure_ascii=False)


def sample_target_script_dict(prefix: str = "TARGET") -> dict:
    return {
        "source_language": "zh-CN",
        "target_language": "English",
        "target_locale": "en-US",
        "scenes": [
            {
                "id": f"S0{index}",
                "title": f"Scene {index}",
                "summary": f"{prefix} summary {index}",
                "text": f"[{prefix} S0{index}] target-language scene",
            }
            for index in range(1, 9)
        ],
    }


def demo_script_text() -> str:
    return (BACKEND_ROOT / "data" / "scripts" / "demo_v0.md").read_text(encoding="utf-8")
