from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from knowledge_core import KnowledgeIndex, load_knowledge, normalize_text, render_context


class KnowledgeCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.knowledge = load_knowledge(PLUGIN_ROOT / "knowledge.json")
        cls.index = KnowledgeIndex(cls.knowledge)

    def test_corpus_contains_general_and_duty_content(self) -> None:
        categories = {chunk.category for chunk in self.knowledge.chunks}
        self.assertIn("basic", categories)
        self.assertIn("duty", categories)
        self.assertGreaterEqual(len(self.knowledge.chunks), 500)

    def test_normalization_is_width_and_case_insensitive(self) -> None:
        self.assertEqual(normalize_text("ＦＦＸＩＶ"), "ffxiv")

    def test_gcd_question_retrieves_battle_knowledge(self) -> None:
        selected = self.index.search("FF14 里的 GCD 是什么意思？")
        self.assertTrue(selected)
        self.assertTrue(any("战斗" in chunk.title or "GCD" in chunk.text for chunk in selected))

    def test_sastasha_question_retrieves_matching_duty(self) -> None:
        selected = self.index.search("沙斯塔夏最后一个BOSS怎么打？")
        self.assertTrue(selected)
        self.assertTrue(any("沙斯塔夏" in chunk.title for chunk in selected))

    def test_unrelated_chat_does_not_retrieve_knowledge(self) -> None:
        self.assertEqual(self.index.search("今晚吃什么比较好？"), ())

    def test_swine_body_question_retrieves_curated_item_knowledge(self) -> None:
        selected = self.index.search("波奇服怎么获得？")
        self.assertTrue(selected)
        self.assertEqual(selected[0].title, "波奇服")
        self.assertIn("120,000", selected[0].text)
        self.assertIn("84,000", selected[0].text)

    def test_swine_body_context_does_not_expose_source_page(self) -> None:
        rendered = render_context(self.index.search("波奇服有什么用？"))
        self.assertIn("波奇服", rendered)
        self.assertNotIn("huijiwiki.com", rendered)

    def test_rendered_context_hides_sources(self) -> None:
        rendered = render_context(self.index.search("沙斯塔夏副本攻略"))
        self.assertIn("<ff14_novice_knowledge>", rendered)
        self.assertNotIn("github.com", rendered)
        self.assertNotIn("docs/duty", rendered)
        self.assertIn("不要提及知识库", rendered)


if __name__ == "__main__":
    unittest.main()
