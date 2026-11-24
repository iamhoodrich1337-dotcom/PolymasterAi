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
