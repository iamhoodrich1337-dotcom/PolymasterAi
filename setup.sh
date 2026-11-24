#!/usr/bin/env bash
set -e

# ---- Структура папок ----
mkdir -p app/{api,core,database,models,schemas,services,strategies,market_data,probability,risk,paper_trading,backtesting,portfolio,telegram,dashboard/templates,monitoring}
mkdir -p tests scripts migrations/versions

# ---- Пустые __init__.py ----
for d in app app/api app/core app/database app/schemas app/market_data app/probability app/strategies app/risk app/paper_trading app/backtesting app/portfolio app/telegram app/dashboard app/monitoring app/services tests; do
  touch "$d/__init__.py"
done

# ---- Корневые файлы ----
cat > requirements.txt <<'END'
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
httpx==0.28.1
websockets==14.1
apscheduler==3.11.0
python-telegram-bot==21.10
pydantic==2.10.4
pydantic-settings==2.7.0
python-dotenv==1.0.1
jinja2==3.1.5
pytest==8.3.4
pytest-asyncio==0.25.2
aiosqlite==0.20.0
END

cat > .env.example <<'END'
APP_NAME=POLYMASTER AI
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=change-me-to-a-long-random-string
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
TELEGRAM_BOT_TOKEN=
TELEGRAM_OWNER_ID=
POLYMARKET_GAMMA_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_URL=https://clob.polymarket.com
POLYMARKET_DATA_URL=https://data-api.polymarket.com
POLYMARKET_WS_MARKET_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market
LIVE_TRADING_ENABLED=false
INITIAL_CAPITAL=100
RESERVE=50
TRADING_BUDGET=25
EXECUTION_RESERVE=15
UNTOUCHABLE_RESERVE=10
MAX_POSITION_SIZE=5
MAX_LOSS_PER_TRADE=1
MAX_MARKET_EXPOSURE=5
MAX_TOTAL_EXPOSURE=25
MAX_CORRELATED_EXPOSURE=10
DAILY_STOP_LOSS=3
WEEKLY_STOP_LOSS=7
MAX_DRAWDOWN=10
MIN_LIQUIDITY=1000
MAX_SPREAD=0.10
MIN_DEPTH_USD=500
STALE_DATA_SECONDS=120
PAPER_SLIPPAGE_BPS=50
PAPER_FEE_BPS=0
SCAN_INTERVAL_SECONDS=120
SNAPSHOT_INTERVAL_SECONDS=300
END

cat > .gitignore <<'END'
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
*.db
*.sqlite3
kill_switch.json
.pytest_cache/
.mypy_cache/
.ruff_cache/
.DS_Store
END

cat > Dockerfile <<'END'
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
END

cat > railway.toml <<'END'
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
END

cat > Procfile <<'END'
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
END

# ---- Config ----
cat > app/config.py <<'END'
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "POLYMASTER AI"
    app_env: str = "production"
    log_level: str = "INFO"
    secret_key: str = "change-me"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/polymaster"
    telegram_bot_token: str = ""
    telegram_owner_id: int = 0
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_url: str = "https://clob.polymarket.com"
    polymarket_data_url: str = "https://data-api.polymarket.com"
    polymarket_ws_market_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    live_trading_enabled: bool = False
    polymarket_private_key: str = ""
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_api_passphrase: str = ""
    initial_capital: float = 100.0
    reserve: float = 50.0
    trading_budget: float = 25.0
    execution_reserve: float = 15.0
    untouchable_reserve: float = 10.0
    max_position_size: float = 5.0
    max_loss_per_trade: float = 1.0
    max_market_exposure: float = 5.0
    max_total_exposure: float = 25.0
    max_correlated_exposure: float = 10.0
    daily_stop_loss: float = 3.0
    weekly_stop_loss: float = 7.0
    max_drawdown: float = 10.0
    min_liquidity: float = 1000.0
    max_spread: float = 0.10
    min_depth_usd: float = 500.0
    stale_data_seconds: int = 120
    paper_slippage_bps: float = 50.0
    paper_fee_bps: float = 0.0
    scan_interval_seconds: int = 120
    snapshot_interval_seconds: int = 300

    @property
    def live_mode_locked(self) -> bool:
        return not self.live_trading_enabled

@lru_cache
def get_settings() -> Settings:
    return Settings()
END

# ---- Core ----
cat > app/core/logging.py <<'END'
import logging
import sys
from app.config import get_settings

def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter('{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}')
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
END

cat > app/core/exceptions.py <<'END'
class PolymasterError(Exception): pass
class DataUnavailableError(PolymasterError): pass
class RiskLimitExceeded(PolymasterError): pass
class LiveModeLocked(PolymasterError): pass
class InsufficientLiquidity(PolymasterError): pass
END

cat > app/core/utils.py <<'END'
import json
from datetime import datetime, timezone
from typing import Any

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def safe_json_loads(value: Any, default: Any = None) -> Any:
    if value is None: return default
    if isinstance(value, (dict, list)): return value
    if isinstance(value, str):
        try: return json.loads(value)
        except (json.JSONDecodeError, TypeError): return default
    return default

def parse_float(value: Any, default: float = 0.0) -> float:
    try: return float(value)
    except (TypeError, ValueError): return default

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
END

cat > app/core/security.py <<'END'
import hashlib, hmac
from datetime import datetime, timedelta, timezone
from app.config import get_settings

def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

def create_access_token(subject: str, expires_minutes: int = 60) -> str:
    settings = get_settings()
    expire = int((datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).timestamp())
    message = f"{subject}.{expire}"
    sig = hmac.new(settings.secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{message}.{sig}"

def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        subject, expire_str, sig = token.rsplit(".", 2)
        if datetime.now(timezone.utc).timestamp() > int(expire_str): return None
        expected = hmac.new(settings.secret_key.encode(), f"{subject}.{expire_str}".encode(), hashlib.sha256).hexdigest()
        return subject if hmac.compare_digest(sig, expected) else None
    except (ValueError, AttributeError): return None
END

# ---- Database ----
cat > app/database/base.py <<'END'
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase): pass
END

cat > app/database/session.py <<'END'
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try: yield session
        finally: await session.close()
END

cat > app/database/init_db.py <<'END'
from app.database.base import Base
from app.database.session import engine

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
END

# ---- Models ----
cat > app/models/__init__.py <<'END'
from app.models.user import User
from app.models.setting import Setting
from app.models.market import Market
from app.models.market_snapshot import MarketSnapshot
from app.models.order_book import OrderBook
from app.models.signal import Signal
from app.models.strategy import Strategy
from app.models.strategy_metric import StrategyMetric
from app.models.wallet import Wallet
from app.models.wallet_trade import WalletTrade
from app.models.paper_order import PaperOrder
from app.models.paper_fill import PaperFill
from app.models.position import Position
from app.models.trade import Trade
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.risk_event import RiskEvent
from app.models.system_event import SystemEvent
from app.models.backtest_run import BacktestRun
from app.models.backtest_trade import BacktestTrade
from app.models.news_event import NewsEvent
from app.models.data_source import DataSource

