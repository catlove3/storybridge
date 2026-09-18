from __future__ import annotations

import re

from app.schemas import Commitment, CultureMechanism, Setting, StoryState

AdaptationTarget = CultureMechanism | Setting

_GENERIC_MODIFIERS = ("超自然", "核心", "故事", "世界观")
_GENERIC_SUFFIXES = ("系统", "机制", "规则", "设定", "背景")


def adaptation_target(state: StoryState, target_id: str) -> AdaptationTarget:
    target = next(
        (
            item
            for item in [*state.culture_mechanisms, *state.settings]
            if item.id == target_id
        ),
        None,
    )
    if target is None:
        raise KeyError(f"unknown adaptation target: {target_id}")
    return target


def linked_commitments(state: StoryState, target_id: str) -> list[Commitment]:
    neighbor_ids: set[str] = set()
    for dependency in state.dependencies:
        if dependency.source_id == target_id:
            neighbor_ids.add(dependency.target_id)
        elif dependency.target_id == target_id:
            neighbor_ids.add(dependency.source_id)
    return [item for item in state.commitments if item.id in neighbor_ids]


def setting_scene_ids(state: StoryState, setting: Setting) -> set[str]:
    scene_ids = set(setting.scene_ids)
    for commitment in linked_commitments(state, setting.id):
        scene_ids.update(
            scene_id
            for scene_id in (
                commitment.established_at_scene_id,
                commitment.payoff_scene_id,
            )
            if scene_id
        )

    # Older saved analyses predate Setting.scene_ids. Recover obvious mentions
    # from the setting name and the leading action in its rule description.
    compact_name = re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", setting.name)
    for modifier in _GENERIC_MODIFIERS:
        compact_name = compact_name.replace(modifier, "")
    keywords = {compact_name} if len(compact_name) >= 2 else set()
    for suffix in _GENERIC_SUFFIXES:
        if suffix in compact_name:
            stem = compact_name.replace(suffix, "")
            if len(stem) >= 2:
                keywords.add(stem)
            keywords.add(suffix)
    first_clause = re.split(r"[，。；：,.;:]", setting.description, maxsplit=1)[0]
    first_action = re.split(r"(?:之后|以后|后|时|会|将|由|是)", first_clause, maxsplit=1)[0]
    first_action = re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", first_action)
    if 2 <= len(first_action) <= 12:
        keywords.add(first_action)

    for scene in state.scenes:
        haystack = f"{scene.title}\n{scene.summary}\n{scene.text}"
        if any(keyword in haystack for keyword in keywords):
            scene_ids.add(scene.id)
    return scene_ids


def target_scene_ids(state: StoryState, target: AdaptationTarget) -> set[str]:
    if isinstance(target, Setting):
        return setting_scene_ids(state, target)
    return set(target.scene_ids)
