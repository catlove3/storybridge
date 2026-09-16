from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import BACKEND_ROOT

CATALOG = BACKEND_ROOT / "config/demo_scripts.yaml"
SCRIPTS = BACKEND_ROOT / "data/scripts"


class DemoSummary(BaseModel):
    id: str
    title: str
    genre: str
    summary: str


class DemoDetail(DemoSummary):
    text: str


class Entry(DemoSummary):
    model_config = ConfigDict(strict=True)
    file: str
    enabled: bool = False
    order: int = 0


def catalog() -> list[Entry]:
    try:
        raw = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise HTTPException(
            503, {"code": "demo_unavailable", "message": "示例暂不可用，你仍可粘贴自己的故事。"}
        ) from None
    if not isinstance(raw, list):
        raise HTTPException(
            503, {"code": "demo_unavailable", "message": "示例目录暂不可用，请稍后重试。"}
        )
    entries: dict[str, Entry] = {}
    for item in raw:
        try:
            entry = Entry.model_validate(item)
            if not entry.enabled or entry.id in entries:
                continue
            script_path(entry)
            entries[entry.id] = entry
        except (ValidationError, ValueError, OSError):
            continue
    return sorted(entries.values(), key=lambda e: (e.order, e.id))


def script_path(entry: Entry) -> Path:
    path = (SCRIPTS / entry.file).resolve()
    if (
        Path(entry.file).is_absolute()
        or not path.is_relative_to(SCRIPTS.resolve())
        or path.suffix.lower() not in {".txt", ".md"}
    ):
        raise ValueError("invalid script path")
    return path


def detail(identifier: str) -> DemoDetail:
    entry = next((e for e in catalog() if e.id == identifier), None)
    if entry is None:
        raise HTTPException(
            404, {"code": "demo_not_found", "message": "这个示例已下架，请重新选择。"}
        )
    try:
        text = script_path(entry).read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("empty script")
    except (OSError, UnicodeError, ValueError):
        raise HTTPException(
            503, {"code": "demo_unavailable", "message": "示例读取失败，原文已保留。"}
        ) from None
    return DemoDetail(**entry.model_dump(exclude={"file", "enabled", "order"}), text=text)
