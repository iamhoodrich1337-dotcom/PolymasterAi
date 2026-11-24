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
