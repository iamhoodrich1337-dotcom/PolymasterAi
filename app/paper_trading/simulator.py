from dataclasses import dataclass
from app.core.exceptions import InsufficientLiquidity

@dataclass
class FillResult:
    filled_size: float
    avg_price: float
    fee: float
    slippage: float
    partial: bool

@dataclass
class SellResult:
    sold_size: float
    avg_price: float
    fee: float
    proceeds: float
    partial: bool

class PaperSimulator:
    def __init__(self, slippage_bps: float = 50.0, fee_bps: float = 0.0) -> None:
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps

    def simulate_buy(self, asks: list[list[float]], size_usd: float, limit_price: float | None = None) -> FillResult:
        if not asks:
            raise InsufficientLiquidity("No asks available")
        remaining_usd = size_usd
        filled_size = 0.0
        cost = 0.0
        for price, qty in asks:
            price = float(price); qty = float(qty)
            if limit_price is not None and price > limit_price:
                break
            level_cost = price * qty
            take_cost = min(remaining_usd, level_cost)
            take_qty = take_cost / price
            cost += take_cost
            filled_size += take_qty
            remaining_usd -= take_cost
            if remaining_usd <= 1e-9:
                break
        if filled_size <= 0:
            raise InsufficientLiquidity("Order book could not fill any size")
        avg_price = cost / filled_size
        slippage = avg_price * (self.slippage_bps / 10_000.0)
        avg_price_with_slippage = avg_price + slippage
        fee = cost * (self.fee_bps / 10_000.0)
        partial = remaining_usd > 1e-6
        return FillResult(filled_size=round(filled_size, 8), avg_price=round(avg_price_with_slippage, 8), fee=round(fee, 8), slippage=round(slippage, 8), partial=partial)

    def simulate_sell(self, bids: list[list[float]], size: float) -> SellResult:
        """bids must be sorted best (highest) price first."""
        if not bids:
            raise InsufficientLiquidity("No bids available")
        remaining = size
        sold = 0.0
        revenue = 0.0
        for price, qty in bids:
            price = float(price); qty = float(qty)
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
