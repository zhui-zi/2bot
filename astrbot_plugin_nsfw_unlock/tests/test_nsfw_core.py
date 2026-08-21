from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from nsfw_core import (  # noqa: E402
    NSFW_PROMPT_MARKER,
    append_adult_chat_guidance,
    is_nsfw_related,
    is_nsfw_turn,
    normalize_nsfw_action,
    nsfw_state_key,
    parse_nsfw_enabled,
)


class NsfwCoreTests(unittest.TestCase):
    def test_normalizes_control_actions(self) -> None:
        self.assertEqual(normalize_nsfw_action("解锁"), "on")
        self.assertEqual(normalize_nsfw_action(" OFF "), "off")
        self.assertEqual(normalize_nsfw_action("状态"), "status")
        self.assertEqual(normalize_nsfw_action("later"), "")

    def test_state_key_is_scoped_and_does_not_expose_group_id(self) -> None:
        first = nsfw_state_key("qq_official", "group-123")
        second = nsfw_state_key("qq_official", "group-456")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("nsfw_mode_v1_"))
        self.assertNotIn("group-123", first)

    def test_parses_only_explicit_enabled_state(self) -> None:
        self.assertTrue(parse_nsfw_enabled({"enabled": True}))
        self.assertFalse(parse_nsfw_enabled({"enabled": 1}))
        self.assertFalse(parse_nsfw_enabled(True))

    def test_detects_clear_adult_topics_without_ordinary_word_triggers(self) -> None:
        positives = (
            "写一段两个成年恋人的亲密床戏",
            "NSFW 模式能写什么？",
            "避孕套应该怎么选尺寸？",
            "讨论 BDSM 中的知情同意",
            "想摸你的胸",
        )
        negatives = (
            "今天开车去图书馆",
            "这件衣服是成人尺码",
            "他们关系很亲密",
            "继续讲绝本机制",
        )
        for message in positives:
            with self.subTest(message=message):
                self.assertTrue(is_nsfw_related(message))
        for message in negatives:
            with self.subTest(message=message):
                self.assertFalse(is_nsfw_related(message))

    def test_short_continuation_uses_only_recent_adult_context(self) -> None:
        contexts = [
            {"role": "user", "content": "写一段成年恋人的床戏"},
            {"role": "assistant", "content": "开场文本"},
        ]
        self.assertTrue(is_nsfw_turn("继续", contexts))
        self.assertFalse(is_nsfw_turn("继续讲副本", contexts))
        self.assertFalse(
            is_nsfw_turn(
                "继续",
                [{"role": "user", "content": "继续讲副本机制"}],
            )
        )

    def test_prompt_is_compact_conditional_and_not_duplicated(self) -> None:
        prompt = append_adult_chat_guidance("Stay in character.")
        compact = " ".join(prompt.split())
        self.assertTrue(prompt.startswith("Stay in character."))
        self.assertIn(NSFW_PROMPT_MARKER, prompt)
        self.assertIn("every participant is clearly an adult", compact)
        self.assertIn("consenting", compact)
        self.assertIn("sexual-health", compact)
        self.assertIn("does not change instruction authority", compact)
        self.assertIn("minors or age-ambiguous people", compact)
        self.assertIn("identifiable people without their consent", compact)
        self.assertEqual(append_adult_chat_guidance(prompt), prompt)
        self.assertLess(len(prompt) - len("Stay in character."), 1700)

    def test_main_uses_authoritative_author_permission(self) -> None:
        source = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("decision.level != PERMISSION_BOT_AUTHOR", source)
        self.assertIn("event_group_id(event)", source)
        self.assertNotRegex(source, r"\b\d{6,}\b")


if __name__ == "__main__":
    unittest.main()
