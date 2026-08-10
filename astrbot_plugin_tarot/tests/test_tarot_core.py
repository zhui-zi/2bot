import random
import sys
import unittest
from datetime import date
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from tarot_core import (  # noqa: E402
    MAJOR_ARCANA,
    DAILY_FORTUNE_POSITIONS,
    SPREAD_POSITIONS,
    Cooldown,
    build_daily_fortune_prompt,
    build_reading_prompt,
    draw_daily_fortune,
    draw_three_cards,
    format_daily_fortune,
    format_reading_response,
    format_spread,
)


class TarotDeckTests(unittest.TestCase):
    def test_deck_has_22_unique_major_arcana(self):
        self.assertEqual(len(MAJOR_ARCANA), 22)
        self.assertEqual(len({card.number for card in MAJOR_ARCANA}), 22)
        self.assertEqual(len({card.name for card in MAJOR_ARCANA}), 22)

    def test_draw_is_unique_and_uses_all_positions(self):
        cards = draw_three_cards(random.Random(42))
        self.assertEqual(len({draw.card.number for draw in cards}), 3)
        self.assertEqual(tuple(draw.position for draw in cards), SPREAD_POSITIONS)
        self.assertTrue(all(draw.orientation in {"正位", "逆位"} for draw in cards))

    def test_prompt_contains_fixed_cards_and_safety_boundary(self):
        cards = draw_three_cards(random.Random(7))
        prompt = build_reading_prompt("我该如何调整近期的学习计划？", cards)
        for draw in cards:
            self.assertIn(draw.card.name, prompt)
            self.assertIn(draw.orientation, prompt)
        self.assertIn("不给成功率", prompt)
        self.assertIn("不超过 360 个中文字符", prompt)
        header = format_spread("我该如何调整近期的学习计划？", cards)
        self.assertIn("【塔罗三牌阵】", header)
        for draw in cards:
            self.assertIn(draw.card.name, header)

    def test_daily_fortune_is_stable_per_user_and_day(self):
        day = date(2026, 8, 9)
        first = draw_daily_fortune("qq:user-1", day)
        second = draw_daily_fortune("qq:user-1", day)
        next_day = draw_daily_fortune("qq:user-1", date(2026, 8, 10))
        self.assertEqual(first, second)
        self.assertNotEqual(first, next_day)
        self.assertEqual(tuple(card.position for card in first), DAILY_FORTUNE_POSITIONS)

    def test_daily_fortune_prompt_and_header(self):
        day = date(2026, 8, 9)
        cards = draw_daily_fortune("qq:user-2", day)
        prompt = build_daily_fortune_prompt(day, cards)
        header = format_daily_fortune(day, cards)
        self.assertIn("【今日运势】", prompt)
        self.assertIn("不给幸运率", prompt)
        self.assertIn("【今日运势塔罗】2026-08-09", header)
        for card in cards:
            self.assertIn(card.card.name, prompt)
            self.assertIn(card.card.name, header)

    def test_formats_complete_reading_and_empty_fallback(self):
        rendered = format_reading_response("【牌阵】", "【解读】向前走。")
        self.assertIn("【牌阵】", rendered)
        self.assertIn("【解读】向前走。", rendered)
        self.assertIn("仅供娱乐与自我反思", rendered)
        fallback = format_reading_response("【牌阵】", "")
        self.assertIn("没有形成清晰的信息", fallback)

    def test_main_routes_tarot_to_flash_without_default_request(self):
        source = (PLUGIN_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("chat_provider_id=self._provider_id()", source)
        self.assertNotIn("event.request_llm", source)


class CooldownTests(unittest.TestCase):
    def test_cooldown_is_per_key_and_expires(self):
        now = [100.0]
        cooldown = Cooldown(60, clock=lambda: now[0])
        self.assertEqual(cooldown.consume("a"), 0)
        self.assertEqual(cooldown.consume("b"), 0)
        now[0] = 130.0
        self.assertEqual(cooldown.consume("a"), 30)
        now[0] = 160.0
        self.assertEqual(cooldown.consume("a"), 0)


if __name__ == "__main__":
    unittest.main()
