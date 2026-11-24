import json
import math
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models.setting import Setting
from app.risk.limits import RiskLimits

RISK_KEY = "risk_overrides"
KILL_KEY = "kill_switch"
MONEY_FIELDS = (
    "max_position_size", "max_loss_per_trade", "max_market_exposure", "max_total_exposure",
    "max_correlated_exposure", "daily_stop_loss", "weekly_stop_loss", "max_drawdown",
)
PCT_FIELDS = {"exit_take_profit_pct": (0.02, 5.0), "exit_stop_loss_pct": (0.05, 0.95)}
ALL_FIELDS = MONEY_FIELDS + tuple(PCT_FIELDS)


def defaults() -> dict[str, float]:
    s = get_settings()
    return {k: float(getattr(s, k)) for k in ALL_FIELDS}


async def _get_json(db: AsyncSession, key: str) -> dict:
    row = await db.get(Setting, key)
    if row is None:
        return {}
    try:
        data = json.loads(row.value)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


async def _put_json(db: AsyncSession, key: str, data: dict) -> None:
    row = await db.get(Setting, key)
    payload = json.dumps(data)
    if row is None:
        db.add(Setting(key=key, value=payload))
    else:
        row.value = payload
    await db.commit()


async def load_overrides(db: AsyncSession) -> dict[str, float]:
    raw = await _get_json(db, RISK_KEY)
    out: dict[str, float] = {}
    for k, v in raw.items():
        if k in ALL_FIELDS:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
    return out


async def save_overrides(db: AsyncSession, data: dict[str, float]) -> None:
    await _put_json(db, RISK_KEY, data)


def effective(overrides: dict[str, float]) -> dict[str, float]:
    return {**defaults(), **overrides}


def validate(updates: dict, capital: float, base: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    clean: dict[str, float] = {}
    errors: list[str] = []
    for key, raw in updates.items():
        if key not in ALL_FIELDS:
            errors.append(f"Неизвестный параметр: {key}")
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{key}: не число")
            continue
        if not math.isfinite(val) or val <= 0:
            errors.append(f"{key}: значение должно быть больше 0")
            continue
        if key in PCT_FIELDS:
            lo, hi = PCT_FIELDS[key]
            if not (lo <= val <= hi):
                errors.append(f"{key}: допустимо от {lo * 100:.0f}% до {hi * 100:.0f}%")
                continue
        elif val > capital:
            errors.append(f"{key}: не может быть больше капитала (${capital:.0f})")
            continue
        clean[key] = val
    merged = {**base, **clean}
    if merged["max_position_size"] > merged["max_total_exposure"]:
        errors.append("Ставка на сделку не может быть больше общего лимита в рынке")
    if merged["max_position_size"] > merged["max_market_exposure"]:
        errors.append("Ставка на сделку не может быть больше лимита на один рынок")
    if merged["max_loss_per_trade"] > merged["max_position_size"]:
        errors.append("Убыток на сделку не может быть больше самой ставки")
    if merged["daily_stop_loss"] > merged["weekly_stop_loss"]:
        errors.append("Дневной стоп не может быть больше недельного")
    return clean, errors


async def load_limits_db(db: AsyncSession) -> RiskLimits:
    v = effective(await load_overrides(db))
    return RiskLimits(**{k: v[k] for k in MONEY_FIELDS})


async def get_kill(db: AsyncSession) -> dict:
    d = await _get_json(db, KILL_KEY)
    return {"engaged": bool(d.get("engaged", False)), "reason": str(d.get("reason", ""))}


async def set_kill(db: AsyncSession, engaged: bool, reason: str) -> None:
    await _put_json(db, KILL_KEY, {"engaged": engaged, "reason": reason})
