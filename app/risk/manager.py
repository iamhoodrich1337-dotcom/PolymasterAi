from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.core.logging import get_logger
from app.models.position import Position
from app.models.trade import Trade
from app.risk.kill_switch import KillSwitch
from app.risk.limits import load_limits
from app.risk.overrides import get_kill, load_limits_db

logger = get_logger(__name__)

@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""
    adjusted_size: float = 0.0
    checks: list[str] = field(default_factory=list)

class RiskManager:
    def __init__(self, kill_switch: KillSwitch | None = None) -> None:
        self.settings = get_settings()
        self.limits = load_limits()
        self.kill_switch = kill_switch or KillSwitch()

    async def check_trade(self, db: AsyncSession, market_id: str, token_id: str, intended_size_usd: float, entry_price: float, is_full_loss: bool) -> RiskDecision:
        checks: list[str] = []
        db_kill = None
        try:
            self.limits = await load_limits_db(db)
            db_kill = await get_kill(db)
        except Exception:
            logger.exception("Could not load risk overrides; using environment limits")
        if db_kill and db_kill.get("engaged"):
            return RiskDecision(False, f"Kill switch engaged: {db_kill.get('reason', '')}", 0.0, checks)
        if self.kill_switch.engaged:
            return RiskDecision(False, f"Kill switch engaged: {self.kill_switch.reason}", 0.0, checks)
        checks.append("kill_switch:ok")
        if not self.settings.live_trading_enabled:
            checks.append("live_mode:locked")
        size = min(intended_size_usd, self.limits.max_position_size)
        if is_full_loss:
            size = min(size, self.limits.max_loss_per_trade)
        checks.append(f"max_position:{size:.2f}")
        total_exposure = await self._total_exposure(db)
        if total_exposure + size > self.limits.max_total_exposure:
            return RiskDecision(False, f"Total exposure {total_exposure + size:.2f} > {self.limits.max_total_exposure}", 0.0, checks)
        checks.append(f"total_exposure:{total_exposure:.2f}")
        market_exposure = await self._market_exposure(db, market_id)
        if market_exposure + size > self.limits.max_market_exposure:
            return RiskDecision(False, f"Market exposure {market_exposure + size:.2f} > {self.limits.max_market_exposure}", 0.0, checks)
        checks.append(f"market_exposure:{market_exposure:.2f}")
        correlated = await self._correlated_exposure(db, market_id)
        if correlated + size > self.limits.max_correlated_exposure:
            return RiskDecision(False, f"Correlated exposure {correlated + size:.2f} > {self.limits.max_correlated_exposure}", 0.0, checks)
        checks.append(f"correlated_exposure:{correlated:.2f}")
        daily_pnl = await self._daily_realized_pnl(db)
        weekly_pnl = await self._weekly_realized_pnl(db)
        if daily_pnl <= -self.limits.daily_stop_loss:
            return RiskDecision(False, f"Daily stop loss reached ({daily_pnl:.2f})", 0.0, checks)
        if weekly_pnl <= -self.limits.weekly_stop_loss:
            return RiskDecision(False, f"Weekly stop loss reached ({weekly_pnl:.2f})", 0.0, checks)
        total_pnl = await self._all_time_pnl(db)
        if total_pnl <= -self.limits.max_drawdown:
            return RiskDecision(False, f"Max drawdown reached (total realized {total_pnl:.2f})", 0.0, checks)
        checks.append(f"daily_pnl:{daily_pnl:.2f}")
        checks.append(f"weekly_pnl:{weekly_pnl:.2f}")
        return RiskDecision(True, "All risk checks passed", size, checks)

    async def _total_exposure(self, db: AsyncSession) -> float:
        result = await db.execute(select(func.coalesce(func.sum(Position.size * Position.avg_price), 0.0)))
        return float(result.scalar() or 0.0)

    async def _market_exposure(self, db: AsyncSession, market_id: str) -> float:
        result = await db.execute(select(func.coalesce(func.sum(Position.size * Position.avg_price), 0.0)).where(Position.market_id == market_id))
        return float(result.scalar() or 0.0)

    async def _correlated_exposure(self, db: AsyncSession, market_id: str) -> float:
        return await self._market_exposure(db, market_id)

    async def _all_time_pnl(self, db: AsyncSession) -> float:
        result = await db.execute(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0)))
        return float(result.scalar() or 0.0)

    async def _daily_realized_pnl(self, db: AsyncSession) -> float:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0)).where(Trade.executed_at >= start))
        return float(result.scalar() or 0.0)

    async def _weekly_realized_pnl(self, db: AsyncSession) -> float:
        start = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0)).where(Trade.executed_at >= start))
        return float(result.scalar() or 0.0)

    async def monthly_performance(self, db: AsyncSession, initial_capital: float) -> dict:
        result = await db.execute(select(Trade.executed_at, Trade.realized_pnl).order_by(Trade.executed_at))
        rows = result.all()
        by_month: dict[str, float] = defaultdict(float)
        for executed_at, pnl in rows:
            if executed_at is None:
                continue
            by_month[executed_at.strftime("%Y-%m")] += float(pnl or 0.0)
        capital = initial_capital
        monthly: dict[str, dict] = {}
        for month in sorted(by_month.keys()):
            pnl = by_month[month]
            pct = (pnl / capital) * 100.0 if capital else 0.0
            monthly[month] = {"pnl_usd": round(pnl, 4), "return_pct": round(pct, 4), "capital_start": round(capital, 4), "capital_end": round(capital + pnl, 4)}
            capital += pnl
        return {"initial_capital": initial_capital, "months": monthly, "total_return_pct": round((capital - initial_capital) / initial_capital * 100, 4) if initial_capital else 0.0}
