import json
import logging
import time
from datetime import datetime, time as dtime, timedelta, timezone
from urllib.parse import urlencode

from taxi.drive import nearest_area
from taxi.model import SYD, Candidate
from taxi.net import clean

API = "https://app.ticketmaster.com/discovery/v2/events.json"
SYDNEY_LATLONG = "-33.8688,151.2093"
PAGE_SIZE = 200
PAGE_SLEEP_S = 0.25  # Discovery API rate limit is 5 requests/s
RANGE_END_HOUR = 3  # include the small hours after the last shift day
DEAD_STATUS = ("cancelled", "canceled", "postponed")  # API docs spell it "canceled"
log = logging.getLogger(__name__)
SKIP_FROM, SKIP_TO = "03:00", "10:00"  # start times in [03:00, 10:00) are morning shows, not shift crowds


def _utc(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_events(key, days, get_text, w):
    first = datetime.combine(min(days), dtime(0, 0), tzinfo=SYD)
    last = datetime.combine(max(days) + timedelta(days=1), dtime(RANGE_END_HOUR, 0), tzinfo=SYD)
    cfg, events, page, pages = w["ticketmaster"], [], 0, 1
    while page < min(pages, cfg["max_pages"]):
        q = urlencode({"apikey": key, "latlong": SYDNEY_LATLONG, "radius": cfg["radius_km"], "unit": "km",
                       "countryCode": "AU", "size": PAGE_SIZE, "sort": "date,asc",
                       "startDateTime": _utc(first), "endDateTime": _utc(last), "page": page}, safe=",:")
        try:
            data = json.loads(get_text(f"{API}?{q}"))
        except Exception as e:
            if page == 0:
                raise
            log.warning("ticketmaster: page %d failed, keeping %d earlier events (%s)", page, len(events), clean(str(e)))
            break
        events += data.get("_embedded", {}).get("events", [])
        pages = data.get("page", {}).get("totalPages", 1)
        page += 1
        if page < min(pages, cfg["max_pages"]):
            time.sleep(PAGE_SLEEP_S)
    return events


def _candidate(e, t, w, seen):
    start = e["dates"]["start"]
    lt = start.get("localTime")
    if (not lt or start.get("timeTBA") or start.get("noSpecificTime") or SKIP_FROM <= lt[:5] < SKIP_TO
            or e["dates"].get("status", {}).get("code", "").lower() in DEAD_STATUS):
        return None
    v = e["_embedded"]["venues"][0]
    lat, lon = float(v["location"]["latitude"]), float(v["location"]["longitude"])
    area = nearest_area(t, lat, lon, w["plan"]["area_max_km"])
    key = (v["name"], start["localDate"], lt)
    if area is None or key in seen:
        return None
    c0 = (e.get("classifications") or [{}])[0]
    info = f'{c0.get("segment", {}).get("name", "")} / {c0.get("genre", {}).get("name", "")}'
    pr = (e.get("priceRanges") or [None])[0]
    if pr:
        info += f' · ${pr["min"]:.0f}–{pr.get("max", pr["min"]):.0f}'
    d = datetime.strptime(f'{start["localDate"]} {lt[:5]}', "%Y-%m-%d %H:%M").replace(tzinfo=SYD)
    c = Candidate(id=f'tm:{e["id"]}', kind="event", name=e["name"], venue=v["name"],
                  address=f'{v["address"]["line1"]}, {v["city"]["name"]}', area=area, lat=lat, lon=lon,
                  source_url=e["url"], start=d, info=info)
    seen.add(key)
    return c


def to_candidates(events, t, w):
    skip = [s.lower() for s in w["ticketmaster"]["skip_words"]]
    out, seen = [], set()
    for e in events:
        try:
            if any(s in e["name"].lower() for s in skip):
                continue
            c = _candidate(e, t, w, seen)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as ex:
            log.warning("ticketmaster: skipped malformed event %s (%s)", e.get("id") if isinstance(e, dict) else "?", type(ex).__name__)
            continue
        if c:
            out.append(c)
    return out
