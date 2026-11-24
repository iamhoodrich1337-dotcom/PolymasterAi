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
