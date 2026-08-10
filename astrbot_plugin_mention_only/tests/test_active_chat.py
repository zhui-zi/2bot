from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from active_chat import (  # noqa: E402
    is_active_reply_candidate,
    normalize_reply_percent,
    should_allow_llm_request,
    should_quote_group_reply,
    should_reply,
)


class ReplyPercentTests(unittest.TestCase):
    def test_normalizes_to_supported_range(self) -> None:
        self.assertEqual(normalize_reply_percent(-1), 0)
        self.assertEqual(normalize_reply_percent(5), 5)
        self.assertEqual(normalize_reply_percent(42), 30)
        self.assertEqual(normalize_reply_percent("invalid"), 0)

    def test_probability_boundaries(self) -> None:
        self.assertFalse(should_reply(0, 0))
        self.assertTrue(should_reply(30, 0.2999))
        self.assertFalse(should_reply(30, 0.3))

    def test_quotes_only_snowluma_group_messages_with_ids(self) -> None:
        self.assertTrue(
            should_quote_group_reply(
                platform_name="aiocqhttp",
                is_group_chat=True,
                message_id="123",
            )
        )
        self.assertFalse(
            should_quote_group_reply(
                platform_name="qq_official",
                is_group_chat=True,
                message_id="123",
            )
        )
        self.assertFalse(
            should_quote_group_reply(
                platform_name="aiocqhttp",
                is_group_chat=False,
                message_id="123",
            )
        )


class CandidateTests(unittest.TestCase):
    def candidate(self, **overrides: object) -> bool:
        values = {
            "platform_name": "aiocqhttp",
            "is_group_chat": True,
            "is_explicit_trigger": False,
            "sender_id": "user",
            "self_id": "bot",
            "message": "今天打什么？",
        }
        values.update(overrides)
        return is_active_reply_candidate(**values)

    def test_accepts_snowluma_and_qq_official_group_text(self) -> None:
        self.assertTrue(self.candidate())
        self.assertTrue(self.candidate(platform_name="qq_official"))

    def test_rejects_non_candidates(self) -> None:
        self.assertFalse(self.candidate(platform_name="discord"))
        self.assertFalse(self.candidate(is_group_chat=False))
        self.assertFalse(self.candidate(is_explicit_trigger=True))
        self.assertFalse(self.candidate(sender_id="bot"))
        self.assertFalse(self.candidate(message=""))
        self.assertFalse(self.candidate(message="/help"))


class LLMGateTests(unittest.TestCase):
    def allow(self, **overrides: object) -> bool:
        values = {
            "platform_name": "qq_official",
            "is_private_chat": False,
            "targets_bot": True,
            "allow_reason": "",
        }
        values.update(overrides)
        return should_allow_llm_request(**values)

    def test_allows_matched_ff14_official_private_request(self) -> None:
        self.assertTrue(
            self.allow(
                is_private_chat=True,
                targets_bot=False,
                allow_reason="ff14_novice",
            )
        )

    def test_keeps_unrelated_official_private_chat_blocked(self) -> None:
        self.assertFalse(
            self.allow(
                is_private_chat=True,
                targets_bot=False,
                allow_reason="",
            )
        )

    def test_preserves_group_mention_and_other_platform_behavior(self) -> None:
        self.assertTrue(self.allow())
        self.assertFalse(self.allow(targets_bot=False))
        self.assertTrue(
            self.allow(
                platform_name="aiocqhttp",
                is_private_chat=True,
                targets_bot=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
