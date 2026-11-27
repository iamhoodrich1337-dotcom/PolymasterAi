import pytest

from app.core.exceptions import InsufficientLiquidity
from app.paper_trading.simulator import PaperSimulator


def test_partial_fill_when_depth_insufficient():
    # Depth: 10 shares @0.50 = $5.00 and 5 shares @0.55 = $2.75 -> 15 shares for $7.75.
    # A $10 order therefore fills only 15 shares (not 20) and leaves $2.25 unfilled.
    sim = PaperSimulator(slippage_bps=0, fee_bps=0)
    result = sim.simulate_buy([[0.50, 10], [0.55, 5]], size_usd=10.0)
    assert result.filled_size == pytest.approx(15.0)
    assert result.cost == pytest.approx(7.75)
    assert result.avg_price == pytest.approx(7.75 / 15.0)
    assert result.unfilled_usd == pytest.approx(2.25)
    assert result.partial is True


def test_full_fill_with_slippage_never_exceeds_requested_usd():
    # 100 bps slippage: effective price 0.50 * 1.01 = 0.505 -> 10 / 0.505 shares; spend is exactly $10.
    sim = PaperSimulator(slippage_bps=100, fee_bps=0)
    result = sim.simulate_buy([[0.50, 100]], size_usd=10.0)
    assert result.avg_price == pytest.approx(0.505)
    assert result.filled_size == pytest.approx(10.0 / 0.505)
    assert result.cost == pytest.approx(10.0)
    assert result.filled_size * result.avg_price == pytest.approx(10.0)
    assert result.slippage == pytest.approx(0.005)
    assert result.partial is False


def test_fee_is_charged_on_top_of_cost():
    sim = PaperSimulator(slippage_bps=0, fee_bps=200)  # 2%
    result = sim.simulate_buy([[0.40, 100]], size_usd=10.0)
    assert result.cost == pytest.approx(10.0)
    assert result.fee == pytest.approx(0.20)


def test_limit_price_stops_the_walk():
    sim = PaperSimulator(slippage_bps=0, fee_bps=0)
    result = sim.simulate_buy([[0.50, 4], [0.60, 100]], size_usd=10.0, limit_price=0.55)
    assert result.filled_size == pytest.approx(4.0)
    assert result.partial is True


def test_unsorted_and_invalid_levels_are_handled():
    sim = PaperSimulator(slippage_bps=0, fee_bps=0)
    asks = [[0.60, 5], [0.0, 100], [1.0, 100], [0.50, -3], [0.50, 10], {"price": "0.55", "size": "2"}]
    result = sim.simulate_buy(asks, size_usd=5.0)
    # cheapest valid level is 0.50 x 10 shares ($5) -> fully filled there
    assert result.filled_size == pytest.approx(10.0)
    assert result.avg_price == pytest.approx(0.50)


def test_no_valid_asks_raises():
    sim = PaperSimulator()
    with pytest.raises(InsufficientLiquidity):
        sim.simulate_buy([[1.0, 10], [0.0, 5]], size_usd=5.0)
    with pytest.raises(InsufficientLiquidity):
        sim.simulate_buy([], size_usd=5.0)


def test_price_at_or_above_one_after_slippage_is_not_bought():
    sim = PaperSimulator(slippage_bps=100, fee_bps=0)
    with pytest.raises(InsufficientLiquidity):
        sim.simulate_buy([[0.995, 100]], size_usd=5.0)


def test_sell_walks_bids_best_first_and_reports_partial():
    sim = PaperSimulator(slippage_bps=0, fee_bps=0)
    result = sim.simulate_sell([[0.40, 5], [0.45, 5]], size=12.0)  # unsorted on purpose
    assert result.sold_size == pytest.approx(10.0)
    assert result.proceeds == pytest.approx(5 * 0.45 + 5 * 0.40)
    assert result.partial is True
