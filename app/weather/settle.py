"""Settles weather signals: after an event is over, asks Polymarket which temperature range won and
stores 1/0 inside each signal's sources_json (no database schema change needed)."""
import json
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.core.logging import get_logger
from app.core.utils import safe_json_loads
from app.database.session import AsyncSessionLocal
from app.models.signal import Signal
from app.weather.model import event_slug

logger = get_logger(__name__)
STRATEGY = "weather_ensemble"
MAX_EVENTS_PER_RUN = 40
LAST_SETTLE: dict[str, Any] = {}


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def settle_weather() -> dict[str, Any]:
    settings = get_settings()
    stats: Counter = Counter()
    today = datetime.now(timezone.utc).date()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Signal).where(Signal.strategy == STRATEGY).order_by(Signal.id.desc()).limit(6000))).scalars().all()
        pending: dict[tuple[str, str], list[tuple[Signal, dict[str, Any]]]] = {}
        for sig in rows:
            try:
                src = json.loads(sig.sources_json or "{}")
            except ValueError:
                continue
            if "resolved" in src:
                continue
            day = src.get("day")
            city = src.get("city") or (sig.reason or "").split(" ", 1)[0]
            try:
                if not day or not city or date.fromisoformat(day) >= today:
                    continue
            except ValueError:
                continue
            pending.setdefault((city, day), []).append((sig, src))
        stats["pending_events"] = len(pending)
        if pending:
            async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "polymaster-weather/1.0"}) as http:
                for (city, day), sigs in list(pending.items())[:MAX_EVENTS_PER_RUN]:
                    slug = event_slug(city, date.fromisoformat(day))
                    try:
                        resp = await http.get(f"{settings.polymarket_gamma_url}/events", params={"slug": slug})
                        resp.raise_for_status()
                        events = resp.json()
                    except Exception as exc:
                        logger.debug("Settle fetch failed %s: %s", slug, exc)
                        stats["fetch_failed"] += 1
                        continue
                    outcomes: dict[str, int] = {}
                    for ev in events if isinstance(events, list) else []:
                        for m in ev.get("markets") or []:
                            prices = safe_json_loads(m.get("outcomePrices"), [])
                            p = _num(prices[0]) if prices else None
                            if not m.get("closed") or p is None:
                                continue
                            if p >= 0.98:
                                outcomes[str(m.get("id"))] = 1
                            elif p <= 0.02:
                                outcomes[str(m.get("id"))] = 0
                    for sig, src in sigs:
                        r = outcomes.get(sig.market_id)
                        if r is None:
                            stats["not_resolved_yet"] += 1
                            continue
                        src["resolved"] = r
                        sig.sources_json = json.dumps(src)
                        stats["settled"] += 1
            await db.commit()
    LAST_SETTLE.clear()
    LAST_SETTLE.update({"at": datetime.now(timezone.utc).isoformat(), **stats})
    logger.info("Weather settle: %s", dict(stats))
    return dict(stats)
