from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


DAY_LABELS = ("今天", "明天", "后天")


class WeatherDataError(ValueError):
    """Raised when a weather service returns incomplete data."""


class LocationNotFound(WeatherDataError):
    """Raised when a location query has no result."""


@dataclass(frozen=True)
class Location:
    label: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WeatherReport:
    location: str
    day_index: int
    condition: str
    temperature: float | None
    apparent_temperature: float | None
    temperature_min: float
    temperature_max: float
    precipitation_probability: int
    relative_humidity: int | None
    wind_speed: float | None


def parse_weather_query(value: str) -> tuple[str, int]:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ，,。.!！?？")
    day_index = 0
    for index, label in enumerate(DAY_LABELS):
        if label in text:
            day_index = index
            text = text.replace(label, " ")
            break
    text = re.sub(
        r"(?:的)?(?:天气|天气预报|气象)(?:怎么样|如何|情况|预报)?$",
        "",
        text,
    )
    text = re.sub(r"^(?:查|查询|查看|看看|搜|搜索)(?:一下)?", "", text)
    location = re.sub(r"\s+", " ", text).strip(" ，,。.!！?？")
    return location, day_index


def parse_location(payload: Any, query: str) -> Location:
    if not isinstance(payload, list) or not payload:
        raise LocationNotFound(query)
    item = payload[0]
    if not isinstance(item, dict):
        raise WeatherDataError("invalid geocoding response")
    try:
        latitude = float(item["lat"])
        longitude = float(item["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherDataError("invalid geocoding coordinates") from exc

    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    name = str(item.get("name") or query).strip()
    region = str(address.get("state") or address.get("region") or "").strip()
    country = str(address.get("country") or "").strip()
    qualifier = region if region and region not in name else country
    label = f"{name}（{qualifier}）" if qualifier and qualifier not in name else name
    return Location(label=label, latitude=latitude, longitude=longitude)


def parse_forecast(payload: Any, location: Location, day_index: int) -> WeatherReport:
    if day_index not in range(len(DAY_LABELS)) or not isinstance(payload, dict):
        raise WeatherDataError("invalid forecast response")
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherDataError("missing daily forecast")

    try:
        weather_code = int(_daily_value(daily, "weather_code", day_index))
        temperature_min = float(
            _daily_value(daily, "temperature_2m_min", day_index)
        )
        temperature_max = float(
            _daily_value(daily, "temperature_2m_max", day_index)
        )
        precipitation_probability = int(
            round(
                float(
                    _daily_value(
                        daily,
                        "precipitation_probability_max",
                        day_index,
                    )
                )
            )
        )
    except (TypeError, ValueError) as exc:
        raise WeatherDataError("invalid daily forecast") from exc

    current = payload.get("current") if day_index == 0 else None
    if not isinstance(current, dict):
        current = {}
    current_code = _optional_number(current.get("weather_code"), int)
    return WeatherReport(
        location=location.label,
        day_index=day_index,
        condition=weather_condition(
            int(current_code) if current_code is not None else weather_code
        ),
        temperature=_optional_number(current.get("temperature_2m"), float),
        apparent_temperature=_optional_number(
            current.get("apparent_temperature"), float
        ),
        temperature_min=temperature_min,
        temperature_max=temperature_max,
        precipitation_probability=max(0, min(100, precipitation_probability)),
        relative_humidity=_optional_number(
            current.get("relative_humidity_2m"), int
        ),
        wind_speed=_optional_number(current.get("wind_speed_10m"), float),
    )


def render_weather(report: WeatherReport) -> str:
    title = f"{report.location}｜{DAY_LABELS[report.day_index]}"
    temperature_range = (
        f"{_number(report.temperature_min)}～{_number(report.temperature_max)}°C"
    )
    if report.day_index == 0 and report.temperature is not None:
        current = f"{report.condition}，{_number(report.temperature)}°C"
        if report.apparent_temperature is not None:
            current += f"（体感 {_number(report.apparent_temperature)}°C）"
        details = [temperature_range, f"降水 {report.precipitation_probability}%"]
        if report.relative_humidity is not None:
            details.append(f"湿度 {report.relative_humidity}%")
        if report.wind_speed is not None:
            details.append(f"风速 {_number(report.wind_speed)} km/h")
        weather_lines = [current, "，".join(details)]
    else:
        weather_lines = [
            f"{report.condition}，{temperature_range}，降水 {report.precipitation_probability}%"
        ]
    return "\n".join([title, *weather_lines])


def weather_condition(code: int) -> str:
    if code == 0:
        return "晴"
    if code in {1, 2}:
        return "晴间多云"
    if code == 3:
        return "阴"
    if code in {45, 48}:
        return "雾"
    if 51 <= code <= 57:
        return "毛毛雨"
    if 61 <= code <= 67:
        return "雨"
    if 71 <= code <= 77:
        return "雪"
    if 80 <= code <= 82:
        return "阵雨"
    if 85 <= code <= 86:
        return "阵雪"
    if 95 <= code <= 99:
        return "雷暴"
    return "天气状况未知"


def _daily_value(daily: dict[str, Any], key: str, index: int) -> Any:
    values = daily.get(key)
    if not isinstance(values, list) or len(values) <= index or values[index] is None:
        raise WeatherDataError(f"missing {key}")
    return values[index]


def _optional_number(value: Any, converter):
    if value is None:
        return None
    try:
        return converter(value)
    except (TypeError, ValueError):
        return None


def _number(value: float) -> str:
    rounded = round(float(value), 1)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:.1f}"
