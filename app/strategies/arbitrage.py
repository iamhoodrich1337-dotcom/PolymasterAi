"""Arbitrage research.

Single binary market: with a valid order book 'YES ask + NO ask < 1' cannot exist, because the NO ask is
1 - best YES bid and bid < ask. An apparent edge there only comes from crossed / stale data, so
ArbitrageResearchStrategy.evaluate() deliberately returns None for single markets.

Real arbitrage candidates are BASKETS: a group of mutually exclusive AND exhaustive outcomes (exactly one
resolves YES, e.g. all temperature ranges of one city-day). Buying one YES share of every leg pays exactly $1.
evaluate_basket() prices that with real order-book depth, slippage and fees. It still does not call anything
'guaranteed': multi-leg partial fills, resolution rules and the exhaustiveness of the group are execution risks."""
from dataclasses import dataclass, field
from typing import Any

from app.market_data.book_validation import normalize_levels
from app.strategies.base import BaseStrategy, StrategySignal


@dataclass
class BasketOpportunity:
    sets: int
    cost_usd: float
    net_profit_usd: float
    net_edge_per_set: float
    top_of_book_edge: float
    legs: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


def _cost_to_buy(asks: list[tuple[float, float]], shares: float, slip: float) -> float | None:
    remaining, cost = shares, 0.0
    for price, qty in asks:
        eff = price * (1.0 + slip)
        if eff >= 1.0:
            return None
        take = min(remaining, qty)
        cost += take * eff
        remaining -= take
        if remaining <= 1e-9:
            return cost
    return None  # not enough depth


def evaluate_basket(legs: list[dict[str, Any]], exhaustive: bool, fee_bps: float = 0.0, slippage_bps: float = 50.0,
                    min_net_edge_per_set: float = 0.01, max_sets: int = 50) -> BasketOpportunity | None:
    """legs: [{'market_id', 'token_id', 'asks': [{'price','size'} or [price,size], ...]}] for the YES token of each outcome."""
    if not exhaustive or len(legs) < 2:
        return None
    books = []
    for leg in legs:
        asks = normalize_levels(leg.get("asks"), False)
        if not asks:
            return None
        books.append(asks)
    slip = slippage_bps / 10_000.0
    top = 1.0 - sum(b[0][0] for b in books)
    best: tuple[float, int, float] | None = None  # (profit, sets, cost)
    for n in range(1, max_sets + 1):
        costs = [_cost_to_buy(b, float(n), slip) for b in books]
        if any(c is None for c in costs):
            break
        cost = sum(costs)  # type: ignore[arg-type]
        profit = n * 1.0 - cost - cost * fee_bps / 10_000.0
        if profit / n >= min_net_edge_per_set and (best is None or profit > best[0]):
            best = (profit, n, cost)
    if best is None:
        return None
    profit, n, cost = best
    leg_info = [{"market_id": l.get("market_id"), "token_id": l.get("token_id"),
                 "avg_price": round(_cost_to_buy(b, float(n), slip) / n, 5)} for l, b in zip(legs, books)]  # type: ignore[operator]
    return BasketOpportunity(
        sets=n, cost_usd=round(cost, 4), net_profit_usd=round(profit, 4), net_edge_per_set=round(profit / n, 5),
        top_of_book_edge=round(top, 5), legs=leg_info,
        risks=["Every leg must fill; a partial fill leaves an unhedged position", "Group must really be exhaustive under the resolution rules",
               "Prices can move between the first and last leg"],
    )


class ArbitrageResearchStrategy(BaseStrategy):
    name = "arbitrage"
    display_name = "Arbitrage Research"
    description = "Basket arbitrage across mutually exclusive outcomes; single-market YES/NO sums are not arbitrage."

    async def evaluate(self, market: dict) -> StrategySignal | None:
        return None
