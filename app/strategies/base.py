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
