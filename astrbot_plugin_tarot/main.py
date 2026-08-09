from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register
from astrbot.core.star.filter.command import GreedyStr

from .tarot_core import (
    TAROT_SYSTEM_PROMPT,
    Cooldown,
    build_daily_fortune_prompt,
    build_reading_prompt,
    draw_daily_fortune,
    draw_three_cards,
    format_daily_fortune,
    format_spread,
)


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@register(
    "tarot_reading",
    "keita",
    "Three-card Major Arcana readings for reflection and entertainment.",
    "1.3.0",
)
class TarotReading(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.cooldown = Cooldown(int(config.get("cooldown_seconds", 60)))

    @filter.command("tarot", alias={"塔罗"})
    async def tarot(self, event: AstrMessageEvent, question: GreedyStr):
        """Draw a three-card Major Arcana spread."""
        async for result in self._reading_results(event, str(question)):
            yield result

    async def _reading_results(self, event: AstrMessageEvent, question: str):
        normalized_question = re.sub(r"\s+", " ", question).strip()
        max_chars = max(20, min(500, int(self.config.get("max_question_chars", 200))))
        if normalized_question and len(normalized_question) > max_chars:
            yield event.plain_result(f"问题请控制在 {max_chars} 个字以内。")
            return

        sender_key = f"{event.get_platform_id()}:{event.get_sender_id()}"
        remaining = self.cooldown.consume(sender_key)
        if remaining:
            yield event.plain_result(f"请先让牌面沉淀一下，{remaining} 秒后再试。")
            return

        if normalized_question:
            cards = draw_three_cards()
            prompt = build_reading_prompt(normalized_question, cards)
            header = format_spread(normalized_question, cards)
        else:
            today = datetime.now(SHANGHAI_TZ).date()
            cards = draw_daily_fortune(sender_key, today)
            prompt = build_daily_fortune_prompt(today, cards)
            header = format_daily_fortune(today, cards)
        event.set_extra("_mention_only_llm_allow", "tarot_reading")
        event.set_extra("_tarot_spread_header", header)
        yield event.request_llm(
            prompt=prompt,
            system_prompt=TAROT_SYSTEM_PROMPT,
            contexts=[],
        )

    @filter.on_llm_response()
    async def finalize_reading(
        self,
        event: AstrMessageEvent,
        response: LLMResponse,
    ) -> None:
        header = event.get_extra("_tarot_spread_header")
        if not header or response is None:
            return
        body = (response.completion_text or "").strip()
        if not body:
            body = "【解读】这次牌面没有形成清晰的信息，请稍后重新抽牌。"
        disclaimer = (
            "【提示】塔罗仅供娱乐与自我反思，不替代医疗、法律、财务或其他专业建议。"
        )
        response.completion_text = f"{header}\n\n{body}\n\n{disclaimer}"
