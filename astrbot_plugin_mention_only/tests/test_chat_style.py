from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from chat_style import (  # noqa: E402
    STYLE_MARKER,
    append_natural_chat_style,
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

    def test_does_not_append_the_style_twice(self) -> None:
        prompt = append_natural_chat_style("Stay in character.")
        self.assertEqual(append_natural_chat_style(prompt), prompt)


if __name__ == "__main__":
    unittest.main()
