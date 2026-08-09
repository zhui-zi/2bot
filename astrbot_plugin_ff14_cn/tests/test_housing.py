import sys
import unittest
from datetime import timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from astrbot_plugin_ff14_cn.housing import (  # noqa: E402
    APPLICATION_SECONDS,
    CYCLE_SECONDS,
    LOTTERY_ANCHOR,
    HousingCriteria,
    House,
    house_matches,
    lottery_cycle,
    parse_house,
    parse_housing_criteria,
)


def payload(**overrides):
    value = {
        "Server": 1043,
        "Area": 3,
        "Slot": 15,
        "ID": 19,
        "Price": 20_000_000,
        "Size": 1,
        "FirstSeen": int((LOTTERY_ANCHOR - timedelta(days=1)).timestamp()),
        "LastSeen": int((LOTTERY_ANCHOR + timedelta(hours=1)).timestamp()),
        "State": 0,
        "Participate": 0,
        "Winner": 0,
        "EndTime": 0,
        "UpdateTime": 0,
        "PurchaseType": 2,
        "RegionType": 0,
    }
    value.update(overrides)
    return value


class LotteryCycleTests(unittest.TestCase):
    def test_cycle_has_five_application_days_and_four_result_days(self):
        key, state, start, end = lottery_cycle(LOTTERY_ANCHOR)
        self.assertEqual(key, str(int(LOTTERY_ANCHOR.timestamp())))
        self.assertEqual(state, 1)
        self.assertEqual(end - start, APPLICATION_SECONDS)

        _key, state, start, end = lottery_cycle(
            LOTTERY_ANCHOR + timedelta(days=5)
        )
        self.assertEqual(state, 2)
        self.assertEqual(end - start, CYCLE_SECONDS)

        next_key, state, _start, _end = lottery_cycle(
            LOTTERY_ANCHOR + timedelta(days=9)
        )
        self.assertNotEqual(next_key, key)
        self.assertEqual(state, 1)

    def test_missing_lottery_details_are_inferred_from_first_seen(self):
        current = LOTTERY_ANCHOR + timedelta(hours=1)
        house = parse_house(payload(), current)

        self.assertIsNotNone(house)
        self.assertTrue(house.inferred)
        self.assertEqual(house.state, 1)
        self.assertEqual(
            house.end_time,
            int(LOTTERY_ANCHOR.timestamp()) + APPLICATION_SECONDS,
        )

    def test_house_discovered_after_round_start_waits_for_next_round(self):
        current = LOTTERY_ANCHOR + timedelta(hours=2)
        house = parse_house(
            payload(FirstSeen=int((LOTTERY_ANCHOR + timedelta(hours=1)).timestamp())),
            current,
        )

        self.assertEqual(house.state, 3)
        self.assertEqual(
            house.end_time,
            int(LOTTERY_ANCHOR.timestamp()) + CYCLE_SECONDS,
        )

    def test_reported_state_advances_across_expired_periods(self):
        application_end = int(LOTTERY_ANCHOR.timestamp()) + APPLICATION_SECONDS
        reported = payload(
            State=1,
            EndTime=application_end,
            UpdateTime=application_end - 60,
        )
        result_period = parse_house(
            reported,
            LOTTERY_ANCHOR + timedelta(days=6),
        )
        next_application = parse_house(
            reported,
            LOTTERY_ANCHOR + timedelta(days=9, hours=1),
        )

        self.assertEqual(result_period.state, 2)
        self.assertEqual(next_application.state, 1)
        self.assertEqual(
            next_application.end_time,
            int(LOTTERY_ANCHOR.timestamp()) + CYCLE_SECONDS + APPLICATION_SECONDS,
        )


class HousingCriteriaTests(unittest.TestCase):
    def test_parser_supports_servers_sizes_and_personal_filter(self):
        criteria, error = parse_housing_criteria("紫水栈桥 M/L 个人")

        self.assertEqual(error, "")
        self.assertEqual(criteria.server_ids, (1043,))
        self.assertEqual(criteria.sizes, {1, 2})
        self.assertEqual(criteria.audiences, {"personal"})

    def test_parser_supports_data_center_and_shared_only(self):
        criteria, error = parse_housing_criteria("豆豆柴 全房型 通用")

        self.assertEqual(error, "")
        self.assertEqual(len(criteria.server_ids), 5)
        self.assertEqual(criteria.sizes, {0, 1, 2})
        self.assertEqual(criteria.audiences, {"shared"})

    def test_server_is_required(self):
        criteria, error = parse_housing_criteria("M 个人")
        self.assertIsNone(criteria)
        self.assertIn("服务器", error)

    def test_personal_and_fc_filters_both_include_shared_houses(self):
        now = LOTTERY_ANCHOR + timedelta(hours=1)
        base = House(
            1043,
            3,
            15,
            19,
            20_000_000,
            1,
            int((now - timedelta(days=1)).timestamp()),
            int(now.timestamp()),
            1,
            0,
            0,
            int((now + timedelta(days=4)).timestamp()),
            int(now.timestamp()),
            2,
            0,
        )
        personal = HousingCriteria((1043,), frozenset({1}), frozenset({"personal"}))
        fc = HousingCriteria((1043,), frozenset({1}), frozenset({"fc"}))
        shared = HousingCriteria((1043,), frozenset({1}), frozenset({"shared"}))

        for criteria in (personal, fc, shared):
            with self.subTest(criteria=criteria):
                self.assertTrue(house_matches(base, criteria, now, 86400))
        self.assertFalse(
            house_matches(
                base.__class__(**{**base.__dict__, "region_type": 2}),
                shared,
                now,
                86400,
            )
        )


if __name__ == "__main__":
    unittest.main()
