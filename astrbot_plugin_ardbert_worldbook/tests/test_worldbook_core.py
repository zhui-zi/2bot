from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from worldbook_core import (  # noqa: E402
    Worldbook,
    WorldbookEntry,
    is_supported_platform,
    load_worldbook,
    normalize_text,
    render_context,
    select_entries,
)


class WorldbookCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worldbook = load_worldbook(PLUGIN_ROOT / "worldbook.json")

    def test_worldbook_has_unique_entries(self):
        ids = [entry.entry_id for entry in self.worldbook.entries]
        self.assertGreaterEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))

    def test_normalization_is_case_and_width_insensitive(self):
        self.assertEqual(normalize_text("ＡＲＤＢＥＲＴ"), "ardbert")

    def test_supports_qq_official_and_snowluma(self):
        self.assertTrue(is_supported_platform("qq_official"))
        self.assertTrue(is_supported_platform("aiocqhttp"))
        self.assertTrue(is_supported_platform(" AIOCQHTTP "))
        self.assertFalse(is_supported_platform("telegram"))

    def test_selects_seto_without_unrelated_entries(self):
        selected = select_entries(self.worldbook, "你还记得赛特吗？")
        selected_ids = {entry.entry_id for entry in selected}
        self.assertIn("seto", selected_ids)
        self.assertNotIn("soul_rejoining", selected_ids)

    def test_old_source_alias_selects_companion_entry(self):
        selected = select_entries(self.worldbook, "你怎么看拉蜜蜜？")
        self.assertIn("lamitt", {entry.entry_id for entry in selected})

    def test_unrelated_chat_has_no_entries(self):
        self.assertEqual(select_entries(self.worldbook, "今晚吃什么？"), ())

    def test_render_context_preserves_spoiler_label(self):
        entry = WorldbookEntry(
            entry_id="test",
            title="Test",
            keywords=("test",),
            content="Content",
            spoiler="5.0",
        )
        rendered = render_context((entry,))
        self.assertIn("spoiler=5.0", rendered)
        self.assertIn("<ardbert_worldbook>", rendered)

    def test_selection_respects_entry_limit(self):
        entries = tuple(
            WorldbookEntry(
                entry_id=f"entry-{index}",
                title=f"Entry {index}",
                keywords=("shared",),
                content="Content",
                priority=index,
            )
            for index in range(5)
        )
        worldbook = Worldbook(entries=entries, max_entries=2, max_chars=1000)
        selected = select_entries(worldbook, "shared")
        self.assertEqual([entry.entry_id for entry in selected], ["entry-4", "entry-3"])


if __name__ == "__main__":
    unittest.main()
