from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from meme_core import (  # noqa: E402
    is_supported_platform,
    load_meme_pack,
    normalize_text,
    render_context,
    select_entries,
)


class ThreeKingdomsMemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_meme_pack(PLUGIN_ROOT / "memes.json")

    def test_pack_has_unique_curated_entries(self):
        entry_ids = [entry.entry_id for entry in self.pack.entries]
        self.assertGreaterEqual(len(entry_ids), 25)
        self.assertEqual(len(entry_ids), len(set(entry_ids)))

    def test_normalization_ignores_width_spaces_and_punctuation(self):
        self.assertEqual(normalize_text("接着奏乐，接着舞！"), "接着奏乐接着舞")
        self.assertEqual(normalize_text("ＡＢＣ"), "abc")

    def test_supports_only_qq_platforms(self):
        self.assertTrue(is_supported_platform("qq_official"))
        self.assertTrue(is_supported_platform(" AIOCQHTTP "))
        self.assertFalse(is_supported_platform("telegram"))

    def test_first_half_selects_the_expected_continuation(self):
        selected = select_entries(self.pack, "那就接着奏乐")
        self.assertEqual(selected[0].entry_id, "music_and_dance")

    def test_punctuation_variant_selects_cao_cao_denial(self):
        selected = select_entries(self.pack, "不可能，绝对不可能！")
        self.assertEqual(selected[0].entry_id, "impossible_denial")

    def test_general_meme_question_selects_overview(self):
        selected = select_entries(self.pack, "新三国梗都有哪些？")
        self.assertEqual(selected[0].entry_id, "overview")

    def test_generic_words_do_not_trigger(self):
        self.assertEqual(select_entries(self.pack, "这大概就是天意吧"), ())
        self.assertEqual(select_entries(self.pack, "今晚星夜出发"), ())
        self.assertEqual(select_entries(self.pack, "不可能吧"), ())

    def test_unrelated_chat_has_no_entries(self):
        self.assertEqual(select_entries(self.pack, "今晚吃什么？"), ())

    def test_multiple_memes_respect_entry_limit(self):
        selected = select_entries(
            self.pack,
            "接着奏乐，接着舞。不可能，绝对不可能。说出吾名！",
        )
        self.assertEqual(len(selected), self.pack.max_entries)

    def test_rendered_context_controls_overuse(self):
        entries = select_entries(self.pack, "接着奏乐")
        rendered = render_context(entries)
        self.assertIn("默认不要解释出处", rendered)
        self.assertIn("不要连续堆梗", rendered)
        self.assertIn("不要为了玩梗跳过事实回答", rendered)
        self.assertIn("tone=banter", rendered)

    def test_sorrow_entry_is_marked_solemn(self):
        entries = select_entries(self.pack, "故人陆续凋零，好似风中落叶")
        self.assertEqual(entries[0].entry_id, "old_friends_fall")
        self.assertEqual(entries[0].tone, "solemn")
        self.assertIn("不做戏谑改写", render_context(entries))

    def test_main_uses_temporary_content(self):
        source = (PLUGIN_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("mark_as_temp()", source)
        self.assertNotIn("request.system_prompt =", source)


if __name__ == "__main__":
    unittest.main()