__all__ = ["User","Setting","Market","MarketSnapshot","OrderBook","Signal","Strategy","StrategyMetric","Wallet","WalletTrade","PaperOrder","PaperFill","Position","Trade","PortfolioSnapshot","RiskEvent","SystemEvent","BacktestRun","BacktestTrade","NewsEvent","DataSource"]
END

cat > app/models/user.py <<'END'
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/setting.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
END

cat > app/models/market.py <<'END'
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Market(Base):
    __tablename__ = "markets"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    condition_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    clob_token_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    neg_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    volume_24hr: Mapped[float] = mapped_column(Float, default=0.0)
    spread: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
END

cat > app/models/market_snapshot.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    best_bid: Mapped[float] = mapped_column(Float, default=0.0)
    best_ask: Mapped[float] = mapped_column(Float, default=0.0)
    midpoint: Mapped[float] = mapped_column(Float, default=0.0)
    spread: Mapped[float] = mapped_column(Float, default=1.0)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    volume_24hr: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(64), default="clob")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
END

cat > app/models/order_book.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class OrderBook(Base):
    __tablename__ = "order_books"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(128), index=True)
    bids_json: Mapped[str] = mapped_column(Text)
    asks_json: Mapped[str] = mapped_column(Text)
    tick_size: Mapped[float] = mapped_column(Float, default=0.01)
    min_order_size: Mapped[float] = mapped_column(Float, default=5.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
END

cat > app/models/signal.py <<'END'
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(32))
    market_probability: Mapped[float] = mapped_column(Float)
    estimated_probability: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    reason: Mapped[str] = mapped_column(Text, default="")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
END

cat > app/models/strategy.py <<'END'
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Strategy(Base):
    __tablename__ = "strategies"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
END

cat > app/models/strategy_metric.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class StrategyMetric(Base):
    __tablename__ = "strategy_metrics"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(ForeignKey("strategies.name"), index=True)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    accepted_signals: Mapped[int] = mapped_column(Integer, default=0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
END

cat > app/models/wallet.py <<'END'
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Wallet(Base):
    __tablename__ = "wallets"
    address: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    avg_position_size: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/wallet_trade.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class WalletTrade(Base):
    __tablename__ = "wallet_trades"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(ForeignKey("wallets.address"), index=True)
    market_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    side: Mapped[str] = mapped_column(String(8))
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
END

cat > app/models/paper_order.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    filled_size: Mapped[float] = mapped_column(Float, default=0.0)
    avg_fill_price: Mapped[float] = mapped_column(Float, default=0.0)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/paper_fill.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class PaperFill(Base):
    __tablename__ = "paper_fills"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/position.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("market_id", "token_id", name="uq_position_market_token"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(128), index=True)
    outcome: Mapped[str] = mapped_column(String(32))
    size: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    fees_paid: Mapped[float] = mapped_column(Float, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
END

cat > app/models/trade.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(128))
    side: Mapped[str] = mapped_column(String(8))
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/portfolio_snapshot.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    positions_value: Mapped[float] = mapped_column(Float, default=0.0)
    total_equity: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
END

cat > app/models/risk_event.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    market_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
END

cat > app/models/system_event.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    component: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
END

cat > app/models/backtest_run.py <<'END'
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_capital: Mapped[float] = mapped_column(Float, default=100.0)
    final_capital: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    out_of_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/backtest_trade.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    market_id: Mapped[str] = mapped_column(String(128))
    side: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float, default=0.0)
    size: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
END

cat > app/models/news_event.py <<'END'
from datetime import datetime
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class NewsEvent(Base):
    __tablename__ = "news_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    headline: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[float] = mapped_column(Float, default=0.0)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
END

cat > app/models/data_source.py <<'END'
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.utils import utc_now
from app.database.base import Base

class DataSource(Base):
    __tablename__ = "data_sources"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(255))
    requires_key: Mapped[bool] = mapped_column(Boolean, default=False)
    healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
END

echo "✅ ЧАСТЬ 1 готова. Файлов создано: $(find . -name '*.py' -o -name '*.txt' -o -name '*.toml' | wc -l)"#!/usr/bin/env bash
set -e

# ---- Market Data ----
cat > app/market_data/gamma_client.py <<'END'
from typing import Any
import httpx
from app.config import get_settings
from app.core.exceptions import DataUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

class GammaClient:
    def __init__(self) -> None:
        self.base_url = get_settings().polymarket_gamma_url
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Gamma API request failed: %s %s", path, exc)
            raise DataUnavailableError(f"Gamma API unavailable: {exc}") from exc

    async def list_markets(self, active: bool = True, closed: bool = False, limit: int = 100, offset: int = 0, order: str = "volume_24hr", ascending: bool = False) -> list[dict[str, Any]]:
        params = {"active": str(active).lower(), "closed": str(closed).lower(), "limit": limit, "offset": offset, "order": order, "ascending": str(ascending).lower()}
        data = await self._get("/markets", params)
        return data if isinstance(data, list) else []

    async def get_market(self, market_id: str) -> dict[str, Any] | None:
        data = await self._get(f"/markets/{market_id}")
        return data if isinstance(data, dict) else None
END

cat > app/market_data/clob_client.py <<'END'
from typing import Any
import httpx
from app.config import get_settings
from app.core.exceptions import DataUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

class ClobClient:
    def __init__(self) -> None:
        self.base_url = get_settings().polymarket_clob_url
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("CLOB request failed: %s %s", path, exc)
            raise DataUnavailableError(f"CLOB unavailable: {exc}") from exc

    async def get_order_book(self, token_id: str) -> dict[str, Any]:
        data = await self._get("/book", {"token_id": token_id})
        if not isinstance(data, dict):
            raise DataUnavailableError("Invalid order book response")
        return data

    async def get_price(self, token_id: str, side: str = "BUY") -> float:
        data = await self._get("/price", {"token_id": token_id, "side": side})
        return float(data.get("price", 0.0))

    async def get_midpoint(self, token_id: str) -> float:
        data = await self._get("/midpoint", {"token_id": token_id})
        return float(data.get("mid", 0.0))

    async def get_price_history(self, condition_id: str, interval: str = "1w", fidelity: int = 100) -> list[dict[str, Any]]:
        data = await self._get("/prices-history", {"market": condition_id, "interval": interval, "fidelity": fidelity})
        if isinstance(data, dict):
            return data.get("history", [])
        return []

    async def get_full_price_history(self, token_id: str, interval: str = "max", fidelity: int = 60) -> list[dict[str, Any]]:
        data = await self._get("/prices-history", {"market": token_id, "interval": interval, "fidelity": fidelity})
        if isinstance(data, dict):
            return data.get("history", [])
        return []
END

cat > app/market_data/data_client.py <<'END'
from typing import Any
import httpx
from app.config import get_settings
from app.core.exceptions import DataUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

