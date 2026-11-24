from sqlalchemy.ext.asyncio import AsyncSession
from app.backtesting.metrics import compute_metrics
from app.models.backtest_run import BacktestRun
from app.models.backtest_trade import BacktestTrade

class BacktestEngine:
    def __init__(self, initial_capital: float = 100.0, fee_bps: float = 0.0, slippage_bps: float = 50.0) -> None:
        self.initial_capital = initial_capital
        self.fee_rate = fee_bps / 10_000.0
        self.slippage_rate = slippage_bps / 10_000.0

    async def run(self, db: AsyncSession, strategy: str, trades: list[dict], out_of_sample: bool = False) -> BacktestRun:
        pnls: list[float] = []
        run = BacktestRun(strategy=strategy, initial_capital=self.initial_capital, out_of_sample=out_of_sample, total_trades=0)
        db.add(run)
        await db.flush()
        for t in trades:
            entry = float(t["entry_price"]); exit_ = float(t["exit_price"]); size = float(t["size"]); side = t.get("side", "BUY")
            gross = (exit_ - entry) * size if side == "BUY" else (entry - exit_) * size
            fees = (entry + exit_) * size * self.fee_rate
            slip = (entry + exit_) * size * self.slippage_rate
            pnl = gross - fees - slip
            pnls.append(pnl)
            db.add(BacktestTrade(run_id=run.id, market_id=str(t.get("market_id", "")), side=side, entry_price=entry, exit_price=exit_, size=size, pnl=round(pnl, 4), entry_at=t.get("entry_at"), exit_at=t.get("exit_at")))
        metrics = compute_metrics(pnls, self.initial_capital)
        run.final_capital = self.initial_capital + sum(pnls)
        run.roi = metrics.roi
        run.max_drawdown = metrics.max_drawdown
        run.win_rate = metrics.win_rate
        run.profit_factor = metrics.profit_factor
        run.total_trades = metrics.total_trades
        await db.commit()
        return run
