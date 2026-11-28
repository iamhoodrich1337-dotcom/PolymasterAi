import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.models.paper_fill import PaperFill
from app.models.paper_order import PaperOrder
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.trade import Trade

MODELS = [Position, PaperOrder, PaperFill, Trade, PortfolioSnapshot]


def _money_columns():
    out = {}
    for model in MODELS:
        cols = [c.name for c in model.__table__.columns if isinstance(c.type, sa.Numeric)]
        out[model.__tablename__] = sorted(cols)
    return out


def test_money_columns_are_exact_numeric():
    for model in MODELS:
        for col in model.__table__.columns:
            if isinstance(col.type, sa.Numeric):
                assert not isinstance(col.type, sa.Float), f"{model.__tablename__}.{col.name} is still Float"
                assert (col.type.precision, col.type.scale) == (18, 8)
                assert col.type.asdecimal is False


def test_no_float_columns_left_in_money_tables():
    for model in MODELS:
        floats = [c.name for c in model.__table__.columns if isinstance(c.type, sa.Float)]
        assert floats == [], f"{model.__tablename__} still has Float columns: {floats}"


def test_migration_covers_exactly_the_model_money_columns():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0002_money_numeric.py"
    spec = importlib.util.spec_from_file_location("money_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {t: sorted(c) for t, c in module.SPEC.items()} == _money_columns()


@pytest.mark.asyncio
async def test_numeric_roundtrip_returns_float(db_session):
    db_session.add(Position(market_id="mm", token_id="tt", outcome="Yes", size=round(0.1 + 0.2, 8), avg_price=0.123456789))
    await db_session.commit()
    row = (await db_session.execute(sa.select(Position))).scalar_one()
    assert isinstance(row.size, float)
    assert row.size == pytest.approx(0.3, abs=1e-8)
