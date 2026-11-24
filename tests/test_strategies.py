import pytest
from app.strategies.arbitrage import ArbitrageResearchStrategy

@pytest.mark.asyncio
async def test_arbitrage_returns_research_not_trade():
    s = ArbitrageResearchStrategy()
    market = {"id": "m1", "clob_token_ids": ["t1", "t2"], "best_ask": 0.48, "best_bid": 0.50, "spread": 0.02}
    sig = await s.evaluate(market)
    assert sig is not None
    assert sig.rejection_reason is not None
