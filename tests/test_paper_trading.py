import pytest
from app.paper_trading.simulator import PaperSimulator

def test_partial_fill_when_depth_insufficient():
    sim = PaperSimulator(slippage_bps=0, fee_bps=0)
    asks = [[0.50, 10], [0.55, 5]]
    result = sim.simulate_buy(asks, size_usd=10.0)
    assert result.filled_size == pytest.approx(20.0)
    assert result.partial is True

def test_full_fill_with_slippage():
    sim = PaperSimulator(slippage_bps=100, fee_bps=0)
    asks = [[0.50, 100]]
    result = sim.simulate_buy(asks, size_usd=10.0)
    assert result.avg_price > 0.50
    assert result.partial is False
