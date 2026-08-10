from __future__ import annotations

import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
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
    format_reading_response,
    format_spread,
)


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_FLASH_PROVIDER_ID = "deepseek_v4_flash"


@register(
    "tarot_reading",
    "keita",
    "Three-card Major Arcana readings for reflection and entertainment.",
    "1.4.0",
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
        try:
            response = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=self._provider_id(),
                    prompt=prompt,
                    system_prompt=TAROT_SYSTEM_PROMPT,
                    contexts=[],
                    temperature=0.7,
                    max_tokens=self._max_tokens(),
                    thinking={"type": "disabled"},
                ),
                timeout=self._timeout_seconds(),
            )
        except Exception as exc:
            logger.warning("Tarot Flash reading failed: %s", type(exc).__name__)
            yield event.plain_result("牌面已经抽好，但解读模型暂时不可用，请稍后再试。")
            return
        yield event.plain_result(
            format_reading_response(header, response.completion_text or "")
        )

    def _provider_id(self) -> str:
        return str(
            self.config.get("flash_provider_id", DEFAULT_FLASH_PROVIDER_ID)
            or DEFAULT_FLASH_PROVIDER_ID
        ).strip()

    def _timeout_seconds(self) -> float:
        try:
            value = float(self.config.get("reading_timeout_seconds", 20))
        except (TypeError, ValueError):
            value = 20
        return max(3.0, min(60.0, value))

    def _max_tokens(self) -> int:
        try:
            value = int(self.config.get("reading_max_tokens", 480))
        except (TypeError, ValueError):
            value = 480
        return max(128, min(1024, value))