class DataApiClient:
    def __init__(self) -> None:
        self.base_url = f"{get_settings().polymarket_data_url}/v2"
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Data API request failed: %s %s", path, exc)
            raise DataUnavailableError(f"Data API unavailable: {exc}") from exc

    async def get_positions(self, user: str, limit: int = 50) -> list[dict[str, Any]]:
        data = await self._get("/positions", {"user": user, "limit": limit})
        return data.get("data", []) or []

    async def get_activity(self, user: str, limit: int = 50) -> list[dict[str, Any]]:
        data = await self._get("/activity", {"user": user, "limit": limit})
        return data.get("data", []) or []
END

cat > app/market_data/websocket_manager.py <<'END'
import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
import websockets
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]

class MarketWebSocket:
    def __init__(self, asset_ids: list[str], on_message: MessageHandler) -> None:
        self.url = get_settings().polymarket_ws_market_url
        self.asset_ids = asset_ids
        self.on_message = on_message
        self._stop = asyncio.Event()
        self._ws: Any = None

    async def stop(self) -> None:
        self._stop.set()
        if self._ws:
            await self._ws.close()

    async def run(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws = ws
                    backoff = 1
                    await ws.send(json.dumps({"assets_ids": self.asset_ids, "type": "market"}))
                    logger.info("WebSocket connected; subscribed to %d assets", len(self.asset_ids))
                    async for raw in ws:
                        if raw == "PONG":
                            continue
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self.on_message(payload)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("WebSocket error: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
END

cat > app/market_data/scanner.py <<'END'
from typing import Any
from app.config import get_settings
from app.core.logging import get_logger
from app.core.utils import parse_float, safe_json_loads
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient

logger = get_logger(__name__)

class MarketScanner:
    def __init__(self, gamma: GammaClient, clob: ClobClient) -> None:
        self.gamma = gamma
        self.clob = clob
        self.settings = get_settings()

    async def scan(self, limit: int = 100) -> list[dict[str, Any]]:
        raw_markets = await self.gamma.list_markets(active=True, closed=False, limit=limit)
        results: list[dict[str, Any]] = []
        for m in raw_markets:
            if not isinstance(m, dict):
                continue
            market_id = str(m.get("id", ""))
            condition_id = m.get("conditionId") or m.get("condition_id") or ""
            if not market_id or not condition_id:
                continue
            liquidity = parse_float(m.get("liquidity"), 0.0)
            if liquidity < self.settings.min_liquidity:
                continue
            token_ids = safe_json_loads(m.get("clobTokenIds") or m.get("clob_token_ids"), [])
            outcomes = safe_json_loads(m.get("outcomes"), [])
            if not isinstance(token_ids, list) or len(token_ids) < 2:
                continue
            best_bid = 0.0
            best_ask = 0.0
            spread = 1.0
            try:
                book = await self.clob.get_order_book(token_ids[0])
                bids = book.get("bids") or []
                asks = book.get("asks") or []
                if bids and asks:
                    best_bid = max(parse_float(b[0], 0.0) for b in bids if isinstance(b, (list, tuple)))
                    best_ask = min(parse_float(a[0], 1.0) for a in asks if isinstance(a, (list, tuple)))
                    spread = max(0.0, best_ask - best_bid)
            except Exception as exc:
                logger.debug("Order book unavailable for %s: %s", market_id, exc)
            if spread > self.settings.max_spread:
                continue
            results.append({
                "id": market_id, "condition_id": condition_id,
                "question": m.get("question") or m.get("title") or "",
                "slug": m.get("slug"), "category": m.get("category"),
                "outcomes": outcomes, "clob_token_ids": token_ids,
                "liquidity": liquidity, "volume": parse_float(m.get("volume"), 0.0),
                "volume_24hr": parse_float(m.get("volume24hr"), 0.0),
                "best_bid": best_bid, "best_ask": best_ask, "spread": spread,
                "neg_risk": bool(m.get("negRisk", False)), "end_date": m.get("endDate"),
                "active": bool(m.get("active", True)), "closed": bool(m.get("closed", False)),
            })
        logger.info("Scanner returned %d tradable markets", len(results))
        return results
END

cat > app/market_data/cache.py <<'END'
import time
from typing import Any

class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
    def get(self, key: str, ttl: float) -> Any | None:
        entry = self._store.get(key)
        if not entry: return None
        ts, value = entry
        if time.monotonic() - ts > ttl:
            self._store.pop(key, None)
            return None
        return value
    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

market_cache = TTLCache()
END

# ---- Probability ----
cat > app/probability/engine.py <<'END'
from dataclasses import dataclass, field
from app.core.utils import clamp

@dataclass
class ProbabilityEstimate:
    probability: float
    confidence: float
    sources: list[str] = field(default_factory=list)
    reasoning: str = ""

class ProbabilityEngine:
    def estimate(self, market_probability: float, external_signals: list[tuple[float, float, str]], min_confidence: float = 0.3) -> ProbabilityEstimate:
        valid = [(p, c, s) for p, c, s in external_signals if 0.0 <= p <= 1.0 and c > 0.0]
        if not valid:
            return ProbabilityEstimate(probability=market_probability, confidence=0.0, sources=[], reasoning="No external signals; market probability used as prior.")
        total_weight = sum(c for _, c, _ in valid)
        weighted = sum(p * c for p, c, _ in valid) / total_weight
        agreement = 1.0 - (max(p for p, _, _ in valid) - min(p for p, _, _ in valid))
        source_quality = min(total_weight / len(valid), 1.0)
        confidence = clamp(agreement * source_quality, 0.0, 1.0)
        final = market_probability + (weighted - market_probability) * confidence
        return ProbabilityEstimate(probability=clamp(final, 0.01, 0.99), confidence=confidence if confidence >= min_confidence else 0.0, sources=[s for _, _, s in valid], reasoning=f"weighted={weighted:.4f}, agreement={agreement:.4f}, quality={source_quality:.4f}")
END

cat > app/probability/sources.py <<'END'
from dataclasses import dataclass
from typing import Protocol

@dataclass
class SourceSignal:
    probability: float
    confidence: float
    source: str
    raw: dict | None = None

class ProbabilitySource(Protocol):
    name: str
    async def get_signal(self, market: dict) -> SourceSignal | None: ...
END

# ---- Strategies ----
cat > app/strategies/base.py <<'END'
from abc import ABC, abstractmethod
from dataclasses import dataclass
from app.probability.engine import ProbabilityEngine

@dataclass
class StrategySignal:
    strategy: str
    market_id: str
    outcome: str
    token_id: str
    market_probability: float
    estimated_probability: float
    edge: float
    confidence: float
    sources: list[str]
    reason: str
    rejection_reason: str | None = None

class BaseStrategy(ABC):
    name: str = "base"
    display_name: str = "Base"
    description: str = ""
    def __init__(self, probability_engine: ProbabilityEngine | None = None) -> None:
        self.probability_engine = probability_engine or ProbabilityEngine()
    @abstractmethod
    async def evaluate(self, market: dict) -> StrategySignal | None: ...
END

cat > app/strategies/weather.py <<'END'
from typing import Any
import httpx
from app.core.logging import get_logger
from app.strategies.base import BaseStrategy, StrategySignal

logger = get_logger(__name__)

class WeatherStrategy(BaseStrategy):
    name = "weather"
    display_name = "Weather Trading"
    description = "Evaluates weather markets against a configured forecast adapter."
    def __init__(self, forecast_provider_url: str = "", api_key: str = "") -> None:
        super().__init__()
        self.forecast_provider_url = forecast_provider_url
        self.api_key = api_key
    async def evaluate(self, market: dict) -> StrategySignal | None:
        question = (market.get("question") or "").lower()
        if not any(k in question for k in ("temperature", "rain", "snow", "weather", "precipitation")):
            return None
        if not self.forecast_provider_url:
            logger.info("Weather strategy skipped: forecast provider not configured")
            return None
        forecast = await self._fetch_forecast(market)
        if forecast is None:
            return None
        prob = float(forecast["probability"])
        conf = float(forecast["confidence"])
        source = str(forecast.get("source", "weather_provider"))
        estimate = self.probability_engine.estimate(market_probability=float(market.get("best_ask", 0.5)), external_signals=[(prob, conf, source)])
        if estimate.confidence <= 0.0:
            return None
        market_prob = float(market.get("best_ask", 0.5))
        edge = estimate.probability - market_prob
        if abs(edge) < 0.03:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="Yes", token_id=market["clob_token_ids"][0], market_probability=market_prob, estimated_probability=estimate.probability, edge=edge, confidence=estimate.confidence, sources=estimate.sources, reason=f"Forecast edge {edge:+.4f} with confidence {estimate.confidence:.2f}")
    async def _fetch_forecast(self, market: dict) -> dict[str, Any] | None:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.forecast_provider_url, params={"market": market.get("slug") or market["id"]}, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict) or "probability" not in payload:
                    return None
                return payload
        except Exception as exc:
            logger.warning("Weather forecast unavailable: %s", exc)
            return None
