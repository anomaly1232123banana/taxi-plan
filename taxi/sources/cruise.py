import logging
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

from taxi.model import SYD, Candidate, at_shift, fmt12, slug
from taxi.net import SourceError

CRUISE_URL = "https://www.portauthoritynsw.com.au/cruise/cruise-schedule/"
MAX_DAYS_AWAY = 180  # the page omits the year; take the one that lands within this many days of today
FIELDS = {"views-field-vessel-name": "ship", "views-field-departure-time": "when", "views-field-berth": "berth"}
log = logging.getLogger(__name__)


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._field = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = {}
        elif tag == "td" and self._row is not None:
            cls = (dict(attrs).get("class") or "").split()
            self._field = next((FIELDS[c] for c in cls if c in FIELDS), None)
            if self._field:
                self._row[self._field] = []

    def handle_data(self, data):
        if self._row is not None and self._field:
            self._row[self._field].append(data.strip())

    def handle_endtag(self, tag):
        if tag == "td":
            self._field = None
        elif tag == "tr" and self._row is not None:
            if set(self._row) == set(FIELDS.values()):
                self.rows.append({k: " ".join(p for p in v if p) for k, v in self._row.items()})
            self._row = None


def _departure(text: str, today: date) -> datetime:
    parts = text.split()  # "Mon 23 Nov 18:00"
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            dt = datetime.strptime(f"{parts[1]} {parts[2]} {year} {parts[3]}", "%d %b %Y %H:%M").replace(tzinfo=SYD)
        except ValueError:
            continue
        gap = abs((dt.date() - today).days)
        if gap <= MAX_DAYS_AWAY and (best is None or gap < best[0]):
            best = (gap, dt)
    if best is None:
        raise SourceError(f"cruise: bad date {text!r}")
    return best[1]


def parse_schedule(html: str, today: date) -> list[dict]:
    p = _Rows()
    p.feed(html)
    if not p.rows:
        raise SourceError("cruise: no rows")
    return [{"ship": r["ship"], "departure": _departure(r["when"], today), "berth": r["berth"]} for r in p.rows]


def fetch_departures(get_text, today: date) -> list[dict]:
    deps = parse_schedule(get_text(CRUISE_URL), today)
    try:
        deps += parse_schedule(get_text(CRUISE_URL + "?page=1"), today)
    except SourceError as e:
        log.warning("cruise page 2 ignored: %s", e)
    seen, out = set(), []
    for d in deps:
        k = (d["ship"], d["departure"])
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


def boarding_candidates(deps, days, w, S) -> list[Candidate]:
    cfg, out = w["cruise"], []
    for d in deps:
        dep, hm = d["departure"], d["departure"].strftime("%H:%M")
        if dep.date() not in days or hm < cfg["min_departure"]:
            continue
        term = cfg["terminals"].get(d["berth"])
        if term is None:
            log.warning("cruise: unknown berth %r for %s, skipped", d["berth"], d["ship"])
            continue
        out.append(Candidate(
            id=f'cruise:{slug(d["ship"])}:{dep.date().isoformat()}', kind="cruise",
            name=S["cruise_name"].format(ship=d["ship"]), venue=d["berth"], address=term["address"], area=term["area"],
            lat=term["lat"], lon=term["lon"], source_url=CRUISE_URL, exit=at_shift(dep.date(), cfg["exit"]),
            size=cfg["size"], median_age=cfg["median_age"], age_lo=cfg["age_lo"], age_hi=cfg["age_hi"],
            pays=cfg["pays"], spend=cfg["spend"],
            desc=S["cruise_desc"].format(time=fmt12(hm, S), terminal=d["berth"]),
            wait=S["cruise_wait"].format(terminal=d["berth"])))
    return out
