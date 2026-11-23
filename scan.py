"""Daily scan: collect, estimate, gap-fill, score, plan, write, publish."""
import argparse
import json
import logging
import os
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

from taxi import cache as cache_mod, claude, data, estimate as est_mod, gapfill as gf_mod, net, plan as planner, publish as pub_mod
from taxi.model import SYD, shift_date, shift_slot, working_days
from taxi.score import score_candidate
from taxi.sources import cruise, offices as office_src, ticketmaster, weather

log = logging.getLogger("scan")

ERR_MAX = 120
LOG_FILE = "scan.log"
SECRET_ENV = {"ticketmaster_key": "TICKETMASTER_KEY", "claude_oauth_token": "CLAUDE_CODE_OAUTH_TOKEN"}


def load_secrets(root: Path) -> dict:
    try:
        file = json.loads((root / "secrets.json").read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        file = {}
    except (OSError, ValueError) as e:
        log.warning("secrets.json unreadable (%s); ignoring it", type(e).__name__)
        file = {}
    file = file if isinstance(file, dict) else {}
    return {k: os.environ.get(env) or file.get(k) or "" for k, env in SECRET_ENV.items()}


def _err(e: Exception) -> str:
    return "error: " + net.clean(str(e))[:ERR_MAX]  # strips URL query strings (API key) and local paths


def run(now: datetime, root: Path, get_text=None, call_claude=None, publish_fn=None,
        use_claude: bool = True, do_publish: bool = True) -> dict:
    get_text = get_text or net.get_text
    publish_fn = publish_fn or pub_mod.publish
    secrets = load_secrets(root)
    if call_claude is None:
        def call_claude(prompt, args, timeout):
            return claude.run_claude(prompt, args, timeout, token=secrets["claude_oauth_token"] or None)

    w = data.load_weights(root / "weights.json")
    S = data.load_strings(root / "site" / "strings.json")
    t = data.load_areas(root / "data" / "areas.json")
    areas = set(t["areas"])
    office_rows = data.load_offices(root / "data" / "offices.json", areas)
    steady = data.load_steady(root / "data" / "steady.json", areas)
    venues = data.load_venues(root / "data" / "gapfill_venues.json", areas)
    today = shift_date(now)  # a scan at 01:30 still serves the shift that began the day before
    days = working_days(today)
    cache_path = root / "cache" / "estimates.json"
    cache = cache_mod.load_cache(cache_path)
    cw, language = w["claude"], S["_prompt_language"]

    sources: dict[str, str] = {}
    results: dict[str, object] = {}

    def collect(name, fn):
        try:
            results[name] = fn()
            sources[name] = "ok"
            log.info("%s: ok, %d candidates", name, len(results[name]))
        except Exception as e:
            results[name], sources[name] = [], _err(e)
            log.warning("%s: %s", name, sources[name])

    def tm():
        if not secrets["ticketmaster_key"]:
            raise RuntimeError("no Ticketmaster key")
        return ticketmaster.to_candidates(ticketmaster.fetch_events(secrets["ticketmaster_key"], days, get_text, w), t, w)

    collect("ticketmaster", tm)
    collect("cruise", lambda: cruise.boarding_candidates(cruise.fetch_departures(get_text, today), days, w, S))
    collect("offices", lambda: office_src.office_candidates(office_rows, days, w, S))
    collect("weather", lambda: weather.fetch_rain(get_text, w))
    rain = results["weather"] or set()

    est_call = gf_call = None
    if use_claude:
        est_call = lambda p: call_claude(p, claude.claude_args([], cw["estimate_max_turns"]), cw["estimate_timeout_s"])
        gf_call = lambda p: call_claude(p, claude.claude_args(["WebSearch", "WebFetch"], cw["gapfill_max_turns"]),
                                        cw["gapfill_timeout_s"])

    tm_cands = results["ticketmaster"]
    try:
        tm_est, sources["estimate"] = est_mod.estimate_events(tm_cands, cache, est_call, w, today, language)
    except Exception as e:  # events without an estimate are dropped: scoring them would crash
        tm_est, sources["estimate"] = [], _err(e)
        log.warning("estimate: %s", sources["estimate"])
    log.info("estimate: %s, %d of %d events", sources["estimate"], len(tm_est), len(tm_cands))
    try:
        gf_cands, disruptions, sources["gapfill"] = gf_mod.gapfill(gf_call, venues, days, tm_cands, t, cache, today, w,
                                                                   language, net.url_alive)
    except Exception as e:
        gf_cands, disruptions, sources["gapfill"] = [], [], _err(e)
        log.warning("gapfill: %s", sources["gapfill"])
    log.info("gapfill: %s, %d events, %d disruptions", sources["gapfill"], len(gf_cands), len(disruptions))

    try:
        cache_mod.prune(cache, today, w["cache_keep_days"])
        cache_mod.save_cache(cache, cache_path)
    except Exception as e:  # a locked OneDrive file must not lose the plan
        log.warning("estimate cache not pruned or saved: %s", net.clean(str(e)))

    by_day: dict[date, list] = {d: [] for d in days}
    for c in tm_est + gf_cands + results["cruise"] + results["offices"]:
        slot = shift_slot(c.exit)
        if slot and slot[0] in by_day:
            score_candidate(c, w, rain, disruptions)
            by_day[slot[0]].append(c)

    sources = {k: net.clean(v)[:ERR_MAX] for k, v in sources.items()}
    # a weather error alone stays "ok": rain is only a score boost, a red header would cry wolf
    healthy = (sources["ticketmaster"] == "ok" and sources["estimate"] == "ok" and sources["cruise"] == "ok"
               and not sources["gapfill"].startswith("error"))
    plan = {"schema": 1, "generated_at": now.isoformat(timespec="seconds"), "status": "ok" if healthy else "partial", "sources": sources,
            "days": [{"date": d.isoformat(), "entries": planner.plan_day(by_day[d], steady, t, w)} for d in days]}
    pub_mod.write_plan(plan, root / "site" / "plan.json")
    if do_publish:
        result = publish_fn(root, today)
        log.info("publish: %s", result)
        if result.startswith("error"):
            raise RuntimeError("publish failed: " + result)  # plan is written; exit non-zero so the scheduler retries
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-claude", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    a = ap.parse_args(argv)
    (a.root / "logs").mkdir(exist_ok=True)
    handler = logging.FileHandler(a.root / "logs" / LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    top = logging.getLogger()
    old_level = top.level
    top.addHandler(handler)
    top.setLevel(logging.INFO)
    try:
        run(datetime.now(SYD), a.root, use_claude=not a.no_claude, do_publish=not a.no_publish)
        return 0
    except Exception:
        log.error("scan failed:\n%s", net.clean(traceback.format_exc()))
        return 1
    finally:
        top.removeHandler(handler)
        top.setLevel(old_level)
        handler.close()


if __name__ == "__main__":
    sys.exit(main())
