from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart

from .knowledge_core import KnowledgeIndex, load_knowledge, render_context


@register(
    "ff14_novice_knowledge",
    "keita",
    "Answers FF14 beginner and duty questions with a local knowledge index.",
    "1.3.0",
)
class FF14NoviceKnowledge(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        knowledge = load_knowledge(Path(__file__).with_name("knowledge.json"))
        self.index = KnowledgeIndex(knowledge)
        logger.info(
            "Loaded FF14 novice knowledge with "
            f"{len(knowledge.chunks)} chunks at {knowledge.source_commit[:12]}."
        )

    @filter.on_llm_request(priority=100)
    async def inject_knowledge(
        self, event: AstrMessageEvent, request: ProviderRequest
    ) -> None:
        if event.get_platform_name() not in {"qq_official", "aiocqhttp"}:
            return
        if event.get_extra("_mention_only_llm_allow") == "tarot_reading":
            return

        query_parts = [str(request.prompt or "")]
        with suppress(Exception):
            query_parts.append(str(event.get_message_str() or ""))
        context_text = render_context(self.index.search("\n".join(query_parts)))
        if context_text:
            event.set_extra("_mention_only_llm_allow", "ff14_novice")
            request.extra_user_content_parts.append(
                TextPart(text=context_text).mark_as_temp()
            )