END

cat > app/strategies/sports.py <<'END'
from typing import Any
import httpx
from app.core.logging import get_logger
from app.strategies.base import BaseStrategy, StrategySignal

logger = get_logger(__name__)

class SportsStrategy(BaseStrategy):
    name = "sports"
    display_name = "Sports Trading"
    description = "Evaluates sports markets against a configured odds adapter."
    def __init__(self, odds_provider_url: str = "", api_key: str = "") -> None:
        super().__init__()
        self.odds_provider_url = odds_provider_url
        self.api_key = api_key
    async def evaluate(self, market: dict) -> StrategySignal | None:
        question = (market.get("question") or "").lower()
        if not any(k in question for k in ("win", "match", "game", "vs", "beat")):
            return None
        if not self.odds_provider_url:
            logger.info("Sports strategy skipped: odds provider not configured")
            return None
        odds = await self._fetch_odds(market)
        if odds is None:
            return None
        prob = float(odds["probability"])
        conf = float(odds["confidence"])
        source = str(odds.get("source", "sports_odds_provider"))
        market_prob = float(market.get("best_ask", 0.5))
        estimate = self.probability_engine.estimate(market_probability=market_prob, external_signals=[(prob, conf, source)])
        if estimate.confidence <= 0.0:
            return None
        edge = estimate.probability - market_prob
        if abs(edge) < 0.03:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="Yes", token_id=market["clob_token_ids"][0], market_probability=market_prob, estimated_probability=estimate.probability, edge=edge, confidence=estimate.confidence, sources=estimate.sources, reason=f"Sports edge {edge:+.4f} with confidence {estimate.confidence:.2f}")
    async def _fetch_odds(self, market: dict) -> dict[str, Any] | None:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.odds_provider_url, params={"market": market.get("slug") or market["id"]}, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict) or "probability" not in payload:
                    return None
                return payload
        except Exception as exc:
            logger.warning("Sports odds unavailable: %s", exc)
            return None
END

cat > app/strategies/arbitrage.py <<'END'
from app.strategies.base import BaseStrategy, StrategySignal

class ArbitrageResearchStrategy(BaseStrategy):
    name = "arbitrage"
    display_name = "Arbitrage Research"
    description = "Detects discrepancies; never calls them guaranteed arbitrage."
    async def evaluate(self, market: dict) -> StrategySignal | None:
        token_ids = market.get("clob_token_ids") or []
        if len(token_ids) < 2:
            return None
        yes_ask = float(market.get("best_ask", 0.5))
        no_ask = 1.0 - float(market.get("best_bid", 0.5))
        total = yes_ask + no_ask
        edge = 1.0 - total
        cost_buffer = float(market.get("spread", 0.0)) + 0.02
        if edge <= cost_buffer:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="YES+NO", token_id=token_ids[0], market_probability=total, estimated_probability=1.0, edge=edge, confidence=0.25, sources=["clob_order_book"], reason=f"Binary sum {total:.4f}; theoretical edge {edge:.4f} before execution risk", rejection_reason="Arbitrage research signals are not auto-executed in paper mode")
END

cat > app/strategies/wallet_intelligence.py <<'END'
from datetime import datetime, timedelta, timezone
from app.core.logging import get_logger
from app.market_data.data_client import DataApiClient
from app.strategies.base import BaseStrategy, StrategySignal

logger = get_logger(__name__)

class WalletIntelligenceStrategy(BaseStrategy):
    name = "wallet_intelligence"
    display_name = "Wallet Intelligence"
    description = "Scores public wallets and flags potentially informed activity."
    def __init__(self, data_client: DataApiClient) -> None:
        super().__init__()
        self.data_client = data_client
    async def evaluate(self, market: dict) -> StrategySignal | None:
        return None
    async def score_wallet(self, address: str) -> dict:
        try:
            activity = await self.data_client.get_activity(address, limit=200)
        except Exception as exc:
            logger.warning("Wallet activity unavailable for %s: %s", address, exc)
            return {"address": address, "score": 0.0, "suspicious": False, "error": str(exc)}
        if not activity:
            return {"address": address, "score": 0.0, "suspicious": False, "trades": 0}
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent = [a for a in activity if str(a.get("timestamp", "")) >= cutoff.isoformat()]
        sizes = [float(a.get("size", 0)) for a in recent if float(a.get("size", 0)) > 0]
        avg_size = sum(sizes) / len(sizes) if sizes else 0.0
        suspicious = avg_size > 10_000 or len(recent) > 150
        score = min(len(recent) / 100.0, 1.0) * (0.5 if suspicious else 1.0)
        return {"address": address, "score": round(score, 4), "suspicious": suspicious, "trades": len(recent), "avg_size": round(avg_size, 2)}
END

cat > app/strategies/market_making.py <<'END'
from app.strategies.base import BaseStrategy, StrategySignal

class MarketMakingResearchStrategy(BaseStrategy):
    name = "market_making"
    display_name = "Market Making Research"
    description = "Estimates spread capture opportunities and inventory risk."
    async def evaluate(self, market: dict) -> StrategySignal | None:
        spread = float(market.get("spread", 1.0))
        liquidity = float(market.get("liquidity", 0.0))
        if spread < 0.02 or liquidity < 5000:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="MM_RESEARCH", token_id=market["clob_token_ids"][0], market_probability=float(market.get("best_ask", 0.5)), estimated_probability=float(market.get("best_bid", 0.5)), edge=spread / 2, confidence=0.2, sources=["clob_order_book"], reason=f"Wide spread {spread:.4f} on liquid market; research candidate only", rejection_reason="Market making research is not executed in paper mode")
