# Weather Lookup

Compact AstrBot weather lookup using Nominatim geocoding and Open-Meteo forecasts.

## Commands

```text
/weather <location> [today|tomorrow|day after tomorrow]
/天气 <地点> [今天|明天|后天]
```

Natural Chinese requests such as `查一下明天上海天气` are routed without an LLM. Location results are cached, and public Nominatim requests are serialized to respect its one-request-per-second usage limit.

Weather data: [Open-Meteo](https://open-meteo.com/). Location data: [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), queried through the public [Nominatim service](https://operations.osmfoundation.org/policies/nominatim/).
