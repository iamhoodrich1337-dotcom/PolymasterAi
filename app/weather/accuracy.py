"""Pure accuracy statistics for the weather scout (no database imports, easy to test)."""
from collections import defaultdict
from typing import Any

from app.weather.model import parse_bin

THRESHOLDS = (0.05, 0.10, 0.20)


def _sim(items: list[dict[str, Any]], min_edge: float) -> dict[str, Any]:
    bets = wins = 0
    pnl = 0.0
    for it in items:
        ask = it["ask"]
        if it["edge"] < min_edge or not (0.03 <= ask <= 0.97):
            continue
        bets += 1
        if it["y"]:
            wins += 1
            pnl += 1.0 / ask - 1.0
        else:
            pnl -= 1.0
    return {"bets": bets, "wins": wins, "pnl": round(pnl, 2), "roi": round(pnl / bets, 3) if bets else None}


def compute_accuracy(items: list[dict[str, Any]]) -> dict[str, Any]:
    """items: one dict per signal row: market_id, city, day, p (model), ask (market), edge, src (sources dict).
    Uses only the EARLIEST signal of each market so repeated snapshots are not double counted."""
    first: dict[str, dict[str, Any]] = {}
    for it in items:
        first.setdefault(it["market_id"], it)
    res = []
    for it in first.values():
        y = it["src"].get("resolved")
        if y in (0, 1):
            res.append({**it, "y": int(y)})
    out: dict[str, Any] = {"signals_total": len(items), "markets_total": len(first), "resolved_markets": len(res)}
    if not res:
        return {**out, "brier": None, "split": {}, "blend": [], "buckets": [], "sim": [], "bias": []}
    out["brier"] = {
        "model": round(sum((r["p"] - r["y"]) ** 2 for r in res) / len(res), 4),
        "market": round(sum((r["ask"] - r["y"]) ** 2 for r in res) / len(res), 4),
    }
    def _brier(grp: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not grp:
            return None
        return {"n": len(grp), "model": round(sum((r["p"] - r["y"]) ** 2 for r in grp) / len(grp), 4),
                "market": round(sum((r["ask"] - r["y"]) ** 2 for r in grp) / len(grp), 4)}

    out["split"] = {"station": _brier([r for r in res if not r["src"].get("approx_location")]),
                    "approx": _brier([r for r in res if r["src"].get("approx_location")])}
    out["blend"] = [{"w": w, "brier": round(sum((w * r["p"] + (1 - w) * r["ask"] - r["y"]) ** 2 for r in res) / len(res), 4)}
                    for w in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)]
    edges = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.01)]
    buckets = []
    for lo, hi in edges:
        grp = [r for r in res if lo <= r["p"] < hi]
        if grp:
            buckets.append({"range": f"{int(lo * 100)}-{min(100, int(hi * 100))}%", "n": len(grp),
                            "predicted": round(sum(r["p"] for r in grp) / len(grp), 3),
                            "actual": round(sum(r["y"] for r in grp) / len(grp), 3)})
    out["buckets"] = buckets
    sim = []
    for t in THRESHOLDS:
        sim.append({
            "min_edge": t,
            "station": _sim([r for r in res if not r["src"].get("approx_location")], t),
            "approx": _sim([r for r in res if r["src"].get("approx_location")], t),
        })
    out["sim"] = sim
    # bias: actual temperature (from the winning exact bin) minus the ensemble mean
    per_city: dict[str, list[float]] = defaultdict(list)
    units: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for r in res:
        if r["y"] != 1 or (r["city"], r["day"]) in seen:
            continue
        b = parse_bin(r["src"].get("bin"))
        mean = r["src"].get("mean_max")
        if not b or b[0] is None or b[1] is None or mean is None:
            continue
        seen.add((r["city"], r["day"]))
        per_city[r["city"]].append((b[0] + b[1]) / 2.0 - float(mean))
        units[r["city"]] = b[2]
    bias = [{"city": c, "days": len(v), "bias": round(sum(v) / len(v), 2), "unit": units[c]} for c, v in per_city.items()]
    bias.sort(key=lambda x: abs(x["bias"]), reverse=True)
    out["bias"] = bias[:15]
    return out
