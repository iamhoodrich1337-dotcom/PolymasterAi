from app.strategies.base import BaseStrategy, StrategySignal

class ArbitrageResearchStrategy(BaseStrategy):
    name = "arbitrage"
    display_name = "Arbitrage Research"
    description = "Detects discrepancies; never calls them guaranteed arbitrage."
    async def evaluate(self, market: dict) -> StrategySignal | None:
        token_ids = market.get("clob_token_ids") or []
        if len(token_ids) < 2:
            return None
        yes_ask = float(market.get("best_ask", 0.5))
        no_ask = 1.0 - float(market.get("best_bid", 0.5))
        total = yes_ask + no_ask
        edge = 1.0 - total
        cost_buffer = float(market.get("spread", 0.0)) + 0.02
        if edge <= cost_buffer:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="YES+NO", token_id=token_ids[0], market_probability=total, estimated_probability=1.0, edge=edge, confidence=0.25, sources=["clob_order_book"], reason=f"Binary sum {total:.4f}; theoretical edge {edge:.4f} before execution risk", rejection_reason="Arbitrage research signals are not auto-executed in paper mode")
