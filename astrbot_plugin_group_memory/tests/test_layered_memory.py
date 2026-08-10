from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT.parent))

from astrbot_plugin_group_memory.layered_memory import (  # noqa: E402
    LongTermMemory,
    effective_memory_strength,
    extract_long_term_memories,
    forget_retracted_memories,
    learn_long_term_memories,
    parse_long_term_memory,
    prune_long_term_memories,
    reinforce_recalled_memories,
    render_long_term_memories,
    select_long_term_memories,
)
from astrbot_plugin_group_memory.memory_core import (  # noqa: E402
    MemoryRecord,
    member_reference,
)


DAY = 86400


class LayeredMemoryLearningTests(unittest.TestCase):
    @staticmethod
    def record(text: str, *, sender: str = "u1", timestamp: float = DAY):
        return MemoryRecord(timestamp, "user", sender, "甲", text)

    def test_learns_stable_preferences_habits_names_and_jobs(self) -> None:
        cases = {
            "我最喜欢钓鱼。": ("preference", "喜欢钓鱼"),
            "我平时晚上九点上线。": ("habit", "通常晚上九点上线"),
            "以后可以叫我小甲": ("preferred_name", "希望被称为小甲"),
            "我的主职是白魔法师": ("primary_job", "常用职业是白魔法师"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                learned = extract_long_term_memories(self.record(text))
                self.assertIn(expected, {(item.kind, item.text) for item in learned})

    def test_does_not_learn_secrets_hostility_or_romance_as_preferences(self) -> None:
        for text in (
            "我的 API key 是 abc",
            "我讨厌这个垃圾机器人",
            "我喜欢你",
            "/groupmemory clear",
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_long_term_memories(self.record(text)), ())

    def test_repeated_evidence_strengthens_without_duplicate(self) -> None:
        first = self.record("我喜欢钓鱼", timestamp=DAY)
        memories = learn_long_term_memories([], first, now=DAY)
        memories = learn_long_term_memories(
            memories,
            self.record("我喜欢钓鱼", timestamp=2 * DAY),
            now=2 * DAY,
        )
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].evidence_count, 2)
        self.assertGreater(memories[0].strength, 0.55)

    def test_exclusive_preferred_name_replaces_old_value(self) -> None:
        memories = learn_long_term_memories([], self.record("叫我小甲"), now=DAY)
        memories = learn_long_term_memories(
            memories,
            self.record("以后叫我甲甲", timestamp=2 * DAY),
            now=2 * DAY,
        )
        names = [memory for memory in memories if memory.kind == "preferred_name"]
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0].text, "希望被称为甲甲")

    def test_explicit_preference_retraction_forgets_old_memory(self) -> None:
        memories = learn_long_term_memories([], self.record("我喜欢钓鱼"), now=DAY)
        updated = learn_long_term_memories(
            memories,
            self.record("我现在不喜欢钓鱼了", timestamp=2 * DAY),
            now=2 * DAY,
        )
        self.assertEqual(updated, [])
        self.assertEqual(
            forget_retracted_memories(
                memories,
                self.record("忘掉我喜欢钓鱼", timestamp=2 * DAY),
            ),
            [],
        )

    def test_retraction_does_not_remove_another_members_preference(self) -> None:
        first = learn_long_term_memories([], self.record("我喜欢钓鱼"), now=DAY)
        second = learn_long_term_memories(
            first,
            self.record("我喜欢钓鱼", sender="u2", timestamp=DAY),
            now=DAY,
        )
        updated = learn_long_term_memories(
            second,
            self.record("我不再喜欢钓鱼", sender="u1", timestamp=2 * DAY),
            now=2 * DAY,
        )
        self.assertEqual([memory.subject_id for memory in updated], ["u2"])

    def test_round_trip_preserves_reinforcement_metadata(self) -> None:
        memory = LongTermMemory(
            "m1", "u1", "甲", "preference", "喜欢钓鱼", DAY, DAY,
            last_recalled_at=2 * DAY,
            strength=0.8,
            evidence_count=3,
            recall_count=4,
        )
        self.assertEqual(parse_long_term_memory(memory.to_dict()), memory)


class LayeredMemoryLifecycleTests(unittest.TestCase):
    @staticmethod
    def memory(
        memory_id: str,
        *,
        sender: str = "u1",
        name: str = "甲",
        text: str = "喜欢钓鱼",
        timestamp: float = DAY,
        strength: float = 0.8,
    ) -> LongTermMemory:
        return LongTermMemory(
            memory_id,
            sender,
            name,
            "preference",
            text,
            timestamp,
            timestamp,
            strength=strength,
        )

    def test_strength_halves_after_one_half_life(self) -> None:
        memory = self.memory("m1", strength=0.8)
        strength = effective_memory_strength(
            memory,
            now=DAY + 180 * DAY,
            half_life_days=180,
        )
        self.assertAlmostEqual(strength, 0.4, places=4)

    def test_recall_restores_strength_and_respects_cooldown(self) -> None:
        memory = self.memory("m1", strength=0.8)
        recalled = reinforce_recalled_memories(
            [memory],
            {"m1"},
            now=DAY + 180 * DAY,
            half_life_days=180,
            boost=0.1,
            cooldown_hours=12,
        )[0]
        self.assertAlmostEqual(recalled.strength, 0.5, places=4)
        self.assertEqual(recalled.recall_count, 1)
        unchanged = reinforce_recalled_memories(
            [recalled],
            {"m1"},
            now=recalled.last_recalled_at + 3600,
            cooldown_hours=12,
        )[0]
        self.assertEqual(unchanged, recalled)

    def test_weak_old_memory_is_forgotten_but_recent_memory_gets_grace(self) -> None:
        old = self.memory("old", timestamp=DAY, strength=0.1)
        recent = self.memory("recent", timestamp=100 * DAY, strength=0.05)
        kept = prune_long_term_memories(
            [old, recent],
            now=110 * DAY,
            half_life_days=180,
            min_strength=0.12,
            max_age_days=730,
        )
        self.assertEqual([memory.memory_id for memory in kept], ["recent"])

    def test_selection_combines_current_member_and_topic_relevance(self) -> None:
        memories = [
            self.memory("personal", sender="u1", name="甲", text="喜欢钓鱼"),
            self.memory("relevant", sender="u2", name="乙", text="喜欢烹饪"),
            self.memory("other", sender="u3", name="丙", text="喜欢挖矿"),
        ]
        selected = select_long_term_memories(
            memories,
            "乙平时喜欢做什么？",
            current_sender_id="u1",
            relevant_count=1,
            personal_count=1,
            now=2 * DAY,
        )
        self.assertEqual(
            {memory.memory_id for memory in selected},
            {"personal", "relevant"},
        )

    def test_render_hides_raw_ids_and_marks_memories_as_fallible(self) -> None:
        rendered = render_long_term_memories((self.memory("m1"),))
        self.assertIn(member_reference("u1"), rendered)
        self.assertIn("喜欢钓鱼", rendered)
        self.assertIn("可能随时间过时", rendered)
        self.assertNotIn("u1", rendered)


if __name__ == "__main__":
    unittest.main()
