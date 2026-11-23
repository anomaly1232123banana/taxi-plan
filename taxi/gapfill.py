import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta

from taxi.claude import ClaudeError, extract_json
from taxi.estimate import apply_estimate, validate_estimate
from taxi.model import SYD, Candidate, slug

log = logging.getLogger(__name__)

OVERLAP_MIN = 60  # a found event starting this close to a known one in the same area is a duplicate
MAX_STR = 120
EVENT_KINDS = ("event", "race")
DISRUPTION_KINDS = ("trackwork", "strike")
_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _s(v) -> bool:
    return isinstance(v, str) and 1 <= len(v) <= MAX_STR


def _url(v) -> bool:
    return isinstance(v, str) and re.match(r"^https?://\S+$", v) is not None


def _day(v, days: set[date]) -> bool:
    try:
        return isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) is not None and date.fromisoformat(v) in days
    except ValueError:
        return False


def _hm(v) -> bool:
    return isinstance(v, str) and _HM.match(v) is not None


def gapfill_prompt(venues: list[dict], days: list[date], known: list[str], area_names: list[str],
                   max_searches: int, language: str) -> str:
    return (
        "Find upcoming Sydney events and transport disruptions that matter to a taxi driver.\n\n"
        "Venues and where to see what is on:\n" + "\n".join(f"- {v['name']} | {v['what_on_url']}" for v in venues) + "\n\n"
        "Dates: " + ", ".join(d.isoformat() for d in days) + "\n\n"
        "Already known, skip these (venue | date):\n" + ("\n".join(f"- {k}" for k in known) or "- none") + "\n\n"
        "Allowed area names: " + ", ".join(area_names) + "\n\n"
        "Find (1) events at those venues expecting at least 500 people, (2) race meetings at the Sydney racecourses, "
        "and (3) Sydney train trackwork or transport strikes on those dates.\n"
        "Every item needs a real source_url taken from the page it came from.\n"
        f"Use at most {max_searches} web searches or fetches in total.\n"
        f"Write wait and desc in {language}.\n"
        "Reply with the bare JSON object (no prose, no code fence): "
        "{\"events\": [...], \"disruptions\": [...]}\n"
        "Event: {\"name\", \"venue\", \"address\", \"area\", \"kind\": \"event\" or \"race\", \"date\": \"YYYY-MM-DD\", "
        "\"start\": \"HH:MM\", \"exit\": \"HH:MM\" (local time most of the crowd leaves), \"source_url\", "
        "\"median_age\", \"age_lo\", \"age_hi\", \"size\" (expected attendance), \"pays\" (share whose taxi an employer pays, 0 to 1), "
        "\"spend\" (spending power 0 to 1), \"wait\" (best nearby place for a taxi to wait), "
        "\"desc\" (one plain sentence for a taxi driver)}\n"
        "Disruption: {\"area\" (an allowed area name, or \"ALL\" for a strike only), \"date\", \"from\": \"HH:MM\", \"to\": \"HH:MM\" (same day), "
        "\"what\": \"trackwork\" or \"strike\", \"source_url\"}"
    )


def validate_event(obj: dict, days: set[date], area_names: set[str]) -> dict | None:
    if not isinstance(obj, dict):
        return None
    est = validate_estimate(obj)
    ok = (est is not None and all(_s(obj.get(k)) for k in ("name", "venue", "address")) and isinstance(obj.get("area"), str) and obj["area"] in area_names
          and obj.get("kind") in EVENT_KINDS and _day(obj.get("date"), days) and _hm(obj.get("start"))
          and _url(obj.get("source_url")))
    if not ok:
        return None
    ev = {k: obj[k] for k in ("name", "venue", "address", "area", "kind", "date", "start", "source_url")}
    return ev | est