END

cat > app/strategies/latency_monitor.py <<'END'
from datetime import datetime, timezone
from app.strategies.base import BaseStrategy, StrategySignal

class LatencyMonitorStrategy(BaseStrategy):
    name = "latency_monitor"
    display_name = "Latency & Price Monitor"
    description = "Flags stale quotes; does not claim latency arbitrage without measurement."
    async def evaluate(self, market: dict) -> StrategySignal | None:
        updated = market.get("updated_at")
        if not updated:
            return None
        try:
            ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        except ValueError:
            return None
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age < 300:
            return None
        return StrategySignal(strategy=self.name, market_id=market["id"], outcome="STALE_DATA", token_id=market["clob_token_ids"][0], market_probability=float(market.get("best_ask", 0.5)), estimated_probability=float(market.get("best_ask", 0.5)), edge=0.0, confidence=0.0, sources=["market_snapshot"], reason=f"Quote is {age:.0f}s old", rejection_reason="Stale data; no trade permitted")
END

# ---- Risk ----
cat > app/risk/limits.py <<'END'
from dataclasses import dataclass
from app.config import get_settings

@dataclass
class RiskLimits:
    max_position_size: float
    max_loss_per_trade: float
    max_market_exposure: float
    max_total_exposure: float
    max_correlated_exposure: float
    daily_stop_loss: float
    weekly_stop_loss: float
    max_drawdown: float

def load_limits() -> RiskLimits:
    s = get_settings()
    return RiskLimits(max_position_size=s.max_position_size, max_loss_per_trade=s.max_loss_per_trade, max_market_exposure=s.max_market_exposure, max_total_exposure=s.max_total_exposure, max_correlated_exposure=s.max_correlated_exposure, daily_stop_loss=s.daily_stop_loss, weekly_stop_loss=s.weekly_stop_loss, max_drawdown=s.max_drawdown)
END

cat > app/risk/kill_switch.py <<'END'
import json
from pathlib import Path
from app.core.logging import get_logger

logger = get_logger(__name__)
KILL_SWITCH_FILE = Path("kill_switch.json")

class KillSwitch:
    def __init__(self) -> None:
        self._engaged = False
        self._reason = ""
        self._load()
    def _load(self) -> None:
        if KILL_SWITCH_FILE.exists():
            try:
                data = json.loads(KILL_SWITCH_FILE.read_text())
                self._engaged = bool(data.get("engaged", False))
                self._reason = str(data.get("reason", ""))
            except Exception:
                logger.exception("Failed to load kill switch state")
    def _persist(self) -> None:
        KILL_SWITCH_FILE.write_text(json.dumps({"engaged": self._engaged, "reason": self._reason}))
    @property
    def engaged(self) -> bool:
        return self._engaged
    @property
    def reason(self) -> str:
        return self._reason
    def engage(self, reason: str) -> None:
        self._engaged = True
        self._reason = reason
        self._persist()
        logger.critical("Kill switch engaged: %s", reason)
    def disengage(self, reason: str = "manual reset") -> None:
        self._engaged = False
        self._reason = reason
        self._persist()
        logger.warning("Kill switch disengaged: %s", reason)
END

cat > app/risk/manager.py <<'END'
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
END

# ---- Paper Trading ----
cat > app/paper_trading/simulator.py <<'END'
from dataclasses import dataclass
from app.core.exceptions import InsufficientLiquidity

@dataclass
class FillResult:
    filled_size: float
    avg_price: float
    fee: float
    slippage: float
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
END

cat > app/paper_trading/engine.py <<'END'
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.core.utils import safe_json_loads
from app.market_data.clob_client import ClobClient
from app.models.market import Market
from app.models.paper_fill import PaperFill
from app.models.paper_order import PaperOrder
from app.models.position import Position
from app.models.trade import Trade
from app.paper_trading.simulator import PaperSimulator
from app.risk.manager import RiskManager

logger = get_logger(__name__)

class PaperTradingEngine:
    def __init__(self, clob: ClobClient, risk: RiskManager, slippage_bps: float = 50.0, fee_bps: float = 0.0) -> None:
        self.clob = clob
        self.risk = risk
        self.simulator = PaperSimulator(slippage_bps=slippage_bps, fee_bps=fee_bps)

    async def execute_signal(self, db: AsyncSession, signal_id: int, market_id: str, token_id: str, outcome: str, strategy: str, size_usd: float) -> PaperOrder | None:
        result = await db.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one_or_none()
        if not market:
            logger.warning("Market %s not found", market_id)
            return None
        book = await self.clob.get_order_book(token_id)
        asks = [[float(p), float(q)] for p, q in (book.get("asks") or [])]
        if not asks:
            logger.info("No asks for %s; signal skipped", token_id)
            return None
        best_ask = asks[0][0]
        first_token = safe_json_loads(market.clob_token_ids, [""])[0]
        is_full_loss = outcome.lower() in ("yes", "no") and token_id == first_token
        decision = await self.risk.check_trade(db=db, market_id=market_id, token_id=token_id, intended_size_usd=size_usd, entry_price=best_ask, is_full_loss=is_full_loss)
        if not decision.allowed:
            logger.info("Risk blocked signal %s: %s", signal_id, decision.reason)
            return None
        size_usd = decision.adjusted_size
        try:
            fill = self.simulator.simulate_buy(asks, size_usd)
        except Exception as exc:
            logger.warning("Simulation failed for %s: %s", token_id, exc)
            return None
        order = PaperOrder(signal_id=signal_id, market_id=market_id, token_id=token_id, outcome=outcome, side="BUY", price=best_ask, size=size_usd / best_ask, filled_size=fill.filled_size, avg_fill_price=fill.avg_price, fee=fill.fee, slippage=fill.slippage, status="PARTIAL" if fill.partial else "FILLED", reason="paper simulation")
        db.add(order)
        await db.flush()
        db.add(PaperFill(order_id=order.id, price=fill.avg_price, size=fill.filled_size, fee=fill.fee))
        pos_result = await db.execute(select(Position).where(Position.market_id == market_id, Position.token_id == token_id))
        position = pos_result.scalar_one_or_none()
        if position:
            total_size = position.size + fill.filled_size
            position.avg_price = ((position.avg_price * position.size) + (fill.avg_price * fill.filled_size)) / total_size
            position.size = total_size
            position.fees_paid += fill.fee
        else:
            position = Position(market_id=market_id, token_id=token_id, outcome=outcome, size=fill.filled_size, avg_price=fill.avg_price, fees_paid=fill.fee)
            db.add(position)
            await db.flush()
        db.add(Trade(position_id=position.id, market_id=market_id, token_id=token_id, side="BUY", price=fill.avg_price, size=fill.filled_size, fee=fill.fee, realized_pnl=0.0, strategy=strategy))
        await db.commit()
        logger.info("Paper order %s filled: %.4f @ %.4f", order.id, fill.filled_size, fill.avg_price)
        return order
END

cat > app/paper_trading/realism.py <<'END'
from dataclasses import dataclass

