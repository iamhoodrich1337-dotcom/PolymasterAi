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
