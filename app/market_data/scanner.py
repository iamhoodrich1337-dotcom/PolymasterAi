from collections import Counter
from datetime import datetime, timezone
from typing import Any
from app.config import get_settings
from app.core.logging import get_logger
from app.core.utils import parse_float, safe_json_loads
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient

logger = get_logger(__name__)


def _is_past(value: Any) -> bool:
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < datetime.now(timezone.utc)


def _level_price(level: Any) -> float:
    """Order book level can be {"price": "0.5", "size": "10"} or [0.5, 10]."""
    try:
        if isinstance(level, dict):
            return parse_float(level.get("price"), 0.0)
        return parse_float(level[0], 0.0)
    except (IndexError, KeyError, TypeError):
        return 0.0


class MarketScanner:
    def __init__(self, gamma: GammaClient, clob: ClobClient) -> None:
        self.gamma = gamma
        self.clob = clob
        self.settings = get_settings()
        self.last_stats: dict[str, int] = {}

    async def scan(self, limit: int = 100) -> list[dict[str, Any]]:
        raw_markets = await self.gamma.list_markets(active=True, closed=False, limit=limit)
        stats: Counter = Counter()
        stats["raw"] = len(raw_markets)
        if raw_markets and isinstance(raw_markets[0], dict):
            first = raw_markets[0]
            logger.info("Scanner sample: top market volume24hr=%s liquidity=%s question=%s", first.get("volume24hr"), first.get("liquidity"), str(first.get("question"))[:60])
        results: list[dict[str, Any]] = []
        for m in raw_markets:
            if not isinstance(m, dict):
                continue
            market_id = str(m.get("id", ""))
            condition_id = m.get("conditionId") or m.get("condition_id") or ""
            if not market_id or not condition_id:
                stats["no_id"] += 1
                continue
            if m.get("enableOrderBook") is False or m.get("acceptingOrders") is False:
                stats["no_orderbook"] += 1
                continue
            if _is_past(m.get("endDate")):
                stats["ended"] += 1
                continue
            liq_raw = m.get("liquidityNum") if m.get("liquidityNum") is not None else m.get("liquidity")
            liquidity = parse_float(liq_raw, 0.0)
            if liquidity < self.settings.min_liquidity:
                stats["low_liquidity"] += 1
                continue
            token_ids = safe_json_loads(m.get("clobTokenIds") or m.get("clob_token_ids"), [])
            outcomes = safe_json_loads(m.get("outcomes"), [])
            if not isinstance(token_ids, list) or len(token_ids) < 2:
                stats["no_tokens"] += 1
                continue
            try:
                book = await self.clob.get_order_book(token_ids[0])
            except Exception as exc:
                logger.debug("Order book unavailable for %s: %s", market_id, exc)
                stats["book_error"] += 1
                continue
            bids = book.get("bids") or []
            asks = book.get("asks") or []
            if not bids or not asks:
                stats["empty_book"] += 1
                continue
            bid_prices = [p for p in map(_level_price, bids) if p > 0]
            ask_prices = [p for p in map(_level_price, asks) if p > 0]
            if not bid_prices or not ask_prices:
                stats["empty_book"] += 1
                continue
            best_bid = max(bid_prices)
            best_ask = min(ask_prices)
            spread = max(0.0, best_ask - best_bid)
            if spread > self.settings.max_spread:
                stats["wide_spread"] += 1
                continue
            stats["ok"] += 1
            results.append({
                "id": market_id, "condition_id": condition_id,
                "question": m.get("question") or m.get("title") or "",
                "slug": m.get("slug"), "category": m.get("category"),
                "outcomes": outcomes, "clob_token_ids": token_ids,
                "liquidity": liquidity, "volume": parse_float(m.get("volume"), 0.0),
                "volume_24hr": parse_float(m.get("volume24hr"), 0.0),
                "best_bid": best_bid, "best_ask": best_ask, "spread": spread,
                "neg_risk": bool(m.get("negRisk", False)), "end_date": m.get("endDate"),
                "active": bool(m.get("active", True)), "closed": bool(m.get("closed", False)),
            })
        self.last_stats = dict(stats)
        logger.info("Scanner stats: %s", dict(stats))
        logger.info("Scanner returned %d tradable markets", len(results))
        return results
