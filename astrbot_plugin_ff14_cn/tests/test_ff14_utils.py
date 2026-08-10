import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from ff14_utils import (  # noqa: E402
    BATTLEFIELD_ANCHOR,
    BATTLEFIELD_ROTATION,
    battlefield_for_time,
    battlefield_rotation_text,
    normalize_scene,
    normalize_subscription,
    parse_feed,
    resolve_qq_scene,
    strip_markup,
)


class BattlefieldTests(unittest.TestCase):
    def test_anchor_and_complete_rotation(self):
        for index, expected in enumerate(BATTLEFIELD_ROTATION):
            current = BATTLEFIELD_ANCHOR + timedelta(days=index)
            self.assertEqual(battlefield_for_time(current), expected)

    def test_rotation_changes_at_2300_shanghai(self):
        before = BATTLEFIELD_ANCHOR - timedelta(minutes=1)
        self.assertEqual(battlefield_for_time(before), BATTLEFIELD_ROTATION[-1])
        self.assertEqual(
            battlefield_for_time(BATTLEFIELD_ANCHOR), BATTLEFIELD_ROTATION[0]
        )

    def test_utc_input_is_converted(self):
        utc = ZoneInfo("UTC")
        current = datetime(2026, 4, 28, 15, 0, tzinfo=utc)
        self.assertEqual(battlefield_for_time(current), BATTLEFIELD_ROTATION[0])

    def test_rotation_text_shows_today_and_tomorrow_without_short_names(self):
        text = battlefield_rotation_text(BATTLEFIELD_ANCHOR)

        self.assertEqual(
            text,
            "【每日战场轮换】\n"
            "今日（2026-04-28）：周边遗迹群（阵地战）\n"
            "明日（2026-04-29）：昂萨哈凯尔（竞争战）",
        )
        self.assertNotIn("常用简称", text)


class FeedTests(unittest.TestCase):
    def test_rss_feed(self):
        items = parse_feed(
            """<?xml version="1.0"?>
            <rss version="2.0"><channel><item>
              <title>Maintenance &amp; News</title>
              <link>https://example.com/1</link><guid>entry-1</guid>
              <pubDate>Fri, 08 Aug 2026 12:00:00 GMT</pubDate>
              <description><![CDATA[<p>Hello <b>World</b></p>]]></description>
            </item></channel></rss>"""
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].item_id, "entry-1")
        self.assertEqual(items[0].title, "Maintenance & News")
        self.assertEqual(items[0].published, "2026-08-08 20:00")
        self.assertEqual(items[0].summary, "Hello World")

    def test_atom_feed(self):
        items = parse_feed(
            """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
              <id>tag:example,1</id><title>Event</title>
              <link href="https://example.com/2" />
              <updated>2026-08-08T13:00:00Z</updated>
              <summary>Summary</summary>
            </entry></feed>"""
        )
        self.assertEqual(items[0].link, "https://example.com/2")
        self.assertEqual(items[0].published, "2026-08-08 21:00")

    def test_markup_truncation(self):
        self.assertEqual(strip_markup("<p>A&nbsp; B</p>"), "A B")
        self.assertEqual(strip_markup("abcdef", 4), "abc…")


class SubscriptionTests(unittest.TestCase):
    def test_private_subscription_is_initialized_per_user(self):
        subscription = normalize_subscription(None, "user-1", "friend")

        self.assertEqual(subscription["scene"], "friend")
        self.assertEqual(subscription["user_id"], "user-1")
        self.assertNotIn("group_id", subscription)
        self.assertFalse(subscription["news"])
        self.assertFalse(subscription["pvp"])

    def test_existing_group_subscription_is_migrated_without_losing_state(self):
        existing = {"news": True, "news_seen": ["entry-1"]}
        subscription = normalize_subscription(existing, "group-1", "group")

        self.assertIs(subscription, existing)
        self.assertEqual(subscription["scene"], "group")
        self.assertEqual(subscription["group_id"], "group-1")
        self.assertTrue(subscription["news"])
        self.assertEqual(subscription["news_seen"], ["entry-1"])
        self.assertFalse(subscription["pvp"])

    def test_unknown_or_legacy_scene_defaults_to_group(self):
        self.assertEqual(normalize_scene(None), "group")
        self.assertEqual(normalize_scene("friend"), "friend")
        self.assertEqual(normalize_scene("unexpected"), "group")


class PlatformSceneTests(unittest.TestCase):
    def test_qq_official_and_snowluma_scenes_are_supported(self):
        self.assertEqual(resolve_qq_scene("qq_official", False, True), "group")
        self.assertEqual(resolve_qq_scene("qq_official", True, False), "friend")
        self.assertEqual(resolve_qq_scene("aiocqhttp", False, True), "group")
        self.assertEqual(resolve_qq_scene("aiocqhttp", True, False), "friend")

    def test_non_qq_and_ambiguous_events_are_rejected(self):
        self.assertEqual(resolve_qq_scene("discord", True, False), "")
        self.assertEqual(resolve_qq_scene("aiocqhttp", False, False), "")


if __name__ == "__main__":
    unittest.main()
