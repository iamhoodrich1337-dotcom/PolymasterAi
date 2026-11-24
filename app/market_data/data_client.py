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
