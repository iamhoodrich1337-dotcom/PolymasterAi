from app.strategies.base import BaseStrategy, StrategySignal

class MarketMakingResearchStrategy(BaseStrategy):
    name = "market_making"
    display_name = "Market Making Research"
    description = "Estimates spread capture opportunities and inventory risk."
    async def evaluate(self, market: dict) -> StrategySignal | None:
        spread = float(market.get("spread", 1.0))
        liquidity = float(market.get("liquidity", 0.0))
        if spread < 0.02 or liquidity < 5000:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="MM_RESEARCH", token_id=market["clob_token_ids"][0], market_probability=float(market.get("best_ask", 0.5)), estimated_probability=float(market.get("best_bid", 0.5)), edge=spread / 2, confidence=0.2, sources=["clob_order_book"], reason=f"Wide spread {spread:.4f} on liquid market; research candidate only", rejection_reason="Market making research is not executed in paper mode")
