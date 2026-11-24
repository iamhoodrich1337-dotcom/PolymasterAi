from dataclasses import dataclass

@dataclass
class RealismReport:
    score: float
    warnings: list[str]

def assess_realism(partial_fill_rate: float, avg_slippage_bps: float, rejected_by_depth: int, total_signals: int) -> RealismReport:
    warnings: list[str] = []
    score = 1.0
    if partial_fill_rate > 0.3:
        warnings.append("High partial-fill rate; paper results may overstate capacity")
        score -= 0.2
    if avg_slippage_bps > 100:
        warnings.append("Slippage assumption is aggressive")
        score -= 0.2
    if total_signals > 0 and rejected_by_depth / total_signals > 0.2:
        warnings.append("Many signals rejected due to insufficient depth")
        score -= 0.2
    return RealismReport(score=max(0.0, round(score, 2)), warnings=warnings)
