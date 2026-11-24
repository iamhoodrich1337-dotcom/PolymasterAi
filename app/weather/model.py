"""Pure helpers for daily-high temperature markets (no database / network imports)."""
import math
import re
from datetime import date

SIGMA = {"F": 1.8, "C": 1.0}  # extra forecast error added on top of ensemble spread

AIRPORTS: dict[str, tuple[float, float]] = {
    "KLGA": (40.7769, -73.8740), "KJFK": (40.6398, -73.7789), "KEWR": (40.6925, -74.1687),
    "KORD": (41.9742, -87.9073), "KMDW": (41.7868, -87.7522),
    "KHOU": (29.6454, -95.2789), "KIAH": (29.9844, -95.3414),
    "KSFO": (37.6213, -122.3790), "KLAX": (33.9416, -118.4085),
    "KMIA": (25.7959, -80.2870), "KATL": (33.6407, -84.4277),
    "KDFW": (32.8998, -97.0403), "KDAL": (32.8471, -96.8518),
    "KSEA": (47.4502, -122.3088), "KDEN": (39.8561, -104.6737),
    "KBOS": (42.3656, -71.0096), "KPHX": (33.4342, -112.0116), "KAUS": (30.1945, -97.6699),
    "EGLC": (51.5053, 0.0553), "EGLL": (51.4700, -0.4543), "LFPG": (49.0097, 2.5479), "LFPB": (48.9694, 2.4414),
    "EHAM": (52.3086, 4.7639), "LTAC": (40.1281, 32.9951), "LTFM": (41.2753, 28.7519), "LTBA": (40.9769, 28.8146),
    "ZBAA": (40.0801, 116.5846), "RKPK": (35.1795, 128.9382), "RKSI": (37.4602, 126.4407), "FACT": (-33.9715, 18.6021),
    "ZUUU": (30.5785, 103.9471), "ZUCK": (29.7192, 106.6417), "ZGGG": (23.3924, 113.2988), "EFHK": (60.3172, 24.9633),
    "VHHH": (22.3080, 113.9185), "OEJN": (21.6796, 39.1565), "OPKC": (24.9065, 67.1608), "WMKK": (2.7456, 101.7099),
    "VILK": (26.7606, 80.8893), "LEMD": (40.4719, -3.5626), "RPLL": (14.5086, 121.0194), "MMMX": (19.4363, -99.0721),
    "LIMC": (45.6306, 8.7281), "UUWW": (55.5915, 37.2615), "UUEE": (55.9726, 37.4146), "EDDM": (48.3538, 11.7861),
    "MPTO": (9.0714, -79.3835), "ZSQD": (36.2661, 120.3744), "SBGR": (-23.4356, -46.4731), "ZSPD": (31.1443, 121.8083),
    "ZGSZ": (22.6393, 113.8107), "WSSS": (1.3644, 103.9915), "RCTP": (25.0777, 121.2328), "LLBG": (32.0114, 34.8867),
    "RJTT": (35.5494, 139.7798), "CYYZ": (43.6777, -79.6248), "EPWA": (52.1657, 20.9671), "NZWN": (-41.3272, 174.8053),
    "ZHHH": (30.7838, 114.2081), "ZHCC": (34.5197, 113.8408), "ZSJN": (36.8572, 117.2158), "SAEZ": (-34.8222, -58.5358),
    "SABE": (-34.5592, -58.4156), "LEBL": (41.2974, 2.0833),
}
STATION_NAMES = {
    "laguardia": "KLGA", "o'hare": "KORD", "ohare": "KORD", "hobby": "KHOU", "midway": "KMDW",
    "san francisco international": "KSFO", "los angeles international": "KLAX", "london city": "EGLC",
}
CITY_QUERY = {"nyc": "New York", "san-francisco": "San Francisco", "los-angeles": "Los Angeles"}
CITY_SLUGS = ["nyc", "chicago", "houston", "san-francisco", "los-angeles", "miami", "dallas", "atlanta", "seattle", "denver", "boston", "london", "paris"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

_SLUG_RE = re.compile(r"^highest-temperature-in-(.+)-on-([a-z]+)-(\d{1,2})-(\d{4})$")
_ICAO_RE = re.compile(r"wunderground\.com/history/daily/[^\s\"')]*?/([A-Z]{4})\b")
_RANGE_RE = re.compile(r"(-?\d+)\s*[-\u2013]\s*(-?\d+)\s*\u00b0?\s*([FC])", re.I)
_LOW_RE = re.compile(r"(-?\d+)\s*\u00b0?\s*([FC])\s*or\s*(below|lower|less)", re.I)
_HIGH_RE = re.compile(r"(-?\d+)\s*\u00b0?\s*([FC])\s*or\s*(higher|above|more)", re.I)
_SINGLE_RE = re.compile(r"(-?\d+)\s*\u00b0\s*([FC])", re.I)


def event_slug(city: str, d: date) -> str:
    return f"highest-temperature-in-{city}-on-{MONTHS[d.month - 1]}-{d.day}-{d.year}"


def parse_slug(slug: str) -> tuple[str, str] | None:
    """-> (city_slug, 'YYYY-MM-DD')"""
    m = _SLUG_RE.match(slug or "")
    if not m or m.group(2) not in MONTHS:
        return None
    return m.group(1), f"{int(m.group(4)):04d}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(3)):02d}"


def extract_icao(*texts: str | None) -> str | None:
    for t in texts:
        if t:
            m = _ICAO_RE.search(t)
            if m:
                return m.group(1)
    return None


def station_from_text(*texts: str | None) -> str | None:
    for t in texts:
        low = (t or "").lower()
        for name, icao in STATION_NAMES.items():
            if name in low:
                return icao
    return None


def city_query(slug: str) -> str:
    return CITY_QUERY.get(slug) or slug.replace("-", " ").title()


def parse_bin(text: str | None) -> tuple[float | None, float | None, str] | None:
    """-> (low, high, unit); None bounds mean open-ended. Bounds are inclusive whole degrees."""
    if not text:
        return None
    m = _LOW_RE.search(text)
    if m:
        return None, float(m.group(1)), m.group(2).upper()
    m = _HIGH_RE.search(text)
    if m:
        return float(m.group(1)), None, m.group(2).upper()
    m = _RANGE_RE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2)), m.group(3).upper()
    m = _SINGLE_RE.search(text)
    if m:
        v = float(m.group(1))
        return v, v, m.group(2).upper()
    return None


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bin_probability(maxes: list[float], low: float | None, high: float | None, sigma: float) -> float:
    """P(rounded daily high falls in [low, high]) averaged over ensemble members, with Gaussian forecast error."""
    if not maxes:
        return 0.0
    total = 0.0
    for x in maxes:
        upper = 1.0 if high is None else _phi((high + 0.5 - x) / sigma)
        lower = 0.0 if low is None else _phi((low - 0.5 - x) / sigma)
        total += max(0.0, upper - lower)
    return total / len(maxes)
