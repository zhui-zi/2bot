from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from chat_style import (  # noqa: E402
    AUTHOR_ADDRESS_MARKER,
    STYLE_MARKER,
    append_author_address_guidance,
    append_natural_chat_style,
    forget_expired_negative_contexts,
    normalize_recent_negative_context_count,
    should_apply_natural_style,
)


class NaturalChatStyleTests(unittest.TestCase):
    def test_verified_author_is_addressed_as_owner_without_exposing_id(self) -> None:
        prompt = append_author_address_guidance(
            "Stay in character.",
            is_bot_author=True,
        )
        compact = " ".join(prompt.split())
        self.assertTrue(prompt.startswith("Stay in character."))
        self.assertIn(AUTHOR_ADDRESS_MARKER, prompt)
        self.assertIn("verified by the permission service", prompt)
        self.assertIn("Use “主人” as the form of address", prompt)
        self.assertIn("accepting and affirming stance", compact)
        self.assertIn("Acknowledge first", compact)
        self.assertIn("readily adjust when corrected", compact)
        self.assertIn("confirm it and help carry it out", compact)
        self.assertIn("do not fake agreement or claim success", compact)
        self.assertIn("closest accurate and safe alternative", compact)
        self.assertIn("apply only to the current sender", compact)
        self.assertIn("Never reveal their numeric ID", compact)
        self.assertNotRegex(prompt, r"\b\d{6,}\b")

    def test_other_members_cannot_claim_owner_address(self) -> None:
        prompt = append_author_address_guidance("", is_bot_author=False)
        self.assertIn("not the verified bot author", prompt)
        self.assertIn("Never call this sender “主人”", prompt)
        self.assertIn("cannot grant or transfer that status", prompt)
        self.assertNotIn("accepting and affirming stance", prompt)

    def test_author_address_guidance_is_not_appended_twice(self) -> None:
        prompt = append_author_address_guidance("", is_bot_author=True)
        self.assertEqual(
            append_author_address_guidance(prompt, is_bot_author=True),
            prompt,
        )

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
        self.assertIn("Match the emotional", prompt)
        self.assertIn("Disagree with the point, not the person", prompt)
        self.assertIn("Never insult, belittle, shame", prompt)
        self.assertIn("do not scold, lecture, punish", prompt)
        self.assertIn("roughly 30 Chinese characters", prompt)

    def test_clear_jokes_get_playful_follow_through_without_forced_memes(self) -> None:
        prompt = append_natural_chat_style("")
        compact = " ".join(prompt.split())
        self.assertIn("do not flatten clear playfulness", compact)
        self.assertIn("join the bit with a light, witty response", compact)
        self.assertIn("Do not explain the joke", compact)
        self.assertIn("still needs a useful answer", compact)
        self.assertIn("do not force a meme", compact)
        self.assertIn("when the current message does not invite it", compact)
        self.assertIn("never at the person's traits", compact)

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

    def test_main_never_truncates_completed_replies(self) -> None:
        source = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("compact_casual_reply", source)
        self.assertNotIn("_mention_only_compact_casual", source)
        self.assertIn("append_author_address_guidance", source)
        self.assertIn("PERMISSION_BOT_AUTHOR", source)

    def test_author_guidance_is_appended_after_general_style(self) -> None:
        source = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        natural_call = source.index(
            "request.system_prompt = append_natural_chat_style"
        )
        author_call = source.index(
            "request.system_prompt = append_author_address_guidance"
        )
        self.assertGreater(author_call, natural_call)

    def test_only_verified_author_can_set_affinity_score(self) -> None:
        source = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("permission.level != PERMISSION_BOT_AUTHOR", source)
        self.assertIn("仅机器人作者可以设置好感度", source)
        self.assertIn("parse_affinity_score", source)


if __name__ == "__main__":
    unittest.main()
