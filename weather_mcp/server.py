"""Minimal weather MCP server for sanje-simple.

Open-Meteo is free and keyless. The server geocodes a free-text place, fetches
one day of weather, and returns a flat summary the agent can use directly.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from mcp.server.fastmcp import FastMCP

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 15.0
SOURCE = "open-meteo"

mcp = FastMCP("sanje-weather")


def _get(url: str, params: dict) -> dict:
    try:
        with httpx.Client(
            timeout=TIMEOUT,
            headers={"User-Agent": "SanjeSimple/0.1"},
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"}


def geocode(location: str) -> dict:
    """Resolve a place name to coordinates."""
    payload = _get(
        GEOCODE_URL,
        {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json",
        },
    )
    if payload.get("_error"):
        raise ValueError(f"geocoding failed: {payload['_error']}")

    rows = payload.get("results") or []
    if not rows:
        raise ValueError(f"could not find a place called {location!r}")

    row = rows[0]
    return {
        "name": row.get("name") or location,
        "admin": row.get("admin1") or "",
        "country": row.get("country") or "",
        "latitude": row["latitude"],
        "longitude": row["longitude"],
    }


def best_window(
    times: list[str],
    temperatures: list[float],
    rain_probabilities: list[float],
    uv_indexes: list[float],
) -> dict | None:
    """Pick the most comfortable 3-hour daylight block.

    Lower rain, heat and UV win. This is a suggestion, not a schedule.
    """
    if not times:
        return None

    best: tuple[float, int, int] | None = None
    count = len(times)

    for start in range(count):
        try:
            hour = datetime.fromisoformat(times[start]).hour
        except ValueError:
            continue
        if hour < 6 or hour > 18:
            continue

        end = start + 3
        if end > count:
            break

        temps = temperatures[start:end]
        rain = rain_probabilities[start:end]
        uv = uv_indexes[start:end]
        if not temps or not rain or not uv:
            continue

        avg_temp = sum(temps) / len(temps)
        max_rain = max(rain)
        max_uv = max(uv)
        score = max_rain + max(0.0, avg_temp - 30.0) * 8 + max(0.0, max_uv - 6.0) * 10
        if max_rain >= 60:
            score += 50

        if best is None or score < best[0]:
            best = (score, start, end)

    if best is None:
        return None

    _, start, end = best
    return {
        "start": times[start][11:16],
        "end": times[end - 1][11:16],
        "avg_temp_c": round(sum(temperatures[start:end]) / (end - start), 1),
        "max_rain_probability": round(max(rain_probabilities[start:end])),
        "max_uv": round(max(uv_indexes[start:end]), 1),
    }


@mcp.tool()
def get_weather(location: str, day: str) -> dict:
    """Get one day of weather for a place.

    Use this before planning outdoor stops. The result includes temperature,
    rain chance, UV, sunrise/sunset and a suggested 3-hour outdoor window.

    Args:
        location: Free-text place name, e.g. "Mangalore" or "Udupi, India".
        day: ISO date, e.g. "2026-10-25".
    """
    try:
        target = date.fromisoformat(day)
    except ValueError:
        return {
            "unavailable": True,
            "error": f"day must be an ISO date such as 2026-10-25, got {day!r}",
            "source": SOURCE,
        }

    try:
        place = geocode(location)
    except ValueError as exc:
        return {
            "unavailable": True,
            "error": str(exc),
            "location": location,
            "day": target.isoformat(),
            "source": SOURCE,
        }

    payload = _get(
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": (
                "temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,precipitation_sum,"
                "uv_index_max,sunrise,sunset"
            ),
            "hourly": "temperature_2m,precipitation_probability,uv_index",
            "timezone": "auto",
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
        },
    )
    if payload.get("_error"):
        return {
            "unavailable": True,
            "error": f"forecast failed: {payload['_error']}",
            "location": location,
            "day": target.isoformat(),
            "source": SOURCE,
        }

    daily = payload.get("daily") or {}
    hourly = payload.get("hourly") or {}

    def daily_value(key: str):
        values = daily.get(key) or []
        return values[0] if values else None

    temps = [float(value) for value in (hourly.get("temperature_2m") or []) if value is not None]
    rain = [
        float(value or 0)
        for value in (hourly.get("precipitation_probability") or [])
        if value is not None
    ]
    uv = [float(value or 0) for value in (hourly.get("uv_index") or []) if value is not None]
    times = list(hourly.get("time") or [])

    temp_max = daily_value("temperature_2m_max")
    temp_min = daily_value("temperature_2m_min")
    rain_max = daily_value("precipitation_probability_max")
    rain_total = daily_value("precipitation_sum")
    uv_max = daily_value("uv_index_max")

    warnings = []
    if rain_max is not None and rain_max >= 60:
        warnings.append(f"{round(rain_max)}% chance of rain - keep an indoor backup")
    if temp_max is not None and temp_max >= 35:
        warnings.append(f"very hot ({round(temp_max)}C) - avoid midday outdoors")
    if uv_max is not None and uv_max >= 8:
        warnings.append(f"high UV ({round(uv_max)}) - cover up or stay in at midday")

    return {
        "unavailable": False,
        "source": SOURCE,
        "location": location,
        "resolved_name": ", ".join(
            part for part in (place["name"], place["admin"], place["country"]) if part
        ),
        "day": target.isoformat(),
        "timezone": payload.get("timezone"),
        "temperature_max_c": round(max(temps), 1) if temps else temp_max,
        "temperature_min_c": round(min(temps), 1) if temps else temp_min,
        "rain_probability_max": round(rain_max) if rain_max is not None else None,
        "rain_total_mm": round(rain_total, 1) if rain_total is not None else None,
        "uv_max": round(uv_max, 1) if uv_max is not None else None,
        "sunrise": daily_value("sunrise"),
        "sunset": daily_value("sunset"),
        "best_outdoor_window": best_window(times, temps, rain, uv),
        "warnings": warnings,
    }
