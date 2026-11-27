import pytest

from app.market_data.book_validation import check_book
from app.strategies.arbitrage import ArbitrageResearchStrategy, evaluate_basket


@pytest.mark.asyncio
async def test_single_market_never_produces_arbitrage_even_with_crossed_book():
    # bid 0.50 above ask 0.48 is a crossed (invalid) book: the "edge" is a data artefact, not arbitrage.
    market = {"id": "m1", "clob_token_ids": ["t1", "t2"], "best_ask": 0.48, "best_bid": 0.50, "spread": 0.02}
    assert await ArbitrageResearchStrategy().evaluate(market) is None
    assert check_book({"bids": [[0.50, 10]], "asks": [[0.48, 10]]}).ok is False


def _legs(prices_and_depths):
    return [{"market_id": f"m{i}", "token_id": f"t{i}", "asks": [[p, d]]} for i, (p, d) in enumerate(prices_and_depths)]


def test_basket_arbitrage_is_sized_by_the_thinnest_leg():
    legs = _legs([(0.30, 10), (0.30, 10), (0.30, 5)])  # sum 0.90, thinnest leg has 5 shares
    opp = evaluate_basket(legs, exhaustive=True, fee_bps=0, slippage_bps=0, min_net_edge_per_set=0.01)
    assert opp is not None
    assert opp.sets == 5
    assert opp.cost_usd == pytest.approx(4.5)
    assert opp.net_profit_usd == pytest.approx(0.5)
    assert opp.net_edge_per_set == pytest.approx(0.10)
    assert opp.risks  # execution risks are always listed


def test_basket_without_edge_is_rejected():
    assert evaluate_basket(_legs([(0.40, 10), (0.40, 10), (0.40, 10)]), exhaustive=True, slippage_bps=0) is None  # sum 1.2


def test_slippage_can_remove_a_thin_edge():
    legs = _legs([(0.495, 100), (0.490, 100)])  # sum 0.985
    assert evaluate_basket(legs, exhaustive=True, slippage_bps=0, min_net_edge_per_set=0.01) is not None
    assert evaluate_basket(legs, exhaustive=True, slippage_bps=100, min_net_edge_per_set=0.01) is None


def test_not_exhaustive_group_is_never_arbitrage():
    assert evaluate_basket(_legs([(0.20, 10), (0.20, 10)]), exhaustive=False) is None
    assert evaluate_basket(_legs([(0.20, 10)]), exhaustive=True) is None


def test_missing_leg_book_rejects_basket():
    legs = _legs([(0.30, 10), (0.30, 10)])
    legs[1]["asks"] = []
    assert evaluate_basket(legs, exhaustive=True) is None
