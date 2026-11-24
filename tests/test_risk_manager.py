import pytest
from app.risk.manager import RiskManager

@pytest.mark.asyncio
async def test_total_exposure_limit_blocks(db_session):
    from app.models.position import Position
    db_session.add(Position(market_id="m1", token_id="t1", outcome="Yes", size=60, avg_price=0.4))
    await db_session.commit()
    rm = RiskManager()
    decision = await rm.check_trade(db=db_session, market_id="m2", token_id="t2", intended_size_usd=5, entry_price=0.5, is_full_loss=False)
    assert decision.allowed is False

@pytest.mark.asyncio
async def test_full_loss_capped_at_one_dollar(db_session):
    rm = RiskManager()
    decision = await rm.check_trade(db=db_session, market_id="m3", token_id="t3", intended_size_usd=5, entry_price=0.5, is_full_loss=True)
    assert decision.allowed is True
    assert decision.adjusted_size <= 1.0
