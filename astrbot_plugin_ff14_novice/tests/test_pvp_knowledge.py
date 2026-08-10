from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from knowledge_core import KnowledgeIndex, load_knowledge, render_context


class PvpKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.knowledge = load_knowledge(PLUGIN_ROOT / "knowledge.json")
        cls.index = KnowledgeIndex(cls.knowledge)

    def test_generic_pvp_query_retrieves_setup_guidance(self) -> None:
        selected = self.index.search("PVP怎么玩？")
        self.assertTrue(selected)
        self.assertTrue(any("PvP" in chunk.title for chunk in selected))
        rendered = render_context(selected)
        self.assertIn("狼狱停船场", rendered)
        self.assertIn("不能视为当前数值", rendered)

    def test_frontline_query_retrieves_objective_guidance(self) -> None:
        selected = self.index.search("FF14战场新人应该怎么打？")
        self.assertTrue(selected)
        rendered = render_context(selected)
        self.assertIn("三方多人目标战", rendered)
        self.assertIn("避免在狭道", rendered)
        self.assertNotIn("6.3 版本每次击杀", rendered)

    def test_onsal_query_retrieves_map_specific_guidance(self) -> None:
        selected = self.index.search("昂萨哈凯尔怎么转点？")
        self.assertTrue(selected)
        self.assertEqual({chunk.document_id for chunk in selected}, {"curated/pvp/onsal"})
        self.assertIn("无垢大地", render_context(selected))

    def test_crystalline_conflict_query_retrieves_push_guidance(self) -> None:
        selected = self.index.search("水晶冲突打赢团战后做什么？")
        self.assertTrue(selected)
        self.assertIn(
            "curated/pvp/crystalline-conflict",
            {chunk.document_id for chunk in selected},
        )
        rendered = render_context(selected)
        self.assertIn("立刻确认水晶是否有人推进", rendered)
        self.assertIn("不要逐个回去送人", rendered)

    def test_map_overview_keeps_legacy_rules_out_of_current_claims(self) -> None:
        selected = self.index.search("纷争前线有哪些地图？")
        self.assertTrue(selected)
        rendered = render_context(selected)
        self.assertIn("尘封秘岩", rendered)
        self.assertIn("周边遗迹群", rendered)
        self.assertIn("不声称旧地图当前仍开放", rendered)


if __name__ == "__main__":
    unittest.main()
