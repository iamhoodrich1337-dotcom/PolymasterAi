from datetime import datetime, timezone
from app.strategies.base import BaseStrategy, StrategySignal

class LatencyMonitorStrategy(BaseStrategy):
    name = "latency_monitor"
    display_name = "Latency & Price Monitor"
    description = "Flags stale quotes; does not claim latency arbitrage without measurement."
    async def evaluate(self, market: dict) -> StrategySignal | None:
        updated = market.get("updated_at")
        if not updated:
            return None
        try:
            ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        except ValueError:
            return None
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age < 300:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="STALE_DATA", token_id=market["clob_token_ids"][0], market_probability=float(market.get("best_ask", 0.5)), estimated_probability=float(market.get("best_ask", 0.5)), edge=0.0, confidence=0.0, sources=["market_snapshot"], reason=f"Quote is {age:.0f}s old", rejection_reason="Stale data; no trade permitted")
