from typing import Any
import httpx
from app.core.logging import get_logger
from app.strategies.base import BaseStrategy, StrategySignal

logger = get_logger(__name__)

class SportsStrategy(BaseStrategy):
    name = "sports"
    display_name = "Sports Trading"
    description = "Evaluates sports markets against a configured odds adapter."
    def __init__(self, odds_provider_url: str = "", api_key: str = "") -> None:
        super().__init__()
        self.odds_provider_url = odds_provider_url
        self.api_key = api_key
    async def evaluate(self, market: dict) -> StrategySignal | None:
        question = (market.get("question") or "").lower()
        if not any(k in question for k in ("win", "match", "game", "vs", "beat")):
            return None
        if not self.odds_provider_url:
            logger.info("Sports strategy skipped: odds provider not configured")
            return None
        odds = await self._fetch_odds(market)
        if odds is None:
            return None
        prob = float(odds["probability"])
        conf = float(odds["confidence"])
        source = str(odds.get("source", "sports_odds_provider"))
        market_prob = float(market.get("best_ask", 0.5))
        estimate = self.probability_engine.estimate(market_probability=market_prob, external_signals=[(prob, conf, source)])
        if estimate.confidence <= 0.0:
            return None
        edge = estimate.probability - market_prob
        if abs(edge) < 0.03:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="Yes", token_id=market["clob_token_ids"][0], market_probability=market_prob, estimated_probability=estimate.probability, edge=edge, confidence=estimate.confidence, sources=estimate.sources, reason=f"Sports edge {edge:+.4f} with confidence {estimate.confidence:.2f}")
    async def _fetch_odds(self, market: dict) -> dict[str, Any] | None:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.odds_provider_url, params={"market": market.get("slug") or market["id"]}, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict) or "probability" not in payload:
                    return None
                return payload
        except Exception as exc:
            logger.warning("Sports odds unavailable: %s", exc)
            return None
