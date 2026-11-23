import logging
import re
from collections.abc import Callable
from datetime import date

from taxi.claude import ClaudeError, extract_json
from taxi.model import Candidate, exit_after

log = logging.getLogger(__name__)

EST_KEYS = ("median_age", "age_lo", "age_hi", "size", "pays", "spend", "exit", "wait", "desc")
_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _num(v, lo, hi) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def _int(v, lo, hi) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _text(v, n) -> bool:
    return isinstance(v, str) and 1 <= len(v) <= n


def validate_estimate(obj: dict) -> dict | None:
    if not isinstance(obj, dict) or any(k not in obj for k in EST_KEYS):
        return None
    ok = (_num(obj["median_age"], 5, 95) and _int(obj["age_lo"], 0, 100) and _int(obj["age_hi"], 0, 100)
          and obj["age_lo"] <= obj["median_age"] <= obj["age_hi"] and _int(obj["size"], 20, 150000)
          and _num(obj["pays"], 0, 1) and _num(obj["spend"], 0, 1)
          and isinstance(obj["exit"], str) and bool(_HM.match(obj["exit"]))
          and _text(obj["wait"], 120) and _text(obj["desc"], 200))
    return {k: obj[k] for k in EST_KEYS} if ok else None


def apply_estimate(c: Candidate, e: dict) -> None:
    for k in EST_KEYS:
        if k != "exit":
            setattr(c, k, e[k])
    c.exit = exit_after(c.start, e["exit"])


def estimate_prompt(events: list[Candidate], language: str) -> str:
    lines = "\n".join(f"{c.id} | {c.name} | {c.venue} | {c.start:%Y-%m-%d %H:%M} | {c.info}" for c in events)
    return (
        "Estimate the crowd for each of these Sydney events, for a taxi driver deciding where to be.\n"
        "One event per line as: id | name | venue | YYYY-MM-DD HH:MM | info\n\n"
        f"{lines}\n\n"
        "Reply with a bare JSON array (no prose, no code fence) of objects, one per event, each with the keys "
        f"\"id\" and {', '.join(f'\"{k}\"' for k in EST_KEYS)}:\n"
        "- median_age, age_lo, age_hi: typical age of the crowd (age_lo <= median_age <= age_hi)\n"
        "- size: expected attendance\n"
        "- pays: share of the crowd whose taxi an employer or company pays, 0 to 1\n"
        "- spend: spending power of the crowd, 0 to 1\n"
        "- exit: the local time (HH:MM, 24 hour) most of the crowd leaves\n"
        "- wait: the best nearby place for a taxi to wait\n"
        "- desc: one plain sentence for a taxi driver\n"
        "Calibration: an Opera House opera is about 2000 people aged 50 to 70 (pays 0.15, spend 1.0); "
        "an Olympic Park rave is young, about 22 (pays 0, spend 0.15); "
        "pays is near 0 for public concerts and sport, high only for corporate crowds.\n"
        f"Write wait and desc in {language}. Estimate only the events listed and never add others."
    )


def _ask(call, events, language, got: dict) -> None:
    """One call; validated items for the listed events are added to `got`."""
    wanted = {c.id for c in events}
    items = extract_json(call(estimate_prompt(events, language)))
    for item in items if isinstance(items, list) else []:
        e = validate_estimate(item) if isinstance(item, dict) else None
        if e and isinstance(item.get("id"), str) and item["id"] in wanted:
            got[item["id"]] = e


def estimate_events(events: list[Candidate], cache: dict, call: Callable[[str], str] | None, w: dict,
                    today: date, language: str) -> tuple[list[Candidate], str]:
    store = cache["estimates"]
    todo = sorted((c for c in events if c.id not in store), key=lambda c: c.start)
    status = "ok"
    cap = w["claude"]["estimate_batch_max"]
    if len(todo) > cap:
        log.warning("estimate batch capped: dropping %d events for today", len(todo) - cap)
        todo = todo[:cap]
    if call is None:
        status = "skipped"
    elif todo:
        got: dict = {}
        try:
            _ask(call, todo, language, got)
            missing = [c for c in todo if c.id not in got]
            if missing:
                _ask(call, missing, language, got)
        except ClaudeError as e:
            status = f"error: {e}"
        if not got and status == "ok":
            status = "error: no valid estimates"
        for i, e in got.items():
            store[i] = {"est": e, "seen": today.isoformat()}
    done = []
    for c in events:
        if c.id in store:
            store[c.id]["seen"] = today.isoformat()
            apply_estimate(c, store[c.id]["est"])
            done.append(c)
        elif c.id in {t.id for t in todo}:
            log.info("no estimate for %s; dropped", c.id)
    return done, status
