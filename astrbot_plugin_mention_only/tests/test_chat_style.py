from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from chat_style import (  # noqa: E402
    STYLE_MARKER,
    append_natural_chat_style,
    compact_casual_reply,
    forget_expired_negative_contexts,
    is_casual_chat_message,
    normalize_casual_reply_max_chars,
    normalize_recent_negative_context_count,
    should_apply_natural_style,
)


class NaturalChatStyleTests(unittest.TestCase):
    def test_applies_only_to_supported_qq_platforms(self) -> None:
        self.assertTrue(should_apply_natural_style("qq_official", True))
        self.assertTrue(should_apply_natural_style(" AIOCQHTTP ", True))
        self.assertFalse(should_apply_natural_style("discord", True))
        self.assertFalse(should_apply_natural_style("qq_official", False))

    def test_appends_style_without_replacing_persona(self) -> None:
        prompt = append_natural_chat_style("Stay in character.")
        self.assertTrue(prompt.startswith("Stay in character."))
        self.assertIn(STYLE_MARKER, prompt)
        self.assertIn("usually use one", prompt)
        self.assertIn("Do not restate", prompt)
        self.assertIn("take priority over brevity", prompt)
        self.assertIn("humor must", prompt)
        self.assertIn("ask one useful follow-up", prompt)
        self.assertIn("Treat older insults", prompt)
        self.assertIn("Do not keep score", prompt)
        self.assertIn("roughly 30 Chinese characters", prompt)

    def test_does_not_append_the_style_twice(self) -> None:
        prompt = append_natural_chat_style("Stay in character.")
        self.assertEqual(append_natural_chat_style(prompt), prompt)

    def test_normalizes_recent_negative_context_count(self) -> None:
        self.assertEqual(normalize_recent_negative_context_count(-1), 0)
        self.assertEqual(normalize_recent_negative_context_count(4), 4)
        self.assertEqual(normalize_recent_negative_context_count(99), 20)
        self.assertEqual(normalize_recent_negative_context_count("invalid"), 4)

    def test_forgets_old_grudges_but_keeps_recent_context(self) -> None:
        old_normal = {"role": "user", "content": "周六晚上八点集合"}
        old_attack = {"role": "user", "content": "你这个垃圾机器人"}
        old_grudge = {
            "role": "assistant",
            "content": [{"type": "text", "text": "别再试探我的底线了"}],
        }
        recent_attack = {"role": "user", "content": "我现在真的很生气"}
        recent_reply = {"role": "assistant", "content": "那先说眼前这件事。"}
        contexts = [
            old_normal,
            old_attack,
            old_grudge,
            recent_attack,
            recent_reply,
        ]
        filtered = forget_expired_negative_contexts(contexts, keep_recent=2)
        self.assertEqual(filtered, [old_normal, recent_attack, recent_reply])

    def test_preserves_tool_context_even_when_negative(self) -> None:
        tool_context = {
            "role": "assistant",
            "content": "骚扰检测结果",
            "tool_calls": [{"id": "call-1"}],
        }
        self.assertEqual(
            forget_expired_negative_contexts([tool_context], keep_recent=0),
            [tool_context],
        )

    def test_does_not_treat_garbage_can_mechanic_as_abuse(self) -> None:
        context = {"role": "user", "content": "你知道垃圾桶机制怎么处理吗"}
        self.assertEqual(
            forget_expired_negative_contexts([context], keep_recent=0),
            [context],
        )

    def test_removes_the_paired_reply_with_old_negative_context(self) -> None:
        contexts = [
            {"role": "user", "content": "今天心情很差"},
            {"role": "assistant", "content": "要不先歇会儿。"},
            {"role": "user", "content": "周六八点集合"},
            {"role": "assistant", "content": "行。"},
            {"role": "user", "content": "换个话题"},
            {"role": "assistant", "content": "你说。"},
        ]
        self.assertEqual(
            forget_expired_negative_contexts(contexts, keep_recent=2),
            contexts[2:],
        )

    def test_classifies_casual_and_detailed_requests(self) -> None:
        self.assertTrue(is_casual_chat_message("你在干嘛"))
        self.assertTrue(is_casual_chat_message("今天好累啊"))
        self.assertFalse(is_casual_chat_message("为什么这个机制会团灭？"))
        self.assertFalse(is_casual_chat_message("请给我详细配置步骤"))
        self.assertFalse(
            is_casual_chat_message("抽张牌", allow_reason="tarot_reading")
        )
        self.assertFalse(is_casual_chat_message("/攻略 绝本"))

    def test_compacts_casual_reply_to_first_sentence(self) -> None:
        response = "在等你开口啊。其实我刚才还想了很多，不过没必要都说出来。"
        self.assertEqual(compact_casual_reply(response), "在等你开口啊。")
        self.assertEqual(compact_casual_reply("行。"), "行。")

    def test_compacts_unpunctuated_long_reply_at_natural_break(self) -> None:
        response = "今天确实有点累，不过看到你过来以后感觉好多了还想再聊一会儿"
        compacted = compact_casual_reply(response, max_chars=24)
        self.assertEqual(compacted, "今天确实有点累。")

    def test_normalizes_casual_reply_limit(self) -> None:
        self.assertEqual(normalize_casual_reply_max_chars(1), 16)
        self.assertEqual(normalize_casual_reply_max_chars(42), 42)
        self.assertEqual(normalize_casual_reply_max_chars(999), 120)
        self.assertEqual(normalize_casual_reply_max_chars("bad"), 42)


if __name__ == "__main__":
    unittest.main()