@dataclass
class RealismReport:
    score: float
    warnings: list[str]

def assess_realism(partial_fill_rate: float, avg_slippage_bps: float, rejected_by_depth: int, total_signals: int) -> RealismReport:
    warnings: list[str] = []
    score = 1.0
    if partial_fill_rate > 0.3:
        warnings.append("High partial-fill rate; paper results may overstate capacity")
        score -= 0.2
    if avg_slippage_bps > 100:
        warnings.append("Slippage assumption is aggressive")
        score -= 0.2
    if total_signals > 0 and rejected_by_depth / total_signals > 0.2:
        warnings.append("Many signals rejected due to insufficient depth")
        score -= 0.2
    return RealismReport(score=max(0.0, round(score, 2)), warnings=warnings)
END

# ---- Backtesting ----
cat > app/backtesting/metrics.py <<'END'
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
END

cat > app/backtesting/engine.py <<'END'
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
END

cat > app/backtesting/historical_loader.py <<'END'
import json
from datetime import datetime, timezone
from app.core.logging import get_logger
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient

logger = get_logger(__name__)

class HistoricalDataLoader:
    def __init__(self, gamma: GammaClient, clob: ClobClient) -> None:
        self.gamma = gamma
        self.clob = clob

    async def load_closed_markets(self, closed_within_days: int = 365, limit: int = 100, min_volume: float = 1000.0) -> list[dict]:
        results: list[dict] = []
        offset = 0
        cutoff = datetime.now(timezone.utc).timestamp() - closed_within_days * 86400
        while len(results) < limit:
            batch = await self.gamma.list_markets(active=False, closed=True, limit=100, offset=offset)
            if not batch:
                break
            for m in batch:
                volume = float(m.get("volume") or 0)
                if volume < min_volume:
                    continue
                end_ts = m.get("endDateIso") or m.get("endDate")
                if end_ts:
                    try:
                        end_dt = datetime.fromisoformat(str(end_ts).replace("Z", "+00:00"))
                        if end_dt.timestamp() < cutoff:
                            continue
                    except ValueError:
                        pass
                token_ids = m.get("clobTokenIds")
                if isinstance(token_ids, str):
                    try:
                        token_ids = json.loads(token_ids)
                    except Exception:
                        continue
                if not isinstance(token_ids, list) or len(token_ids) < 1:
                    continue
                results.append({"id": str(m.get("id")), "condition_id": m.get("conditionId"), "question": m.get("question"), "token_ids": token_ids, "volume": volume, "end_date": end_ts})
                if len(results) >= limit:
                    break
            offset += 100
        logger.info("Loaded %d closed markets", len(results))
        return results

    async def load_price_history_for_market(self, market: dict, interval: str = "max", fidelity: int = 60) -> dict:
        histories: dict[str, list[dict]] = {}
        for token_id in market["token_ids"]:
            try:
                points = await self.clob.get_full_price_history(token_id, interval=interval, fidelity=fidelity)
                histories[token_id] = points
            except Exception as exc:
                logger.warning("Price history unavailable for token %s: %s", token_id, exc)
                histories[token_id] = []
        return histories
END

# ---- Portfolio ----
cat > app/schemas/portfolio.py <<'END'
from datetime import datetime
from pydantic import BaseModel

class PortfolioSummary(BaseModel):
    cash: float
    positions_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    drawdown: float
    open_positions: int
    timestamp: datetime
END

cat > app/portfolio/manager.py <<'END'
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.utils import utc_now
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.trade import Trade
from app.schemas.portfolio import PortfolioSummary

class PortfolioManager:
    def __init__(self, initial_capital: float) -> None:
        self.initial_capital = initial_capital

    async def snapshot(self, db: AsyncSession) -> PortfolioSummary:
        realized = await db.scalar(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0)))
        realized = float(realized or 0.0)
        positions_result = await db.execute(select(Position))
        positions = positions_result.scalars().all()
        positions_value = sum(float(p.size) * float(p.avg_price) for p in positions)
        unrealized = 0.0
        cash = self.initial_capital + realized - positions_value
        equity = cash + positions_value
        peak = max(self.initial_capital, equity)
        drawdown = max(0.0, peak - equity)
        snap = PortfolioSnapshot(cash=round(cash, 4), positions_value=round(positions_value, 4), total_equity=round(equity, 4), realized_pnl=round(realized, 4), unrealized_pnl=round(unrealized, 4), drawdown=round(drawdown, 4))
        db.add(snap)
        await db.commit()
        return PortfolioSummary(cash=round(cash, 4), positions_value=round(positions_value, 4), total_equity=round(equity, 4), realized_pnl=round(realized, 4), unrealized_pnl=round(unrealized, 4), drawdown=round(drawdown, 4), open_positions=len(positions), timestamp=utc_now())
END

echo "✅ ЧАСТЬ 2 готова. Всего .py файлов: $(find app -name '*.py' | wc -l)"#!/usr/bin/env bash
set -e

# ---- API ----
cat > app/api/health.py <<'END'
from fastapi import APIRouter
from sqlalchemy import text
from app.database.session import AsyncSessionLocal
from app.market_data.clob_client import ClobClient

router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> dict:
    db_ok = False
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    clob_ok = False
    client = ClobClient()
    try:
        await client.get_midpoint("0")
        clob_ok = True
    except Exception:
        pass
    finally:
        await client.close()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "polymarket_clob": clob_ok, "live_mode": "LOCKED"}
END

cat > app/api/markets.py <<'END'
from fastapi import APIRouter, Query
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient
from app.market_data.scanner import MarketScanner

router = APIRouter(prefix="/markets", tags=["markets"])

