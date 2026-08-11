from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart

from .meme_core import (
    is_supported_platform,
    load_meme_pack,
    render_context,
    select_entries,
)


@register(
    "three_kingdoms_memes",
    "keita",
    "Injects relevant 2010 Three Kingdoms meme context into QQ conversations.",
    "1.0.0",
)
class ThreeKingdomsMemes(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.meme_pack = load_meme_pack(Path(__file__).with_name("memes.json"))
        logger.info(
            "Loaded Three Kingdoms meme pack with %s entries.",
            len(self.meme_pack.entries),
        )

    @filter.on_llm_request()
    async def inject_meme_context(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        if not is_supported_platform(event.get_platform_name()):
            return
        if event.get_extra("_mention_only_llm_allow") == "tarot_reading":
            return

        query_parts = [str(request.prompt or "")]
        with suppress(Exception):
            query_parts.append(str(event.get_message_str() or ""))
        entries = select_entries(self.meme_pack, "\n".join(query_parts))
        context_text = render_context(entries)
        if not context_text:
            return

        request.extra_user_content_parts.append(
            TextPart(text=context_text).mark_as_temp()
        )
