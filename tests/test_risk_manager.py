import pytest

from app.risk.manager import RiskManager


@pytest.mark.asyncio
async def test_total_exposure_limit_blocks(db_session):
    # 60 shares at 0.40 = $24 at cost; another $5 would make $29 > $25 limit.
    from app.models.position import Position
    db_session.add(Position(market_id="m1", token_id="t1", outcome="Yes", size=60, avg_price=0.4))
    await db_session.commit()
    decision = await RiskManager().check_trade(db=db_session, market_id="m2", token_id="t2", intended_size_usd=5, entry_price=0.5, is_full_loss=False)
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_market_exposure_limit_blocks(db_session):
    # $4.50 already in m1; another $1 would make $5.50 > $5 per-market limit.
    from app.models.position import Position
    db_session.add(Position(market_id="m1", token_id="t1", outcome="Yes", size=9, avg_price=0.5))
    await db_session.commit()
    decision = await RiskManager().check_trade(db=db_session, market_id="m1", token_id="t1", intended_size_usd=1, entry_price=0.5, is_full_loss=False)
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_full_loss_capped_at_one_dollar(db_session):
    # Any unhedged purchase of a binary outcome can lose its whole stake, so the stake is capped at the max loss per trade.
    decision = await RiskManager().check_trade(db=db_session, market_id="m3", token_id="t3", intended_size_usd=5, entry_price=0.5, is_full_loss=True)
    assert decision.allowed is True
    assert decision.adjusted_size <= 1.0


@pytest.mark.asyncio
async def test_hedged_trade_may_use_full_position_limit(db_session):
    decision = await RiskManager().check_trade(db=db_session, market_id="m4", token_id="t4", intended_size_usd=5, entry_price=0.5, is_full_loss=False)
    assert decision.allowed is True
    assert decision.adjusted_size == pytest.approx(5.0)
