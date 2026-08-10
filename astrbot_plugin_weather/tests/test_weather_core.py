from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from weather_core import (
    Location,
    LocationNotFound,
    parse_forecast,
    parse_location,
    parse_weather_query,
    render_weather,
    weather_condition,
)


class WeatherCoreTests(unittest.TestCase):
    def test_parses_location_and_day(self) -> None:
        cases = {
            "北京": ("北京", 0),
            "北京 今天": ("北京", 0),
            "明天 上海": ("上海", 1),
            "东京后天天气": ("东京", 2),
            "查一下明天上海天气": ("上海", 1),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_weather_query(value), expected)

    def test_parses_localized_location(self) -> None:
        location = parse_location(
            [
                {
                    "name": "海口市",
                    "lat": "20.0462328",
                    "lon": "110.1956502",
                    "address": {"state": "海南省", "country": "中国"},
                }
            ],
            "海口",
        )
        self.assertEqual(
            location,
            Location("海口市（海南省）", 20.0462328, 110.1956502),
        )
        with self.assertRaises(LocationNotFound):
            parse_location([], "不存在的地方")

    def test_renders_compact_current_weather(self) -> None:
        location = Location("海口市（海南省）", 20.0, 110.0)
        report = parse_forecast(
            {
                "current": {
                    "temperature_2m": 27.2,
                    "apparent_temperature": 30.1,
                    "relative_humidity_2m": 78,
                    "weather_code": 2,
                    "wind_speed_10m": 12.4,
                },
                "daily": {
                    "weather_code": [3, 61, 0],
                    "temperature_2m_max": [29.4, 28.0, 30.0],
                    "temperature_2m_min": [22.1, 21.0, 20.0],
                    "precipitation_probability_max": [40, 80, 10],
                },
            },
            location,
            0,
        )
        text = render_weather(report)
        self.assertIn("海口市（海南省）｜今天", text)
        self.assertIn("晴间多云，27.2°C（体感 30.1°C）", text)
        self.assertIn("22.1～29.4°C，降水 40%", text)
        self.assertIn("湿度 78%", text)
        self.assertIn("© OpenStreetMap contributors", text)
        self.assertEqual(len(text.splitlines()), 4)

    def test_renders_single_future_day(self) -> None:
        location = Location("上海市", 31.2, 121.5)
        report = parse_forecast(
            {
                "daily": {
                    "weather_code": [0, 61, 3],
                    "temperature_2m_max": [31, 29, 28],
                    "temperature_2m_min": [24, 23, 22],
                    "precipitation_probability_max": [10, 75, 30],
                }
            },
            location,
            1,
        )
        self.assertEqual(
            render_weather(report).splitlines()[1],
            "雨，23～29°C，降水 75%",
        )

    def test_maps_wmo_conditions(self) -> None:
        self.assertEqual(weather_condition(0), "晴")
        self.assertEqual(weather_condition(48), "雾")
        self.assertEqual(weather_condition(82), "阵雨")
        self.assertEqual(weather_condition(96), "雷暴")


if __name__ == "__main__":
    unittest.main()
