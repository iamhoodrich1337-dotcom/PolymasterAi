from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class BacktestMetrics:
    roi: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int

def compute_metrics(pnls: list[float], initial_capital: float) -> BacktestMetrics:
    if not pnls:
        return BacktestMetrics(0, 0, 0, 0, 0, 0, 0)
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    wins = []
    losses = []
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if pnl >= 0:
            wins.append(pnl)
        else:
            losses.append(abs(pnl))
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    return BacktestMetrics(roi=(equity - initial_capital) / initial_capital, max_drawdown=max_dd, win_rate=len(wins) / len(pnls), profit_factor=profit_factor, avg_win=sum(wins) / len(wins) if wins else 0.0, avg_loss=sum(losses) / len(losses) if losses else 0.0, total_trades=len(pnls))

def monthly_returns_pct(pnls_with_dates: list[tuple[datetime, float]], initial_capital: float) -> dict[str, float]:
    if not pnls_with_dates:
        return {}
    by_month: dict[str, list[float]] = defaultdict(list)
    for dt, pnl in pnls_with_dates:
        by_month[dt.strftime("%Y-%m")].append(pnl)
    capital = initial_capital
    result: dict[str, float] = {}
    for month in sorted(by_month.keys()):
        month_pnl = sum(by_month[month])
        pct = (month_pnl / capital) * 100.0 if capital else 0.0
        result[month] = round(pct, 4)
        capital += month_pnl
    return result
