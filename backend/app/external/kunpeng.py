from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("/tmp/opencode/drama-l10n")


def _load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA_ROOT / f"{name}.parquet")


def extract_culture_lexicon(df: pd.DataFrame, sample_size: int, seed: int) -> list[dict]:
    rows = df.sample(n=min(sample_size, len(df)), random_state=seed)
    items: list[dict] = []
    for _, row in rows.iterrows():
        query = str(row["query"])
        match = re.search(r"文本[:：](.+?)翻译[:：]", query, re.DOTALL)
        if not match:
            continue
        items.append(
            {
                "source_text": match.group(1).strip(),
                "reference_translation": str(row["answer"]).strip(),
            }
        )
    return items


def extract_long_script(df: pd.DataFrame, chapter_index: int) -> dict:
    row = df.iloc[chapter_index]
    entries = list(row["entries"])
    first = entries[0]
    content = first["content"] if isinstance(first, dict) else str(first)
    match = re.search(r"文本[:：](.+?)翻译[:：]?\s*$", content, re.DOTALL)
    body = match.group(1).strip() if match else content
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]

    scene_size = 15
    scenes: list[str] = []
    for i in range(0, len(lines), scene_size):
        header = f"【第{i // scene_size + 1:02d}幕】"
        scenes.append(header + "\n" + "\n".join(lines[i : i + scene_size]))

    return {
        "title": lines[0] if lines else f"chapter-{chapter_index}",
        "scene_count": len(scenes),
        "script": "\n\n".join(scenes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="kunpeng_bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lexicon", help="idiom 集 → 文化负载词外部验证集")
    p.add_argument("--sample", type=int, default=50)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/external/kunpeng_lexicon.json")

    p = sub.add_parser("chapter", help="doclevel 集 → 长剧本测试文件")
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--out", default="data/external/kunpeng_chapter.md")

    args = parser.parse_args()

    if args.cmd == "lexicon":
        df = _load("kunpeng-idiom-train")
        items = extract_culture_lexicon(df, args.sample, args.seed)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"lexicon: {len(items)} items -> {out}")
    else:
        df = _load("kunpeng-doclevel")
        chapter = extract_long_script(df, args.index)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(chapter["script"], encoding="utf-8")
        print(f"chapter: {chapter['title']} ({chapter['scene_count']} scenes) -> {out}")


if __name__ == "__main__":
    main()
