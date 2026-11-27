from dataclasses import dataclass

from app.core.exceptions import InsufficientLiquidity
from app.market_data.book_validation import normalize_levels


@dataclass
class FillResult:
    filled_size: float      # shares received
    avg_price: float        # effective average price per share INCLUDING slippage (cost / shares)
    fee: float              # fee in USD, charged on top of cost
    slippage: float         # slippage per share (avg_price - raw book average)
    partial: bool
    cost: float = 0.0       # USD spent on shares, excluding fee; never exceeds the requested size_usd
    unfilled_usd: float = 0.0
    raw_avg_price: float = 0.0


@dataclass
class SellResult:
    sold_size: float
    avg_price: float
    fee: float
    proceeds: float         # USD received after fee
    partial: bool


class PaperSimulator:
    """Market-order simulator. Walks the book level by level.
    Slippage is applied to every level's price (a safety buffer for latency / queue effects), so
    shares = USD spent / effective price and the requested USD is never exceeded."""

    def __init__(self, slippage_bps: float = 50.0, fee_bps: float = 0.0) -> None:
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps

    def simulate_buy(self, asks: list, size_usd: float, limit_price: float | None = None) -> FillResult:
        levels = normalize_levels(asks, False)
        if not levels:
            raise InsufficientLiquidity("No valid asks available")
        if size_usd <= 0:
            raise InsufficientLiquidity("Order size must be positive")
        slip = self.slippage_bps / 10_000.0
        remaining_usd = float(size_usd)
        shares = spent = raw_cost = 0.0
        for price, qty in levels:
            if limit_price is not None and price > limit_price:
                break
            eff = price * (1.0 + slip)
            if eff >= 1.0:  # a share costing $1 or more cannot make money
                break
            take_usd = min(remaining_usd, eff * qty)
            take_shares = take_usd / eff
            spent += take_usd
            shares += take_shares
            raw_cost += take_shares * price
            remaining_usd -= take_usd
            if remaining_usd <= 1e-9:
                break
        if shares <= 0:
            raise InsufficientLiquidity("Order book could not fill any size")
        avg = spent / shares
        raw_avg = raw_cost / shares
        return FillResult(
            filled_size=round(shares, 8), avg_price=round(avg, 8), fee=round(spent * self.fee_bps / 10_000.0, 8),
            slippage=round(avg - raw_avg, 8), partial=remaining_usd > 1e-6, cost=round(spent, 8),
            unfilled_usd=round(max(0.0, remaining_usd), 8), raw_avg_price=round(raw_avg, 8),
        )

    def simulate_sell(self, bids: list, size: float) -> SellResult:
        levels = normalize_levels(bids, True)
        if not levels:
            raise InsufficientLiquidity("No valid bids available")
        remaining = float(size)
        sold = revenue = 0.0
        for price, qty in levels:
            take = min(remaining, qty)
            revenue += take * price
            sold += take
            remaining -= take
            if remaining <= 1e-9:
                break
        if sold <= 0:
            raise InsufficientLiquidity("Order book could not absorb any size")
        avg = (revenue / sold) * (1.0 - self.slippage_bps / 10_000.0)
        gross = avg * sold
        fee = gross * (self.fee_bps / 10_000.0)
        return SellResult(sold_size=round(sold, 8), avg_price=round(avg, 8), fee=round(fee, 8), proceeds=round(gross - fee, 8), partial=remaining > 1e-6)
