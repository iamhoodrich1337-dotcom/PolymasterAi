"""money columns: DOUBLE PRECISION -> NUMERIC(18, 8)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-28

Converts prices, share counts, fees and PnL to exact decimals in PostgreSQL. Existing rows are kept (values are
rounded to 8 decimals). Runs in one transaction: either every column is converted or none. Safe to run twice
(columns that are already NUMERIC are skipped). Other databases (SQLite in tests) are not touched.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

PRECISION, SCALE = 18, 8
SPEC: dict[str, list[str]] = {
    "positions": ["size", "avg_price", "realized_pnl", "fees_paid"],
    "paper_orders": ["price", "size", "filled_size", "avg_fill_price", "fee", "slippage"],
    "paper_fills": ["price", "size", "fee"],
    "trades": ["price", "size", "fee", "realized_pnl"],
    "portfolio_snapshots": ["cash", "positions_value", "total_equity", "realized_pnl", "unrealized_pnl", "drawdown"],
}


def _convert(target: sa.types.TypeEngine, using_type: str, only_float: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    for table, columns in SPEC.items():
        if not insp.has_table(table):
            continue
        existing = {c["name"]: c["type"] for c in insp.get_columns(table)}
        for col in columns:
            current = existing.get(col)
            if current is None:
                continue
            is_float = isinstance(current, sa.Float)
            if only_float and not is_float:
                continue
            if not only_float and is_float:
                continue
            op.alter_column(table, col, type_=target, existing_type=current, postgresql_using=f'"{col}"::{using_type}')


def upgrade() -> None:
    _convert(sa.Numeric(PRECISION, SCALE), f"numeric({PRECISION},{SCALE})", only_float=True)


def downgrade() -> None:
    _convert(sa.Float(), "double precision", only_float=False)
