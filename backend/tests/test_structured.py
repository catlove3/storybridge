from __future__ import annotations

import pytest

from app.llm.structured import extract_json_payload


def test_plain_json():
    assert extract_json_payload('{"a": 1}') == '{"a": 1}'


def test_fenced_json():
    text = "好的，结果如下：\n```json\n{\"a\": [1, 2]}\n```\n以上。"
    assert extract_json_payload(text) == '{"a": [1, 2]}'
    assert extract_json_payload(text) == '{"a": [1, 2]}'


def test_json_with_braces_in_strings():
    text = 'prefix {"a": "包含 } 花括号", "b": {"c": "\\"quoted\\""}} suffix'
    payload = extract_json_payload(text)
    import json

    assert json.loads(payload)["b"]["c"] == '"quoted"'


def test_no_json_returns_none():
    assert extract_json_payload("抱歉我无法输出 JSON") is None
