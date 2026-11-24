import time
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODELS = ("ecmwf_ifs025", "gfs025", "icon_seamless")
_cache: dict[tuple[str, str], tuple[float, dict[str, list[float]], list[str]]] = {}
CACHE_SECONDS = 25 * 60


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
