from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_KANA_HANGUL_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uac00-\ud7af]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)?")


def foreign_language_fragments(text: str) -> list[str]:
    """Return obvious target-language passages inside a Chinese structure draft.

    Short acronyms and a single original-language proper noun remain allowed.
    Whole foreign-language labels or dialogue lines do not.
    """

    fragments: list[str] = []
    script_chars = _KANA_HANGUL_RE.findall(text)
    outside_parentheses = re.sub(r"[（(][^）)]*[）)]", "", text)
    unannotated_script = _KANA_HANGUL_RE.search(outside_parentheses)
    if script_chars and (len(script_chars) > 12 or unannotated_script):
        match = unannotated_script or _KANA_HANGUL_RE.search(text)
        if match:
            start = max(0, match.start() - 24)
            fragments.append(text[start : match.start() + 72].strip())

    for line in text.splitlines() or [text]:
        words = _LATIN_WORD_RE.findall(line)
        latin_letters = sum(len(word.replace("-", "")) for word in words)
        cjk_chars = len(_CJK_RE.findall(line))
        if (
            len(words) >= 4
            and latin_letters >= 16
            and (cjk_chars == 0 or latin_letters > cjk_chars * 2)
        ):
            fragments.append(line.strip()[:120])

    return list(dict.fromkeys(fragment for fragment in fragments if fragment))