def validate_disruption(obj: dict, days: set[date], area_names: set[str]) -> dict | None:
    if not isinstance(obj, dict):
        return None
    ok = (isinstance(obj.get("area"), str) and obj["area"] in area_names | {"ALL"} and _day(obj.get("date"), days) and _hm(obj.get("from"))
          and _hm(obj.get("to")) and obj["from"] <= obj["to"] and obj.get("what") in DISRUPTION_KINDS
          and (obj["area"] != "ALL" or obj["what"] == "strike")  # network-wide trackwork would boost every stop
          and _url(obj.get("source_url")))
    return {k: obj[k] for k in ("area", "date", "from", "to", "what", "source_url")} if ok else None


def event_to_candidate(ev: dict, t: dict) -> Candidate:
    h, m = map(int, ev["start"].split(":"))
    d = date.fromisoformat(ev["date"])
    lat, lon = t["areas"][ev["area"]]
    c = Candidate(id="gf:" + slug(f"{ev['venue']}-{ev['date']}-{ev['name']}")[:80], kind=ev["kind"], name=ev["name"],
                  venue=ev["venue"], address=ev["address"], area=ev["area"], lat=lat, lon=lon, source_url=ev["source_url"],
                  start=datetime(d.year, d.month, d.day, h, m, tzinfo=SYD))
    apply_estimate(c, ev)
    return c


def _overlaps(c: Candidate, others: list[Candidate]) -> bool:
    return any(o.id != c.id and o.area == c.area and o.start and abs(o.start - c.start) <= timedelta(minutes=OVERLAP_MIN)
               for o in others)


def _alive(alive: Callable[[str], bool], url: str) -> bool:
    try:
        return bool(alive(url))
    except Exception:  # a malformed URL from Claude must not stop the scan
        return False


def gapfill(call: Callable[[str], str] | None, venues: list[dict], days: list[date], existing: list[Candidate],
            t: dict, cache: dict, today: date, w: dict, language: str,
            alive: Callable[[str], bool]) -> tuple[list[Candidate], list[dict], str]:
    store = cache["gapfill"]
    disruptions: list[dict] = []
    status = "ok"

    def cached() -> list[Candidate]:
        return [event_to_candidate(v["event"], t) for v in store.values() if v["event"]["date"] >= today.isoformat()]

    if call is None:
        status = "skipped"
    elif cache.get("gapfill_ran") == today.isoformat():
        status = "cached"  # same-day re-run: the search is the costliest Claude call, so reuse today's result
    else:
        names = set(t["areas"])
        pool = existing + cached()
        known = sorted({f"{e.venue} | {e.start:%Y-%m-%d}" for e in pool if e.start})
        cw = w["claude"]
        try:
            obj = extract_json(call(gapfill_prompt(venues, days, known, sorted(names), cw["gapfill_max_searches"], language)))
            if not isinstance(obj, dict):
                raise ClaudeError("gap-fill reply was not an object")
        except ClaudeError as e:
            status, obj = f"error: {e}", {}
        events, dis = obj.get("events"), obj.get("disruptions")
        kept = 0
        for raw in events if isinstance(events, list) else []:
            ev = validate_event(raw, set(days), names)
            if ev is None:
                continue
            c = event_to_candidate(ev, t)
            if _overlaps(c, pool):
                continue
            if kept >= cw["gapfill_max_events"]:
                log.warning("gap-fill event cap reached; dropping the rest")
                break
            if not _alive(alive, ev["source_url"]):
                log.info("gap-fill event dropped, dead link: %s", ev["name"])
                continue
            store[c.id] = {"event": ev, "seen": today.isoformat()}
            pool.append(c)
            kept += 1
        if status == "ok":
            cache["gapfill_ran"] = today.isoformat()
            cache["disruptions"] = ([d for d in (validate_disruption(x, set(days), names) for x in dis) if d]
                                    if isinstance(dis, list) else [])
    disruptions = [d for d in cache.get("disruptions", []) if d["date"] >= today.isoformat()]
    return [c for c in cached() if not _overlaps(c, existing)], disruptions, status
