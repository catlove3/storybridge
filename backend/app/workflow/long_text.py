from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import blake2b

from app.schemas import (
    Character,
    Commitment,
    CultureMechanism,
    Dependency,
    Event,
    Scene,
    Setting,
    StoryState,
)

CHUNKER_VERSION = "scene-boundary-v1"

_HEADING_RE = re.compile(
    r"(?im)^(?:"
    r"#{1,6}\s+\S.*|"
    r"第[零〇一二三四五六七八九十百千万两\d]+(?:集|章|幕|场)(?:\s|[:：.-]).*|"
    r"(?:场景|scene)\s*[零〇一二三四五六七八九十百千万两\d]*\s*[:：.-]?.*|"
    r"【(?:S\d+|场景\s*[零〇一二三四五六七八九十百千万两\d]*)[^】]*】|"
    r"(?:INT|EXT|内景|外景)[.．\s/-]+\S.*"
    r")$"
)
_NORMALIZE_RE = re.compile(r"[^\w\u3400-\u9fff]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ScriptChunk:
    index: int
    start: int
    end: int
    text: str
    fingerprint: str


def content_fingerprint(text: str, *, context: str = "") -> str:
    payload = f"{CHUNKER_VERSION}\0{context}\0{text}".encode("utf-8")
    return blake2b(payload, digest_size=20).hexdigest()


def _split_oversized(start: int, text: str, max_chars: int) -> list[tuple[int, str]]:
    pieces: list[tuple[int, str]] = []
    cursor = 0
    while len(text) - cursor > max_chars:
        hard_end = cursor + max_chars
        minimum = cursor + max(max_chars // 2, 1)
        boundary = text.rfind("\n\n", minimum, hard_end + 1)
        if boundary < minimum:
            boundary = text.rfind("\n", minimum, hard_end + 1)
        if boundary < minimum:
            boundary = hard_end
        else:
            boundary += 2 if text[boundary : boundary + 2] == "\n\n" else 1
        pieces.append((start + cursor, text[cursor:boundary]))
        cursor = boundary
    if cursor < len(text):
        pieces.append((start + cursor, text[cursor:]))
    return pieces


def split_script(script_text: str, *, max_chars: int = 16_000) -> list[ScriptChunk]:
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    if not script_text:
        return []

    boundaries = sorted({0, *(match.start() for match in _HEADING_RE.finditer(script_text))})
    units: list[tuple[int, str]] = []
    for position, start in enumerate(boundaries):
        end = boundaries[position + 1] if position + 1 < len(boundaries) else len(script_text)
        unit = script_text[start:end]
        if unit:
            units.extend(_split_oversized(start, unit, max_chars))

    combined: list[tuple[int, str]] = []
    current_start = 0
    current_text = ""
    for start, unit in units:
        if current_text and len(current_text) + len(unit) > max_chars:
            combined.append((current_start, current_text))
            current_text = ""
        if not current_text:
            current_start = start
        current_text += unit
    if current_text:
        combined.append((current_start, current_text))

    chunks = [
        ScriptChunk(
            index=index,
            start=start,
            end=start + len(text),
            text=text,
            fingerprint=content_fingerprint(text, context=str(index)),
        )
        for index, (start, text) in enumerate(combined)
    ]
    if "".join(chunk.text for chunk in chunks) != script_text:
        raise AssertionError("chunker must preserve the source text byte-for-byte")
    return chunks


def _normalized(value: str) -> str:
    return _NORMALIZE_RE.sub("", value.casefold())


def _unique(existing: list[str], incoming: list[str]) -> list[str]:
    return list(dict.fromkeys([*existing, *incoming]))


def _commitment_similarity(left: str, right: str) -> float:
    left_norm = _normalized(left)
    right_norm = _normalized(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    matcher = SequenceMatcher(None, left_norm, right_norm)
    sequence = matcher.ratio()
    common_span = matcher.find_longest_match().size / min(len(left_norm), len(right_norm))
    left_pairs = {left_norm[index : index + 2] for index in range(len(left_norm) - 1)}
    right_pairs = {right_norm[index : index + 2] for index in range(len(right_norm) - 1)}
    overlap = (
        len(left_pairs & right_pairs) / len(left_pairs | right_pairs)
        if left_pairs and right_pairs
        else 0.0
    )
    return max(sequence, overlap, common_span)


def _scene_number(scene_id: str | None) -> int:
    if scene_id is None:
        return 10**12
    match = re.search(r"\d+", scene_id)
    return int(match.group()) if match else 10**12


def merge_story_chunks(states: list[StoryState]) -> StoryState:
    characters: list[Character] = []
    scenes: list[Scene] = []
    events: list[Event] = []
    settings: list[Setting] = []
    mechanisms: list[CultureMechanism] = []
    commitments: list[Commitment] = []
    dependencies: list[Dependency] = []

    character_keys: dict[str, Character] = {}
    setting_keys: dict[str, Setting] = {}
    mechanism_keys: dict[str, CultureMechanism] = {}

    for chunk in states:
        id_map: dict[str, str] = {}
        scene_map = {
            scene.id: f"S{len(scenes) + offset:02d}"
            for offset, scene in enumerate(chunk.scenes, start=1)
        }
        id_map.update(scene_map)

        for item in chunk.characters:
            key = _normalized(item.name) or f"chunk-character:{len(characters)}:{item.id}"
            found = character_keys.get(key)
            if found is None:
                found = item.model_copy(deep=True)
                found.id = f"C{len(characters) + 1:02d}"
                characters.append(found)
                character_keys[key] = found
            else:
                if len(item.description) > len(found.description):
                    found.description = item.description
                found.goals = _unique(found.goals, item.goals)
                if found.role in {"supporting", "minor"} and item.role in {
                    "protagonist",
                    "antagonist",
                }:
                    found.role = item.role
            id_map[item.id] = found.id

        for item in chunk.settings:
            key = _normalized(item.name) or f"chunk-setting:{len(settings)}:{item.id}"
            found = setting_keys.get(key)
            if found is None:
                found = item.model_copy(deep=True)
                found.id = f"SET{len(settings) + 1:02d}"
                settings.append(found)
                setting_keys[key] = found
            elif len(item.description) > len(found.description):
                found.description = item.description
            id_map[item.id] = found.id

        for item in chunk.culture_mechanisms:
            aliases = {
                normalized
                for value in [item.name, *item.surface_text]
                if (normalized := _normalized(value))
            }
            found = next(
                (
                    mechanism_keys[alias]
                    for alias in sorted(aliases)
                    if alias in mechanism_keys
                ),
                None,
            )
            if found is None:
                found = item.model_copy(deep=True)
                found.id = f"CM{len(mechanisms) + 1:02d}"
                found.scene_ids = [scene_map[value] for value in item.scene_ids if value in scene_map]
                mechanisms.append(found)
            else:
                if len(item.description) > len(found.description):
                    found.description = item.description
                found.surface_text = _unique(found.surface_text, item.surface_text)
                found.scene_ids = _unique(
                    found.scene_ids,
                    [scene_map[value] for value in item.scene_ids if value in scene_map],
                )
            for alias in aliases:
                mechanism_keys[alias] = found
            id_map[item.id] = found.id

        for item in chunk.events:
            found = item.model_copy(deep=True)
            found.id = f"E{len(events) + 1:02d}"
            found.scene_ids = [scene_map[value] for value in item.scene_ids if value in scene_map]
            events.append(found)
            id_map[item.id] = found.id

        for item in chunk.commitments:
            match = max(
                commitments,
                key=lambda existing: _commitment_similarity(
                    existing.description, item.description
                ),
                default=None,
            )
            score = (
                _commitment_similarity(match.description, item.description)
                if match is not None
                else 0.0
            )
            established = scene_map.get(item.established_at_scene_id or "")
            payoff = scene_map.get(item.payoff_scene_id or "")
            if match is None or score < 0.58:
                match = item.model_copy(deep=True)
                match.id = f"NC{len(commitments) + 1:02d}"
                match.established_at_scene_id = established
                match.payoff_scene_id = payoff
                commitments.append(match)
            else:
                candidates = [
                    value
                    for value in (
                        match.established_at_scene_id,
                        match.payoff_scene_id,
                        established,
                        payoff,
                    )
                    if value is not None
                ]
                if candidates:
                    ordered = sorted(set(candidates), key=_scene_number)
                    match.established_at_scene_id = ordered[0]
                    if len(ordered) > 1:
                        match.payoff_scene_id = ordered[-1]
                match.must_preserve = match.must_preserve or item.must_preserve
                if len(item.description) > len(match.description):
                    match.description = item.description
            id_map[item.id] = match.id

        for item in chunk.scenes:
            found = item.model_copy(deep=True)
            found.id = scene_map[item.id]
            found.character_ids = [id_map[value] for value in item.character_ids if value in id_map]
            found.event_ids = [id_map[value] for value in item.event_ids if value in id_map]
            scenes.append(found)

        for item in chunk.dependencies:
            source = id_map.get(item.source_id)
            target = id_map.get(item.target_id)
            if source is None or target is None:
                continue
            found = item.model_copy(deep=True)
            found.source_id = source
            found.target_id = target
            dependencies.append(found)

    return StoryState(
        characters=characters,
        scenes=scenes,
        events=events,
        settings=settings,
        culture_mechanisms=mechanisms,
        commitments=commitments,
        dependencies=dependencies,
    )
