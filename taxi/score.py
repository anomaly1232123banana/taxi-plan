import math

from taxi.model import Candidate, shift_minute, shift_slot


def age_factor(age: float, curve: list) -> float:
    if age <= curve[0][0]:
        return curve[0][1]
    for (a0, f0), (a1, f1) in zip(curve, curve[1:]):
        if age <= a1:
            return f0 + (f1 - f0) * (age - a0) / (a1 - a0)
    return curve[-1][1]


def size_factor(n: int, w: dict) -> float:
    lo, hi = w["size"]["zero_at"], w["size"]["full_at"]
    if n <= lo:
        return 0.0
    return min(1.0, math.log10(n / lo) / math.log10(hi / lo))


def late_factor(exit_minute: int, w: dict) -> float:
    if exit_minute >= shift_minute(w["late"]["full_from"]):
        return 1
    return 0.5 if exit_minute >= shift_minute(w["late"]["half_from"]) else 0


def score(median_age: float, pays: float, size: int, spend: float, exit_minute: int, w: dict,
          rain: bool = False, disrupted: bool = False) -> int:
    p = w["points"]
    raw = (p["age"] * age_factor(median_age, w["age_curve"]) + p["pays"] * pays + p["size"] * size_factor(size, w)
           + p["spend"] * spend + p["late"] * late_factor(exit_minute, w))
    if rain:
        raw *= w["boost"]["rain"]
    if disrupted:
        raw *= w["boost"]["disruption"]
    return round(min(100, raw))


def score_candidate(c: Candidate, w: dict, rain: set[str], disruptions: list[dict]) -> int:
    _, minute = shift_slot(c.exit)
    hm = c.exit.strftime("%H:%M")
    disrupted = any(d["area"] in (c.area, "ALL") and d["date"] == c.exit.date().isoformat() and d["from"] <= hm <= d["to"]
                    for d in disruptions)
    c.score = score(c.median_age, c.pays, c.size, c.spend, minute, w,
                    rain=c.exit.strftime("%Y-%m-%dT%H") in rain, disrupted=disrupted)
    return c.score
