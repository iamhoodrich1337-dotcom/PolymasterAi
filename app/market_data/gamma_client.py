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
