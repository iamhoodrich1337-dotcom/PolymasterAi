from dataclasses import dataclass, field
from app.core.utils import clamp

@dataclass
class ProbabilityEstimate:
    probability: float
    confidence: float
    sources: list[str] = field(default_factory=list)
    reasoning: str = ""

class ProbabilityEngine:
    def estimate(self, market_probability: float, external_signals: list[tuple[float, float, str]], min_confidence: float = 0.3) -> ProbabilityEstimate:
        valid = [(p, c, s) for p, c, s in external_signals if 0.0 <= p <= 1.0 and c > 0.0]
        if not valid:
            return ProbabilityEstimate(probability=market_probability, confidence=0.0, sources=[], reasoning="No external signals; market probability used as prior.")
        total_weight = sum(c for _, c, _ in valid)
        weighted = sum(p * c for p, c, _ in valid) / total_weight
        agreement = 1.0 - (max(p for p, _, _ in valid) - min(p for p, _, _ in valid))
        source_quality = min(total_weight / len(valid), 1.0)
        confidence = clamp(agreement * source_quality, 0.0, 1.0)
        final = market_probability + (weighted - market_probability) * confidence
        return ProbabilityEstimate(probability=clamp(final, 0.01, 0.99), confidence=confidence if confidence >= min_confidence else 0.0, sources=[s for _, _, s in valid], reasoning=f"weighted={weighted:.4f}, agreement={agreement:.4f}, quality={source_quality:.4f}")
