import time
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODELS = ("ecmwf_ifs025", "gfs025")
_cache: dict[tuple[str, str], tuple[float, dict[str, list[float]], list[str]]] = {}
CACHE_SECONDS = 3 * 3600  # forecast models update only every 6-12 hours; keeps us under the free API limit


async def fetch_member_maxima(http: httpx.AsyncClient, icao: str, lat: float, lon: float, unit: str) -> tuple[dict[str, list[float]], list[str]]:
    """Daily maximum temperature per ensemble member, per local date: {'2026-11-25': [m1, m2, ...]}."""
    key = (icao, unit)
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1], cached[2]
    result: dict[str, list[float]] = {}
    used: list[str] = []
    for model in MODELS:
        params: dict[str, Any] = {
            "latitude": lat, "longitude": lon, "hourly": "temperature_2m", "models": model,
            "temperature_unit": "fahrenheit" if unit == "F" else "celsius", "timezone": "auto", "forecast_days": 4,
        }
        try:
            resp = await http.get(ENSEMBLE_URL, params=params)
            resp.raise_for_status()
            hourly = (resp.json() or {}).get("hourly") or {}
        except Exception as exc:
            logger.warning("Open-Meteo %s failed for %s: %s", model, icao, exc)
            continue
        times = hourly.get("time") or []
        series = [v for k, v in hourly.items() if k.startswith("temperature_2m") and isinstance(v, list)]
        if not times or not series:
            continue
        used.append(model)
        for member in series:
            per_day: dict[str, float] = {}
            for t, v in zip(times, member):
                if v is None:
                    continue
                d = str(t)[:10]
                if d not in per_day or v > per_day[d]:
                    per_day[d] = float(v)
            for d, mx in per_day.items():
                result.setdefault(d, []).append(mx)
    _cache[key] = (time.time(), result, used)
    return result, used


GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_geo_cache: dict[str, tuple[float, float] | None] = {}


async def geocode(http: httpx.AsyncClient, name: str) -> tuple[float, float] | None:
    """City-centre coordinates (approximate) when the exact weather station is not in our table."""
    if name in _geo_cache:
        return _geo_cache[name]
    try:
        resp = await http.get(GEOCODE_URL, params={"name": name, "count": 1, "language": "en", "format": "json"})
        resp.raise_for_status()
        results = (resp.json() or {}).get("results") or []
        value = (float(results[0]["latitude"]), float(results[0]["longitude"])) if results else None
    except Exception as exc:
        logger.warning("Geocoding failed for %s: %s", name, exc)
        return None
    _geo_cache[name] = value
    return value
