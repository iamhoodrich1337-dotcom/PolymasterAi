from functools import lru_cache
from pydantic import field_validator
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
    admin_token: str = ""
    exit_take_profit_pct: float = 0.20
    exit_stop_loss_pct: float = 0.40
    kelly_fraction: float = 0.5
    auto_paper_trading: bool = True
    weather_provider_url: str = ""
    weather_api_key: str = ""
    odds_provider_url: str = ""
    odds_api_key: str = ""

    @field_validator("database_url")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @property
    def live_mode_locked(self) -> bool:
        return not self.live_trading_enabled

@lru_cache
def get_settings() -> Settings:
    return Settings()
