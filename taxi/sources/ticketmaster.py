import json
import time
from datetime import datetime, time as dtime, timedelta, timezone
from urllib.parse import urlencode

from taxi.drive import nearest_area
from taxi.model import SYD, Candidate

API = "https://app.ticketmaster.com/discovery/v2/events.json"
SYDNEY_LATLONG = "-33.8688,151.2093"
PAGE_SIZE = 200
PAGE_SLEEP_S = 0.25  # Discovery API rate limit is 5 requests/s
RANGE_END_HOUR = 3  # include the small hours after the last shift day
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
        data = json.loads(get_text(f"{API}?{q}"))
        events += data.get("_embedded", {}).get("events", [])
        pages = data.get("page", {}).get("totalPages", 1)
        page += 1
        if page < min(pages, cfg["max_pages"]):
            time.sleep(PAGE_SLEEP_S)
    return events


def to_candidates(events, t, w):
    skip = [s.lower() for s in w["ticketmaster"]["skip_words"]]
    out, seen = [], set()
    for e in events:
        start = e["dates"]["start"]
        lt = start.get("localTime")
        if not lt or any(s in e["name"].lower() for s in skip) or SKIP_FROM <= lt[:5] < SKIP_TO:
            continue
        v = e["_embedded"]["venues"][0]
        loc = v.get("location") or {}
        if "latitude" not in loc:
            continue
        lat, lon = float(loc["latitude"]), float(loc["longitude"])
        area = nearest_area(t, lat, lon, w["plan"]["area_max_km"])
        key = (v["name"], start["localDate"], lt)
        if area is None or key in seen:
            continue
        seen.add(key)
        c0 = (e.get("classifications") or [{}])[0]
        info = f'{c0.get("segment", {}).get("name", "")} / {c0.get("genre", {}).get("name", "")}'
        pr = (e.get("priceRanges") or [None])[0]
        if pr:
            info += f' · ${pr["min"]:.0f}–{pr.get("max", pr["min"]):.0f}'
        d = datetime.strptime(f'{start["localDate"]} {lt[:5]}', "%Y-%m-%d %H:%M").replace(tzinfo=SYD)
        out.append(Candidate(id=f'tm:{e["id"]}', kind="event", name=e["name"], venue=v["name"],
                             address=f'{v["address"]["line1"]}, {v["city"]["name"]}', area=area, lat=lat, lon=lon,
                             source_url=e["url"], start=d, info=info))
    return out
