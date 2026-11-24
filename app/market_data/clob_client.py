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
