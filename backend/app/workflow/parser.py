from __future__ import annotations

from app.llm import LLMClient
from app.schemas import StoryState
from app.skills import PARSE_STORY, SkillSpec
from app.workflow.long_text import content_fingerprint, merge_story_chunks, split_script


class StoryParser:
    def __init__(
        self,
        client: LLMClient,
        skill: SkillSpec = PARSE_STORY,
        *,
        chunk_threshold_chars: int = 24_000,
        chunk_chars: int = 16_000,
    ) -> None:
        self.client = client
        self.skill = skill
        self.chunk_threshold_chars = chunk_threshold_chars
        self.chunk_chars = chunk_chars

    @property
    def step_name(self) -> str:
        return self.skill.name

    async def parse(
        self,
        script_text: str,
        target_market: str = "",
        *,
        project_id: str | None = None,
        checkpoint_store=None,
    ) -> StoryState:
        if len(script_text) <= self.chunk_threshold_chars:
            return await self.skill.run(
                self.client,
                script_text=script_text,
                target_market=target_market,
                chunk_context="",
            )

        chunks = split_script(script_text, max_chars=self.chunk_chars)
        analysis_key = content_fingerprint(script_text, context=target_market)
        supports_checkpoints = checkpoint_store is not None and all(
            hasattr(checkpoint_store, method)
            for method in (
                "load_completed_analysis",
                "load_analysis_chunk",
                "save_analysis_chunk",
                "complete_analysis",
            )
        )
        if project_id and supports_checkpoints:
            completed = checkpoint_store.load_completed_analysis(project_id, analysis_key)
            if completed is not None:
                return completed

        parsed_chunks: list[StoryState] = []
        for chunk in chunks:
            cached = None
            if project_id and supports_checkpoints:
                cached = checkpoint_store.load_analysis_chunk(
                    project_id,
                    analysis_key,
                    chunk.index,
                    chunk.fingerprint,
                )
            if cached is None:
                context = (
                    f"这是长剧本的第 {chunk.index + 1}/{len(chunks)} 个分块。"
                    "只抽取本块中明确出现的实体、场景、事件、文化机制和叙事承诺；"
                    "ID 在本块内从 01 开始，后续由程序统一重编号。"
                    "若承诺的建立或回收发生在其他分块，未知的一端填 null，禁止猜测。"
                )
                cached = await self.skill.run(
                    self.client,
                    script_text=chunk.text,
                    target_market=target_market,
                    chunk_context=context,
                )
                if project_id and supports_checkpoints:
                    checkpoint_store.save_analysis_chunk(
                        project_id,
                        analysis_key,
                        chunk.index,
                        chunk.fingerprint,
                        len(chunks),
                        cached,
                    )
            parsed_chunks.append(cached)

        merged = merge_story_chunks(parsed_chunks)
        if project_id and supports_checkpoints:
            checkpoint_store.complete_analysis(project_id, analysis_key, merged)
        return merged
