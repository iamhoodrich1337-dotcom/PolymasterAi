import json
from datetime import datetime, timezone
from typing import Any

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def safe_json_loads(value: Any, default: Any = None) -> Any:
    if value is None: return default
    if isinstance(value, (dict, list)): return value
    if isinstance(value, str):
        try: return json.loads(value)
        except (json.JSONDecodeError, TypeError): return default
    return default

def parse_float(value: Any, default: float = 0.0) -> float:
    try: return float(value)
    except (TypeError, ValueError): return default

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
