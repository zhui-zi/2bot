from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart

from .worldbook_core import (
    is_supported_platform,
    load_worldbook,
    render_context,
    select_entries,
)


@register(
    "ardbert_worldbook",
    "keita",
    "Injects topic-relevant Ardbert lore into QQ Official and SnowLuma chats.",
    "1.1.0",
)
class ArdbertWorldbook(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.worldbook = load_worldbook(Path(__file__).with_name("worldbook.json"))
        logger.info(
            f"Loaded Ardbert worldbook with {len(self.worldbook.entries)} entries."
        )

    @filter.on_llm_request()
    async def inject_worldbook(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        if not is_supported_platform(str(event.get_platform_name() or "")):
            return
        if event.get_extra("_mention_only_llm_allow") == "tarot_reading":
            return
        if not self._is_ardbert_persona(request):
            return

        query_parts = [str(request.prompt or "")]
        with suppress(Exception):
            query_parts.append(str(event.get_message_str() or ""))
        entries = select_entries(self.worldbook, "\n".join(query_parts))
        context_text = render_context(entries)
        if not context_text:
            return

        request.extra_user_content_parts.append(
            TextPart(text=context_text).mark_as_temp()
        )

    @staticmethod
    def _is_ardbert_persona(request: ProviderRequest) -> bool:
        prompt = request.system_prompt or ""
        return "阿尔博特" in prompt or "Ardbert" in prompt
