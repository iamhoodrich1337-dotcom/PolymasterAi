from typing import Any
from app.config import get_settings
from app.core.logging import get_logger
from app.core.utils import parse_float, safe_json_loads
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient

logger = get_logger(__name__)

class MarketScanner:
    def __init__(self, gamma: GammaClient, clob: ClobClient) -> None:
        self.gamma = gamma
        self.clob = clob
        self.settings = get_settings()

    async def scan(self, limit: int = 100) -> list[dict[str, Any]]:
        raw_markets = await self.gamma.list_markets(active=True, closed=False, limit=limit)
        results: list[dict[str, Any]] = []
        for m in raw_markets:
            if not isinstance(m, dict):
                continue
            market_id = str(m.get("id", ""))
            condition_id = m.get("conditionId") or m.get("condition_id") or ""
            if not market_id or not condition_id:
                continue
            liquidity = parse_float(m.get("liquidity"), 0.0)
            if liquidity < self.settings.min_liquidity:
                continue
            token_ids = safe_json_loads(m.get("clobTokenIds") or m.get("clob_token_ids"), [])
            outcomes = safe_json_loads(m.get("outcomes"), [])
            if not isinstance(token_ids, list) or len(token_ids) < 2:
                continue
            best_bid = 0.0
            best_ask = 0.0
            spread = 1.0
            try:
                book = await self.clob.get_order_book(token_ids[0])
                bids = book.get("bids") or []
                asks = book.get("asks") or []
                if bids and asks:
                    best_bid = max(parse_float(b[0], 0.0) for b in bids if isinstance(b, (list, tuple)))
                    best_ask = min(parse_float(a[0], 1.0) for a in asks if isinstance(a, (list, tuple)))
                    spread = max(0.0, best_ask - best_bid)
            except Exception as exc:
                logger.debug("Order book unavailable for %s: %s", market_id, exc)
            if spread > self.settings.max_spread:
                continue
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
        logger.info("Scanner returned %d tradable markets", len(results))
        return results
