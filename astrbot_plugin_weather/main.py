from __future__ import annotations

import asyncio
import time
from collections import OrderedDict

import httpx
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.star.filter.command import GreedyStr

from .weather_core import (
    Location,
    LocationNotFound,
    WeatherDataError,
    parse_forecast,
    parse_location,
    parse_weather_query,
    render_weather,
)


@register(
    "weather_lookup",
    "keita",
    "Queries current weather and short forecasts without an LLM.",
    "1.0.1",
)
class WeatherLookup(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        timeout = max(
            3.0,
            min(float(config.get("request_timeout_seconds", 12)), 30.0),
        )
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "2bot-weather/1.0 (https://github.com/zhui-zi/2bot)",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            },
        )
        self._geocode_lock = asyncio.Lock()
        self._last_geocode_request = 0.0
        self._location_cache: OrderedDict[str, tuple[float, Location]] = OrderedDict()

    @filter.command("weather", alias={"天气"})
    async def weather(self, event: AstrMessageEvent, query: GreedyStr = ""):
        """Query current weather or the forecast for a location."""
        location_query, day_index = parse_weather_query(str(query or ""))
        if not location_query:
            yield event.plain_result("想查哪里的天气？例如：/天气 北京 明天")
            return
        try:
            location = await self._geocode(location_query)
            payload = await self._forecast(location)
            report = parse_forecast(payload, location, day_index)
        except LocationNotFound:
            yield event.plain_result(
                f"没找到“{location_query}”，可以换成更完整的城市或地区名。"
            )
            return
        except (httpx.HTTPError, WeatherDataError, ValueError):
            logger.warning("Weather lookup failed.", exc_info=True)
            yield event.plain_result("天气服务暂时没响应，稍后再试一下。")
            return
        yield event.plain_result(render_weather(report))

    async def _geocode(self, query: str) -> Location:
        key = query.casefold()
        now = time.monotonic()
        cached = self._location_cache.get(key)
        if cached and cached[0] > now:
            self._location_cache.move_to_end(key)
            return cached[1]

        async with self._geocode_lock:
            now = time.monotonic()
            cached = self._location_cache.get(key)
            if cached and cached[0] > now:
                self._location_cache.move_to_end(key)
                return cached[1]
            wait_seconds = 1.05 - (now - self._last_geocode_request)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._last_geocode_request = time.monotonic()
            response = await self._client.get(
                str(
                    self.config.get(
                        "geocoding_url",
                        "https://nominatim.openstreetmap.org/search",
                    )
                ),
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 1,
                    "accept-language": "zh-CN,zh,en",
                },
            )
            response.raise_for_status()
            location = parse_location(response.json(), query)
            cache_hours = max(
                1.0,
                min(float(self.config.get("geocode_cache_hours", 24)), 168.0),
            )
            self._location_cache[key] = (
                time.monotonic() + cache_hours * 3600,
                location,
            )
            self._location_cache.move_to_end(key)
            while len(self._location_cache) > 256:
                self._location_cache.popitem(last=False)
            return location

    async def _forecast(self, location: Location):
        response = await self._client.get(
            str(
                self.config.get(
                    "forecast_url",
                    "https://api.open-meteo.com/v1/forecast",
                )
            ),
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,"
                    "weather_code,wind_speed_10m"
                ),
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "timezone": "auto",
                "forecast_days": 3,
            },
        )
        response.raise_for_status()
        return response.json()

    async def terminate(self) -> None:
        await self._client.aclose()
