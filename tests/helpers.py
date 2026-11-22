from pathlib import Path

from taxi.data import load_strings, load_weights, parse_areas
from taxi.model import Candidate

ROOT = Path(__file__).resolve().parent.parent
_COORDS = {"CBD": (-33.8688, 151.2093), "Barangaroo": (-33.8615, 151.2010), "Pyrmont": (-33.8697, 151.1940),
           "Circular Quay/The Rocks": (-33.8599, 151.2090), "Olympic Park": (-33.8474, 151.0636),
           "Rooty Hill": (-33.7707, 150.8440)}
_PAIRS = [["CBD", "Barangaroo", 6], ["CBD", "Pyrmont", 7], ["CBD", "Circular Quay/The Rocks", 5],
          ["CBD", "Olympic Park", 30], ["CBD", "Rooty Hill", 45], ["Barangaroo", "Pyrmont", 6],
          ["Barangaroo", "Circular Quay/The Rocks", 5], ["Barangaroo", "Olympic Park", 30],
          ["Barangaroo", "Rooty Hill", 45], ["Pyrmont", "Circular Quay/The Rocks", 8],
          ["Pyrmont", "Olympic Park", 27], ["Pyrmont", "Rooty Hill", 42],
          ["Circular Quay/The Rocks", "Olympic Park", 32], ["Circular Quay/The Rocks", "Rooty Hill", 47],
          ["Olympic Park", "Rooty Hill", 20]]
AREAS_JSON = {"estimate": True, "researched": "2026-11-23",
              "areas": {n: {"lat": la, "lon": lo} for n, (la, lo) in _COORDS.items()},
              "pairs": _PAIRS, "same_area_min": 5,
              "peak": {"from": "16:00", "to": "19:00", "factor": 1.5}, "late": {"from": "21:00", "factor": 0.8}}
TABLE = parse_areas(AREAS_JSON)
W = load_weights(ROOT / "weights.json")
S = load_strings(ROOT / "site" / "strings.json")

OFFICE = {"id": "kpmg-barangaroo", "name": "KPMG Barangaroo", "address": "Tower 3, 300 Barangaroo Ave, Barangaroo NSW 2000",
          "area": "Barangaroo", "lat": -33.8622, "lon": 151.2016, "staff": 3000, "cabcharge": 1.0, "median_age": 40,
          "age_lo": 25, "age_hi": 55, "spend": 0.7, "normal_finish": "17:30", "late_finish": "20:30",
          "wait": "Barangaroo Ave rank", "desc": "Big accounting firm, about 3,000 staff. Many use Cabcharge.",
          "source_url": "https://kpmg.com/au/en/home/contacts/offices.html"}


def cand(**kw) -> Candidate:
    base = dict(id="x", kind="event", name="X", venue="V", address="A", area="CBD",
                lat=-33.8688, lon=151.2093, source_url="https://example.com")
    base.update(kw)
    return Candidate(**base)
