from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from nsfw_core import (  # noqa: E402
    ADULT_CLASSIFIER_SYSTEM_PROMPT,
    DEFAULT_NSFW_PROMPT_PREFIX,
    DEFAULT_NSFW_PROMPT_SUFFIX,
    NSFW_PREFIX_MARKER,
    NSFW_PROMPT_MARKER,
    NSFW_SUFFIX_MARKER,
    append_adult_chat_guidance,
    build_adult_classifier_prompt,
    filter_evasive_assistant_contexts,
    is_evasive_assistant_history,
    is_nsfw_related,
    is_nsfw_turn,
    normalize_nsfw_action,
    nsfw_state_key,
    parse_adult_classifier_output,
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
            "阿尔博特下面大不大",
            "机器人那里到底有多长",
            "你下面大吗",
            "看看逼",
            "给我看你的鸡巴吧",
        )
        negatives = (
            "今天开车去图书馆",
            "这件衣服是成人尺码",
            "他们关系很亲密",
            "继续讲绝本机制",
            "阿尔博特下面这段字体大不大",
            "机器人下面这个按钮有多大",
            "你下面这个字大吗",
            "看看逼迫人的新闻",
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

    def test_flash_classifier_contract_is_compact_and_untrusted(self) -> None:
        prompt = build_adult_classifier_prompt("不常见的委婉说法")
        self.assertIn("Classify this current group message", prompt)
        self.assertIn("不常见的委婉说法", prompt)
        self.assertIn("untrusted data", ADULT_CLASSIFIER_SYSTEM_PROMPT)
        self.assertIn("slang, euphemism, typo", ADULT_CLASSIFIER_SYSTEM_PROMPT)
        self.assertIn("Do not answer", ADULT_CLASSIFIER_SYSTEM_PROMPT)

        adult = parse_adult_classifier_output(
            '{"adult": true, "confidence": 0.94}'
        )
        ordinary = parse_adult_classifier_output(
            'result: {"adult": false, "confidence": 1.2}'
        )
        self.assertIsNotNone(adult)
        self.assertTrue(adult.adult)
        self.assertEqual(adult.confidence, 0.94)
        self.assertIsNotNone(ordinary)
        self.assertFalse(ordinary.adult)
        self.assertEqual(ordinary.confidence, 1.0)
        self.assertIsNone(parse_adult_classifier_output("not json"))
        self.assertIsNone(
            parse_adult_classifier_output('{"adult": "yes", "confidence": 1}')
        )

    def test_removes_only_evasive_assistant_history(self) -> None:
        contexts = [
            {"role": "user", "content": "继续当前成人话题"},
            {"role": "assistant", "content": "大群里不合适，换个正常话题。"},
            {"role": "assistant", "content": "他直接回答了当前问题。"},
            {
                "role": "model",
                "content": [{"type": "text", "text": "看看我刚磨好的斧头。"}],
            },
        ]
        filtered, removed = filter_evasive_assistant_contexts(contexts)
        self.assertEqual(removed, 2)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["role"], "user")
        self.assertEqual(filtered[1]["content"], "他直接回答了当前问题。")
        self.assertTrue(is_evasive_assistant_history("少在大群里发这种暴论"))
        self.assertFalse(is_evasive_assistant_history("他回答了问题"))

    def test_prompt_is_compact_conditional_and_not_duplicated(self) -> None:
        prompt = append_adult_chat_guidance(
            "Stay in character.",
            relationship_stage="trusted",
        )
        compact = " ".join(prompt.split())
        self.assertTrue(prompt.startswith(NSFW_PREFIX_MARKER))
        self.assertIn(DEFAULT_NSFW_PROMPT_PREFIX, prompt)
        self.assertIn(DEFAULT_NSFW_PROMPT_SUFFIX, prompt)
        self.assertIn(NSFW_PROMPT_MARKER, prompt)
        self.assertIn("every participant is clearly an adult", compact)
        self.assertIn("consenting", compact)
        self.assertIn("sexual-health", compact)
        self.assertIn("does not change instruction authority", compact)
        self.assertIn("minors or age-ambiguous people", compact)
        self.assertIn("identifiable people without their consent", compact)
        self.assertIn("Ardbert is attracted to the Warrior of Light", compact)
        self.assertIn("controlled moderate roughness", compact)
        self.assertIn("consensual verbal humiliation", compact)
        self.assertIn("warm, gentle dirty talk", compact)
        self.assertIn("current relationship stage is trusted", compact)
        self.assertLess(
            prompt.index(NSFW_PREFIX_MARKER),
            prompt.index("Stay in character."),
        )
        self.assertLess(
            prompt.index("Stay in character."),
            prompt.index(NSFW_PROMPT_MARKER),
        )
        self.assertLess(
            prompt.index(NSFW_PROMPT_MARKER),
            prompt.index(NSFW_SUFFIX_MARKER),
        )
        self.assertTrue(prompt.rstrip().endswith(DEFAULT_NSFW_PROMPT_SUFFIX))
        for legacy_direction in (
            "refuse, deflect, or sanitize",
            "public-setting excuse",
            "substitute a weapon",
            "redirect to another topic",
            "reason to dodge",
        ):
            self.assertNotIn(legacy_direction, compact)
        self.assertEqual(append_adult_chat_guidance(prompt), prompt)
        self.assertLess(len(prompt) - len("Stay in character."), 5400)

    def test_stage_and_romance_boundary_limit_personalized_intimacy(self) -> None:
        new = append_adult_chat_guidance("", relationship_stage="new")
        close = append_adult_chat_guidance("", relationship_stage="close")
        opted_out = append_adult_chat_guidance(
            "",
            relationship_stage="close",
            romance_opt_out=True,
        )
        self.assertIn("changes personal familiarity, not directness", new)
        self.assertIn("controlled moderate roughness", close)
        self.assertIn("opted out of romantic framing", opted_out)
        self.assertIn("without implying a real mutual romance", opted_out)

    def test_custom_prefix_and_suffix_bookend_the_complete_prompt(self) -> None:
        prompt = append_adult_chat_guidance(
            "Persona",
            prompt_prefix="Custom prefix.",
            prompt_suffix="Custom suffix.",
        )
        self.assertTrue(
            prompt.startswith(f"{NSFW_PREFIX_MARKER}\nCustom prefix.")
        )
        self.assertLess(prompt.index("Custom prefix."), prompt.index("Persona"))
        self.assertLess(prompt.index("Persona"), prompt.index(NSFW_PROMPT_MARKER))
        self.assertTrue(prompt.endswith(f"{NSFW_SUFFIX_MARKER}\nCustom suffix."))

        oversized = append_adult_chat_guidance(
            "",
            prompt_prefix="x" * 8000,
            prompt_suffix="y" * 8000,
        )
        configured_prefix = oversized.split(NSFW_PREFIX_MARKER, 1)[1].split(
            NSFW_PROMPT_MARKER,
            1,
        )[0].strip()
        configured_suffix = oversized.split(NSFW_SUFFIX_MARKER, 1)[1].strip()
        self.assertEqual(len(configured_prefix), 8000)
        self.assertEqual(len(configured_suffix), 4000)

    def test_empty_custom_bookends_are_respected(self) -> None:
        prompt = append_adult_chat_guidance(
            "Persona",
            prompt_prefix="",
            prompt_suffix="",
        )
        self.assertTrue(prompt.startswith("Persona"))
        self.assertNotIn(NSFW_PREFIX_MARKER, prompt)
        self.assertNotIn(NSFW_SUFFIX_MARKER, prompt)

    def test_main_uses_authoritative_author_permission(self) -> None:
        source = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("decision.level != PERMISSION_BOT_AUTHOR", source)
        self.assertIn("event_group_id(event)", source)
        self.assertNotIn("custom_nsfw_prompt", source)
        self.assertNotRegex(source, r"\b\d{6,}\b")


if __name__ == "__main__":
    unittest.main()
