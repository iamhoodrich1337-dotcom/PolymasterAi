"""Order book validation (pure functions, no network or database imports).

Polymarket returns levels as {"price": "0.48", "size": "120"}; older code assumed [price, size] lists.
Both are accepted here. All other modules should use these helpers instead of parsing books themselves."""
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class BookCheck:
    ok: bool
    reason: str = ""
    best_bid: float | None = None
    best_ask: float | None = None

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


def normalize_levels(raw: Any, descending: bool) -> list[tuple[float, float]]:
    """-> [(price, size), ...] best first (bids: highest price first, asks: lowest first).
    Drops levels with price outside (0, 1), non-positive size, NaN/inf or unparsable values."""
    out: list[tuple[float, float]] = []
    for level in raw or []:
        try:
            if isinstance(level, dict):
                price, size = float(level["price"]), float(level["size"])
            else:
                price, size = float(level[0]), float(level[1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if not (0.0 < price < 1.0) or not (size > 0.0) or size == float("inf"):
            continue
        out.append((price, size))
    out.sort(key=lambda lv: lv[0], reverse=descending)
    return out


def _timestamp_seconds(value: Any) -> float | None:
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    return ts / 1000.0 if ts > 1e11 else ts


def check_book(book: Any, *, max_age_seconds: float | None = None, now: float | None = None,
               require_bids: bool = True, require_asks: bool = True) -> BookCheck:
    """Validates an order book snapshot. Reasons: empty_asks, empty_bids, invalid_prices, crossed_book, stale_book, invalid_book.
    Note: the book timestamp may mean 'last change', so staleness is only enforced when max_age_seconds is given."""
    if not isinstance(book, dict):
        return BookCheck(False, "invalid_book")
    raw_bids, raw_asks = book.get("bids") or [], book.get("asks") or []
    bids = normalize_levels(raw_bids, True)
    asks = normalize_levels(raw_asks, False)
    if require_asks and not asks:
        return BookCheck(False, "invalid_prices" if raw_asks else "empty_asks")
    if require_bids and not bids:
        return BookCheck(False, "invalid_prices" if raw_bids else "empty_bids")
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    if best_bid is not None and best_ask is not None and best_bid >= best_ask:
        return BookCheck(False, "crossed_book", best_bid, best_ask)
    if max_age_seconds is not None:
        ts = _timestamp_seconds(book.get("timestamp"))
        if ts is not None and (now if now is not None else time.time()) - ts > max_age_seconds:
            return BookCheck(False, "stale_book", best_bid, best_ask)
    return BookCheck(True, "", best_bid, best_ask)