@router.get("")
async def list_markets(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    gamma = GammaClient(); clob = ClobClient()
    scanner = MarketScanner(gamma, clob)
    try:
        return await scanner.scan(limit=limit)
    finally:
        await gamma.close(); await clob.close()

@router.get("/{market_id}/book")
async def order_book(market_id: str, token_id: str) -> dict:
    clob = ClobClient()
    try:
        return await clob.get_order_book(token_id)
    finally:
        await clob.close()
END

cat > app/api/signals.py <<'END'
from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.models.signal import Signal

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("")
async def list_signals(limit: int = 100, db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(Signal).order_by(desc(Signal.created_at)).limit(limit))
    signals = result.scalars().all()
    return [{"id": s.id, "strategy": s.strategy, "market_id": s.market_id, "outcome": s.outcome, "market_probability": s.market_probability, "estimated_probability": s.estimated_probability, "edge": s.edge, "confidence": s.confidence, "accepted": s.accepted, "rejection_reason": s.rejection_reason, "created_at": s.created_at.isoformat()} for s in signals]
END

cat > app/api/portfolio.py <<'END'
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database.session import get_db
from app.portfolio.manager import PortfolioManager

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("")
async def get_portfolio(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    manager = PortfolioManager(settings.initial_capital)
    summary = await manager.snapshot(db)
    return summary.model_dump(mode="json")
END

cat > app/api/risk.py <<'END'
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database.session import get_db
from app.risk.kill_switch import KillSwitch
from app.risk.limits import load_limits
from app.risk.manager import RiskManager

router = APIRouter(prefix="/risk", tags=["risk"])
kill_switch = KillSwitch()

@router.get("")
async def risk_status() -> dict:
    limits = load_limits()
    return {"kill_switch_engaged": kill_switch.engaged, "kill_switch_reason": kill_switch.reason, "limits": {"max_position_size": limits.max_position_size, "max_loss_per_trade": limits.max_loss_per_trade, "max_total_exposure": limits.max_total_exposure, "daily_stop_loss": limits.daily_stop_loss, "weekly_stop_loss": limits.weekly_stop_loss, "max_drawdown": limits.max_drawdown}, "live_mode": "LOCKED"}

@router.get("/monthly")
async def monthly_risk(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    manager = RiskManager()
    return await manager.monthly_performance(db, settings.initial_capital)

@router.post("/emergency-stop")
async def emergency_stop(reason: str = "manual API call") -> dict:
    kill_switch.engage(reason)
    return {"engaged": True, "reason": reason}
END

cat > app/api/strategies.py <<'END'
from fastapi import APIRouter

router = APIRouter(prefix="/strategies", tags=["strategies"])

@router.get("")
async def list_strategies() -> list[dict]:
    return [{"name": "weather", "display_name": "Weather Trading", "enabled": True}, {"name": "sports", "display_name": "Sports Trading", "enabled": True}, {"name": "arbitrage", "display_name": "Arbitrage Research", "enabled": True}, {"name": "wallet_intelligence", "display_name": "Wallet Intelligence", "enabled": True}, {"name": "market_making", "display_name": "Market Making Research", "enabled": True}, {"name": "latency_monitor", "display_name": "Latency Monitor", "enabled": True}]
END

cat > app/api/backtest.py <<'END'
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.backtesting.engine import BacktestEngine
from app.backtesting.historical_loader import HistoricalDataLoader
from app.backtesting.metrics import monthly_returns_pct
from app.database.session import get_db
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient

router = APIRouter(prefix="/backtest", tags=["backtest"])

class BacktestRequest(BaseModel):
    strategy: str
    trades: list[dict]
    out_of_sample: bool = False

class HistoricalBacktestRequest(BaseModel):
    strategy: str
    closed_within_days: int = 365
    limit_markets: int = 50
    fidelity: int = 60

@router.post("/run")
async def run_backtest(payload: BacktestRequest, db: AsyncSession = Depends(get_db)) -> dict:
    engine = BacktestEngine()
    run = await engine.run(db, payload.strategy, payload.trades, payload.out_of_sample)
    return {"run_id": run.id, "strategy": run.strategy, "roi": run.roi, "max_drawdown": run.max_drawdown, "win_rate": run.win_rate, "profit_factor": run.profit_factor, "total_trades": run.total_trades, "out_of_sample": run.out_of_sample}

@router.post("/historical")
async def backtest_historical(payload: HistoricalBacktestRequest) -> dict:
    gamma = GammaClient(); clob = ClobClient()
    loader = HistoricalDataLoader(gamma, clob)
    try:
        markets = await loader.load_closed_markets(closed_within_days=payload.closed_within_days, limit=payload.limit_markets)
        pnls_with_dates: list[tuple] = []
        initial_capital = 100.0
        for m in markets:
            histories = await loader.load_price_history_for_market(m, interval="max", fidelity=payload.fidelity)
            yes_points = histories.get(m["token_ids"][0], [])
            for i in range(len(yes_points) - 1):
                p_now = float(yes_points[i].get("p") or yes_points[i].get("price") or 0)
                p_next = float(yes_points[i + 1].get("p") or yes_points[i + 1].get("price") or 0)
                if p_now <= 0.0 or p_next <= 0.0:
                    continue
                if p_now < 0.30 and p_next >= 0.50:
                    size = 1.0 / p_now
                    pnl = (p_next - p_now) * size
                    ts = yes_points[i + 1].get("t") or yes_points[i + 1].get("timestamp")
                    try:
                        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    except Exception:
                        continue
                    pnls_with_dates.append((dt, pnl))
        monthly = monthly_returns_pct(pnls_with_dates, initial_capital)
        total_pnl = sum(p for _, p in pnls_with_dates)
        return {"strategy": payload.strategy, "markets_loaded": len(markets), "simulated_trades": len(pnls_with_dates), "total_pnl": round(total_pnl, 4), "monthly_returns_pct": monthly, "initial_capital": initial_capital}
    finally:
        await gamma.close(); await clob.close()
END

cat > app/api/settings.py <<'END'
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
async def get_settings_endpoint() -> dict:
    s = get_settings()
    return {"initial_capital": s.initial_capital, "reserve": s.reserve, "trading_budget": s.trading_budget, "execution_reserve": s.execution_reserve, "untouchable_reserve": s.untouchable_reserve, "max_position_size": s.max_position_size, "max_loss_per_trade": s.max_loss_per_trade, "live_trading_enabled": s.live_trading_enabled, "live_mode": "LOCKED" if not s.live_trading_enabled else "UNLOCKED"}
END

# ---- Scheduler ----
cat > app/services/scheduler.py <<'END'
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.core.logging import get_logger
from app.market_data.clob_client import ClobClient
from app.market_data.gamma_client import GammaClient
from app.market_data.scanner import MarketScanner

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()

async def scan_job() -> None:
    gamma = GammaClient(); clob = ClobClient()
    scanner = MarketScanner(gamma, clob)
    try:
        markets = await scanner.scan(limit=100)
        logger.info("Scheduled scan complete: %d markets", len(markets))
    except Exception:
        logger.exception("Scheduled scan failed")
    finally:
        await gamma.close(); await clob.close()

async def start_scheduler() -> None:
    settings = get_settings()
    scheduler.add_job(scan_job, IntervalTrigger(seconds=settings.scan_interval_seconds), id="market_scan", replace_existing=True, max_instances=1)
    scheduler.start()
    logger.info("Scheduler started (scan every %ss)", settings.scan_interval_seconds)

async def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
END

# ---- Telegram ----
cat > app/telegram/bot.py <<'END'
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def _owner_only(update: Update) -> bool:
    settings = get_settings()
    user = update.effective_user
    return bool(user and user.id == settings.telegram_owner_id)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text("POLYMASTER AI\n\nPaper trading mode is active. Live mode is LOCKED.\nUse /status, /balance, /risk, /pause.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("System: online\nMode: PAPER\nLive mode: LOCKED")

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("Paper balance available via dashboard /api/portfolio")

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("Risk limits: max position $5, max loss/trade $1, daily stop $3.")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    from app.risk.kill_switch import KillSwitch
    KillSwitch().engage("paused via Telegram")
    await update.message.reply_text("Kill switch engaged. New trades blocked.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    from app.risk.kill_switch import KillSwitch
    KillSwitch().disengage("resumed via Telegram")
    await update.message.reply_text("Kill switch disengaged.")

async def cmd_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update): return
    await update.message.reply_text("Mode is always PAPER. Live trading requires manual unlock and gate completion.")

def build_application() -> Application | None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("Telegram token not configured; bot disabled")
        return None
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("paper", cmd_paper))
    return app
END

cat > app/telegram/runner.py <<'END'
import asyncio
from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.telegram.bot import build_application

setup_logging()
logger = get_logger(__name__)

async def main() -> None:
    settings = get_settings()
    app = build_application()
    if app is None:
        logger.error("Cannot start Telegram bot: token missing")
        return
    if not settings.telegram_owner_id:
        logger.error("TELEGRAM_OWNER_ID is not set; bot will refuse all commands")
    async with app:
        await app.start()
        await app.updater.start_polling()
        logger.info("Telegram bot started")
        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
END

# ---- Dashboard ----
cat > app/dashboard/templates/index.html <<'END'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>POLYMASTER AI</title>
  <style>
    :root { --bg:#0b0f14; --card:#131a22; --text:#e6edf3; --muted:#8b949e; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }
    .top { padding:16px; border-bottom:1px solid #21262d; display:flex; justify-content:space-between; align-items:center; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; padding:16px; }
    .card { background:var(--card); border:1px solid #21262d; border-radius:10px; padding:16px; }
    .card h3 { margin:0 0 8px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
    .val { font-size:24px; font-weight:700; }
    .ok { color:#3fb950; }
    .bad { color:#f85149; }
    .muted { color:var(--muted); font-size:12px; }
    @media (max-width:480px){ .val{font-size:20px;} }
  </style>
</head>
<body>
  <div class="top"><strong>POLYMASTER AI</strong><span class="muted">PAPER · LIVE LOCKED</span></div>
  <div class="grid">
    <div class="card"><h3>Total Equity</h3><div class="val" id="equity">—</div><div class="muted" id="cash"></div></div>
    <div class="card"><h3>Realized PnL</h3><div class="val" id="pnl">—</div></div>
    <div class="card"><h3>Drawdown</h3><div class="val" id="dd">—</div></div>
    <div class="card"><h3>Open Positions</h3><div class="val" id="positions">—</div></div>
    <div class="card"><h3>Risk</h3><div class="val ok" id="risk">OK</div></div>
    <div class="card"><h3>System</h3><div class="val ok" id="health">—</div></div>
  </div>
  <script>
    async function load() {
      try {
        const [p, r, h] = await Promise.all([
          fetch('/api/portfolio').then(x=>x.json()).catch(()=>({})),
          fetch('/api/risk').then(x=>x.json()).catch(()=>({})),
          fetch('/api/health').then(x=>x.json()).catch(()=>({}))
        ]);
        if (p.total_equity !== undefined) {
          document.getElementById('equity').textContent = '$' + Number(p.total_equity).toFixed(2);
          document.getElementById('cash').textContent = 'Cash $' + Number(p.cash).toFixed(2);
          document.getElementById('pnl').textContent = '$' + Number(p.realized_pnl).toFixed(2);
          document.getElementById('dd').textContent = '$' + Number(p.drawdown).toFixed(2);
          document.getElementById('positions').textContent = p.open_positions;
        }
        if (r.kill_switch_engaged !== undefined) {
          document.getElementById('risk').textContent = r.kill_switch_engaged ? 'BLOCKED' : 'OK';
          document.getElementById('risk').className = 'val ' + (r.kill_switch_engaged ? 'bad' : 'ok');
        }
        document.getElementById('health').textContent = h.status || '—';
      } catch (e) { console.error(e); }
    }
    load(); setInterval(load, 15000);
  </script>
</body>
</html>
END

# ---- Main ----
cat > app/main.py <<'END'
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path
from app.api import backtest, health, markets, portfolio, risk, settings, signals, strategies
from app.core.logging import get_logger, setup_logging
from app.database.init_db import init_db
from app.services.scheduler import start_scheduler, stop_scheduler

setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting POLYMASTER AI")
    await init_db()
    await start_scheduler()
    yield
    await stop_scheduler()
    logger.info("POLYMASTER AI stopped")

app = FastAPI(title="POLYMASTER AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/api")
app.include_router(markets.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    template = Path("app/dashboard/templates/index.html")
    return template.read_text() if template.exists() else "POLYMASTER AI"
END

# ---- Scripts ----
cat > scripts/seed.py <<'END'
import asyncio
from app.database.init_db import init_db
from app.database.session import AsyncSessionLocal
from app.models.strategy import Strategy

async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        for name, display in [("weather", "Weather Trading"), ("sports", "Sports Trading"), ("arbitrage", "Arbitrage Research"), ("wallet_intelligence", "Wallet Intelligence"), ("market_making", "Market Making Research"), ("latency_monitor", "Latency & Price Monitor")]:
            db.add(Strategy(name=name, display_name=display))
        await db.commit()

if __name__ == "__main__":
    asyncio.run(main())
END

# ---- Tests ----
cat > tests/conftest.py <<'END'
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.database.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()
END

cat > tests/test_risk_manager.py <<'END'
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
END

cat > tests/test_paper_trading.py <<'END'
import pytest
from app.paper_trading.simulator import PaperSimulator

def test_partial_fill_when_depth_insufficient():
    sim = PaperSimulator(slippage_bps=0, fee_bps=0)
    asks = [[0.50, 10], [0.55, 5]]
    result = sim.simulate_buy(asks, size_usd=10.0)
    assert result.filled_size == pytest.approx(20.0)
    assert result.partial is True

def test_full_fill_with_slippage():
    sim = PaperSimulator(slippage_bps=100, fee_bps=0)
    asks = [[0.50, 100]]
    result = sim.simulate_buy(asks, size_usd=10.0)
    assert result.avg_price > 0.50
    assert result.partial is False
END

cat > tests/test_pnl.py <<'END'
from app.backtesting.metrics import compute_metrics

def test_metrics_with_mixed_pnls():
    m = compute_metrics([2.0, -1.0, 3.0, -1.0], initial_capital=100)
    assert m.total_trades == 4
    assert m.win_rate == 0.5
    assert m.profit_factor == 2.5
    assert m.roi == 0.03
END

cat > tests/test_live_mode_blocked.py <<'END'
from app.config import get_settings

def test_live_mode_locked_by_default():
    s = get_settings()
    assert s.live_trading_enabled is False
    assert s.live_mode_locked is True
END

cat > tests/test_strategies.py <<'END'
import pytest
from app.strategies.arbitrage import ArbitrageResearchStrategy

@pytest.mark.asyncio
async def test_arbitrage_returns_research_not_trade():
    s = ArbitrageResearchStrategy()
    market = {"id": "m1", "clob_token_ids": ["t1", "t2"], "best_ask": 0.48, "best_bid": 0.50, "spread": 0.02}
    sig = await s.evaluate(market)
    assert sig is not None
    assert sig.rejection_reason is not None
END

# ---- README ----
cat > README.md <<'END'
# POLYMASTER AI

Autonomous research and paper-trading platform for Polymarket.

**Live trading is LOCKED by default. This project performs paper trading only.**

## Quick Start (Local)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: DATABASE_URL, TELEGRAM_BOT_OKEN, TELEGRAM_OWNER_ID
python scripts/seed.py
uvi