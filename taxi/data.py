import json
import re
from itertools import combinations
from datetime import date
from pathlib import Path
from typing import Any

from taxi.model import shift_minute

WEIGHT_KEYS = ("points", "age_curve", "size", "late", "boost", "rain", "plan", "office", "cruise",
               "ticketmaster", "claude", "cache_keep_days")
STEADY_KINDS = ("hotel", "casino", "club", "hospital")
VENUE_KINDS = ("venue", "racecourse")


class DataError(Exception):
    pass


def load_json(path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise DataError(f"{Path(path).name}: cannot read ({e})") from e


def _hm(v) -> bool:
    return isinstance(v, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v) is not None


def _num(v, lo, hi) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def _int(v, lo, hi) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _url(v) -> bool:
    return isinstance(v, str) and v.startswith(("http://", "https://"))


def _str(v, max_len=None) -> bool:
    return isinstance(v, str) and v != "" and (max_len is None or len(v) <= max_len)


def _geo(r) -> bool:
    return _num(r.get("lat"), -34.5, -33.0) and _num(r.get("lon"), 150.0, 151.5)


def _check_header(obj, fname: str) -> None:
    if not isinstance(obj, dict):
        raise DataError(f"{fname}: top level must be an object")
    if obj.get("estimate") is not True:
        raise DataError(f"{fname}: top-level \"estimate\" must be true")
    if not _str(obj.get("researched")):
        raise DataError(f"{fname}: missing \"researched\" date")


def _load_list(path, key: str, rules, area_names: set[str], id_key: str = "id") -> list[dict]:
    """Load obj[key], checking each record with rules(record) -> list of problems, area, and unique id_key."""
    fname = Path(path).name
    obj = load_json(path)
    _check_header(obj, fname)
    items = obj.get(key)
    if not isinstance(items, list) or not items:
        raise DataError(f"{fname}: \"{key}\" must be a non-empty list")
    seen = set()
    for i, r in enumerate(items):
        ident = r.get(id_key) if isinstance(r, dict) else None
        label = f"{fname}: {ident or f'{key}[{i}]'}"
        if not isinstance(r, dict) or not _str(ident):
            raise DataError(f"{label}: needs a non-empty \"{id_key}\"")
        if ident in seen:
            raise DataError(f"{label}: duplicate {id_key}")
        seen.add(ident)
        if r.get("area") not in area_names:
            raise DataError(f"{label}: unknown area {r.get('area')!r}")
        bad = rules(r)
        if bad:
            raise DataError(f"{label}: bad or missing {', '.join(bad)}")
    return items


def parse_areas(obj: dict) -> dict:
    f = "areas.json"
    _check_header(obj, f)
    areas = obj.get("areas")
    if not isinstance(areas, dict) or "CBD" not in areas:
        raise DataError(f"{f}: \"areas\" must be an object containing \"CBD\"")
    for name, a in areas.items():
        if not (isinstance(a, dict) and _geo(a)):
            raise DataError(f"{f}: area {name!r} needs lat -34.5..-33.0 and lon 150.0..151.5")
    minutes: dict[tuple[str, str], int] = {}
    for p in obj.get("pairs", []):
        if not (isinstance(p, list) and len(p) == 3 and p[0] in areas and p[1] in areas and p[0] != p[1]
                and _int(p[2], 1, 120)):
            raise DataError(f"{f}: bad pair {p!r}")
        if (p[0], p[1]) in minutes:
            raise DataError(f"{f}: duplicate pair {p[0]} - {p[1]}")
        minutes[(p[0], p[1])] = minutes[(p[1], p[0])] = p[2]
    for a, b in combinations(areas, 2):
        if (a, b) not in minutes:
            raise DataError(f"{f}: missing pair {a} - {b}")
    peak, late = obj.get("peak"), obj.get("late")
    if not (isinstance(peak, dict) and _hm(peak.get("from")) and _hm(peak.get("to")) and _num(peak.get("factor"), 0.1, 10)):
        raise DataError(f"{f}: bad \"peak\"")
    if not (isinstance(late, dict) and _hm(late.get("from")) and _num(late.get("factor"), 0.1, 10)):
        raise DataError(f"{f}: bad \"late\"")
    if not _int(obj.get("same_area_min"), 1, 120):
        raise DataError(f"{f}: bad \"same_area_min\"")
    return {"areas": {n: (a["lat"], a["lon"]) for n, a in areas.items()}, "minutes": minutes,
            "same_area_min": obj["same_area_min"],
            "peak": (shift_minute(peak["from"]), shift_minute(peak["to"]), peak["factor"]),
            "late": (shift_minute(late["from"]), late["factor"])}


def load_areas(path) -> dict:
    return parse_areas(load_json(path))


def _office_problems(r) -> list[str]:
    checks = {"name": _str(r.get("name")), "address": _str(r.get("address")), "lat/lon": _geo(r),
              "staff": _int(r.get("staff"), 100, 20000), "cabcharge": _num(r.get("cabcharge"), 0, 1),
              "median_age": _num(r.get("median_age"), 18, 70), "age_lo": _int(r.get("age_lo"), 0, 100),
              "age_hi": _int(r.get("age_hi"), 0, 100), "spend": _num(r.get("spend"), 0, 1),
              "normal_finish": _hm(r.get("normal_finish")) and "16:30" <= r["normal_finish"] <= "18:59",
              "late_finish": _hm(r.get("late_finish")) and "19:30" <= r["late_finish"] <= "22:30",
              "wait": isinstance(r.get("wait"), str), "desc": _str(r.get("desc"), 160),
              "source_url": _url(r.get("source_url"))}
    return [k for k, ok in checks.items() if not ok]


def _steady_problems(r) -> list[str]:
    busy = r.get("busy")
    checks = {"kind": r.get("kind") in STEADY_KINDS, "name": _str(r.get("name")), "address": _str(r.get("address")),
              "lat/lon": _geo(r),
              "busy": isinstance(busy, list) and bool(busy)
              and all(isinstance(b, list) and len(b) == 2 and _hm(b[0]) and _hm(b[1]) for b in busy),
              "wait": isinstance(r.get("wait"), str)}
    return [k for k, ok in checks.items() if not ok]


def _venue_problems(r) -> list[str]:
    checks = {"kind": r.get("kind") in VENUE_KINDS, "address": _str(r.get("address")), "what_on_url": _url(r.get("what_on_url"))}
    return [k for k, ok in checks.items() if not ok]


def load_offices(path, area_names: set[str]) -> list[dict]:
    return _load_list(path, "offices", _office_problems, area_names)


def load_steady(path, area_names: set[str]) -> list[dict]:
    return _load_list(path, "places", _steady_problems, area_names)


def load_venues(path, area_names: set[str]) -> list[dict]:
    return _load_list(path, "venues", _venue_problems, area_names, id_key="name")


def load_holidays(path) -> frozenset[date]:
    fname = Path(path).name
    obj = load_json(path)
    _check_header(obj, fname)
    try:
        return frozenset(date.fromisoformat(d) for d in obj["dates"])
    except (KeyError, TypeError, ValueError) as e:
        raise DataError(f"{fname}: \"dates\" must be a list of YYYY-MM-DD") from e


def load_weights(path) -> dict:
    w = load_json(path)
    missing = [k for k in WEIGHT_KEYS if not isinstance(w, dict) or k not in w]
    if missing:
        raise DataError(f"weights.json: missing {', '.join(missing)}")
    if sum(w["points"].values()) != 100:
        raise DataError("weights.json: \"points\" must sum to 100")
    return w


def load_strings(path, lang: str | None = None) -> dict:
    obj = load_json(path)
    lang = lang or obj.get("lang")
    if lang not in obj:
        raise DataError(f"strings.json: no language {lang!r}")
    return obj[lang]
