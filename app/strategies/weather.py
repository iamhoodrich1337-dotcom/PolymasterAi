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
