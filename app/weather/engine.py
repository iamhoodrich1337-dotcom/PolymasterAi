"""Weather scout (SHADOW mode): finds Polymarket daily-high-temperature markets, builds a probability for each
temperature range from weather ensembles, and records it as a signal next to the market price.
It places NO trades. The records are used to measure whether the forecasts actually beat the market."""
import asyncio
import json
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.core.logging import get_logger
from app.core.utils import safe_json_loads, utc_now
from app.database.session import AsyncSessionLocal
from app.models.signal import Signal
from app.services.trading_cycle import _recent_signal_exists, upsert_markets
from app.weather.forecast import fetch_member_maxima, geocode
from app.weather.model import AIRPORTS, CITY_SLUGS, SIGMA, bin_probability, city_query, event_slug, extract_icao, parse_bin, parse_slug, station_from_text

logger = get_logger(__name__)
STRATEGY = "weather_ensemble"
DEDUPE_MINUTES = 120
MIN_RECORD_PROB = 0.02
LAST_WEATHER: dict[str, Any] = {}


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def _get_events(http: httpx.AsyncClient, base: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        resp = await http.get(f"{base}/events", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.debug("Gamma events request failed %s: %s", params, exc)
        return []


async def discover_events(http: httpx.AsyncClient, base: str, stats: Counter) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    today = datetime.now(timezone.utc).date()
    sem = asyncio.Semaphore(8)

    async def by_slug(slug: str) -> None:
        async with sem:
            for ev in await _get_events(http, base, {"slug": slug}):
                if ev.get("slug"):
                    found[ev["slug"]] = ev
                    stats["found_by_slug"] += 1

    await asyncio.gather(*[by_slug(event_slug(c, today + timedelta(days=i))) for c in CITY_SLUGS for i in range(-1, 4)])
    for tag in ("weather", "daily-temperature"):
        for ev in await _get_events(http, base, {"tag_slug": tag, "active": "true", "closed": "false", "limit": 200}):
            slug = ev.get("slug") or ""
            if slug.startswith("highest-temperature-in-") and slug not in found:
                found[slug] = ev
                stats["found_by_tag"] += 1
    return list(found.values())


async def run_weather_scan() -> dict[str, Any]:
    settings = get_settings()
    stats: Counter = Counter()
    unknown: set[str] = set()
    approx_cities: set[str] = set()
    items: list[dict[str, Any]] = []
    market_rows: list[dict[str, Any]] = []
    models_used: set[str] = set()
    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "polymaster-weather/1.0"}) as http:
        events = await discover_events(http, settings.polymarket_gamma_url, stats)
        stats["events"] = len(events)
        for ev in events:
            parsed = parse_slug(ev.get("slug") or "")
            if not parsed or ev.get("closed"):
                continue
            city, day = parsed
            mkts = [m for m in (ev.get("markets") or []) if isinstance(m, dict) and not m.get("closed")]
            texts = [ev.get("resolutionSource"), ev.get("description")] + [m.get("resolutionSource") for m in mkts] + [m.get("description") for m in mkts]
            icao = extract_icao(*texts) or station_from_text(*texts)
            coords = AIRPORTS.get(icao) if icao else None
            approx = coords is None
            if approx:
                coords = await geocode(http, city_query(city))
                if coords is None:
                    unknown.add(city)
                    stats["unknown_station"] += 1
                    continue
                stats["geocoded"] += 1
                approx_cities.add(city)
            first_bin = next((parse_bin(m.get("groupItemTitle") or m.get("question")) for m in mkts if parse_bin(m.get("groupItemTitle") or m.get("question"))), None)
            if first_bin is None:
                stats["no_bins"] += 1
                continue
            unit = first_bin[2]
            lat, lon = coords
            place = f"{city}≈" if approx else str(icao)
            maxima, used = await fetch_member_maxima(http, place, lat, lon, unit)
            models_used.update(used)
            members = maxima.get(day) or []
            if len(members) < 10:
                stats["no_forecast"] += 1
                continue
            mean = statistics.fmean(members)
            std = statistics.pstdev(members)
            stats["events_ok"] += 1
            for m in mkts:
                b = parse_bin(m.get("groupItemTitle") or m.get("question"))
                tokens = safe_json_loads(m.get("clobTokenIds"), [])
                if not b or not isinstance(tokens, list) or len(tokens) < 2 or m.get("enableOrderBook") is False:
                    stats["market_skipped"] += 1
                    continue
                stats["markets"] += 1
                prices = safe_json_loads(m.get("outcomePrices"), [])
                ask = _num(m.get("bestAsk")) or (_num(prices[0]) if prices else None)
                bid = _num(m.get("bestBid")) or ask
                if not ask or not (0.0 < ask < 1.0):
                    stats["no_price"] += 1
                    continue
                prob = bin_probability(members, b[0], b[1], SIGMA[unit])
                if prob < MIN_RECORD_PROB and ask < 0.05:
                    continue
                spread = max(0.0, ask - (bid or ask))
                edge = prob - ask - spread / 2.0 - settings.paper_slippage_bps / 10_000.0
                confidence = max(0.1, min(0.9, 1.0 - std / (6.0 if unit == "F" else 3.5)))
                label = m.get("groupItemTitle") or m.get("question")
                items.append({
                    "id": str(m.get("id")), "prob": prob, "ask": ask, "edge": edge, "confidence": confidence,
                    "reason": f"{city} {day} ({place}), {label}: ансамбль {len(members)} членов, среднее макс. {mean:.1f}°{unit} (разброс {std:.1f}); модель {prob * 100:.0f}% против рынка {ask * 100:.0f}%",
                    "sources": {"icao": icao, "approx_location": approx, "models": used, "members": len(members), "mean_max": round(mean, 2), "std": round(std, 2), "unit": unit, "bin": label, "day": day},
                })
                market_rows.append({
                    "id": str(m.get("id")), "condition_id": m.get("conditionId") or "", "question": m.get("question") or "",
                    "slug": m.get("slug"), "category": "weather", "outcomes": safe_json_loads(m.get("outcomes"), []),
                    "clob_token_ids": tokens, "end_date": m.get("endDate") or ev.get("endDate"), "active": True, "closed": False,
                    "neg_risk": bool(m.get("negRisk", False)), "liquidity": _num(m.get("liquidityNum")) or _num(m.get("liquidity")) or 0.0,
                    "volume": _num(m.get("volumeNum")) or _num(m.get("volume")) or 0.0, "volume_24hr": _num(m.get("volume24hr")) or 0.0, "spread": spread,
                })
    saved = 0
    if items:
        async with AsyncSessionLocal() as db:
            ok_ids = await upsert_markets(db, market_rows)
            since = utc_now() - timedelta(minutes=DEDUPE_MINUTES)
            for it in items:
                if it["id"] not in ok_ids or await _recent_signal_exists(db, STRATEGY, it["id"], since):
                    continue
                db.add(Signal(
                    strategy=STRATEGY, market_id=it["id"], outcome="Yes", market_probability=it["ask"], estimated_probability=it["prob"],
                    edge=it["edge"], confidence=it["confidence"], sources_json=json.dumps(it["sources"]), reason=it["reason"],
                    rejection_reason="Теневой режим: идёт проверка точности прогнозов, сделок нет", accepted=False,
                ))
                saved += 1
            await db.commit()
    LAST_WEATHER.clear()
    LAST_WEATHER.update({"at": utc_now().isoformat(), "events": stats["events"], "markets": stats["markets"], "saved": saved,
                         "unknown_stations": sorted(unknown), "approx_cities": sorted(approx_cities), "models": sorted(models_used), "stats": dict(stats)})
    logger.info("Weather scan: %s saved=%d unknown=%s approx_cities=%d models=%s", dict(stats), saved, sorted(unknown), len(approx_cities), sorted(models_used))
    return dict(LAST_WEATHER)
