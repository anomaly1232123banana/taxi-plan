# Taxi Plan Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily 10:00 scan on the owner's Windows laptop that turns free event feeds, researched fixed lists and a few capped Claude estimates into a 5-working-day taxi plan, published as a phone page on GitHub Pages.

**Architecture:** `scan.py` runs a fixed pipeline (collect → estimate → gapfill → score → plan → write → publish) from small modules in the `taxi/` package; Claude is used only through the headless `claude -p` CLI, at most three calls a day (one batched estimate, one retry of that estimate, one capped gap-fill), with estimates cached by candidate id. Scoring and the itinerary are plain, deterministic Python. The page in `site/` is static HTML/CSS/JS that reads `site/plan.json`, deployed to GitHub Pages by a GitHub Actions workflow on every push.

**Tech Stack:** Python 3.13 standard library (urllib, json, html.parser, subprocess, unittest, zoneinfo) + `tzdata`; plain HTML/CSS/JS; Node 24 only to run `node --test` on the page logic; git + Git Credential Manager; Windows Task Scheduler; GitHub Pages via Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-taxi-dashboard-design.md`

## Global Constraints

- Python 3.13, standard library only, plus `tzdata` (Windows Python has no IANA database; `ZoneInfo("Australia/Sydney")` needs it). `requirements.txt` holds exactly `tzdata>=2024.1`. No other pip packages.
- Frontend: plain HTML, CSS and JS. No framework, no build step, no npm dependencies, no `package.json`. JS tests use only `node:test` and `node:assert`.
- All times are **Australia/Sydney**, including daylight saving. Use `taxi.model.SYD`; never use naive datetimes in logic.
- "Shift minutes" = minutes since 12:00 on the shift date, 0–900 (12 pm = 0, 3 am next day = 900). Blocks: `[0,120) [120,240) [240,360) [360,480) [480,600) [600,720) [720,840) [840,900]` (last block includes 900).
- He works Monday to Saturday; nothing on a Sunday's shift. An exit between 00:00 and 03:00 belongs to the previous calendar day's shift.
- Claude is called only via the headless CLI on the subscription: `claude -p --model sonnet --output-format json …` with the exact flags in Task 6, the prompt on stdin, `encoding="utf-8"`, and a timeout. No Anthropic API key, no SDK. **Tests never run the real `claude`** — they inject a fake or patch `taxi.claude.subprocess.run`.
- The repo is public. Nothing personal or secret is committed: `secrets.json` (Ticketmaster key, Claude token) is gitignored, env vars `TICKETMASTER_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` override it, the repo-local git identity is a placeholder, and no committed file contains an absolute user path, a name, a phone number or an address of a person.
- Error messages that reach `plan.json` or logs never contain a URL query string (the Ticketmaster key travels in one).
- All UI text lives in `site/strings.json` under a language key (`"en"` now; `"zh"` later is a new sibling object). No UI copy is hard-coded in JS, HTML or Python; Python reads the few templates it needs from the same file.
- Tunable numbers live in `weights.json`; code reads them from there instead of repeating them.
- Each source failure is caught, logged and recorded in `plan.json.sources`; it never stops the scan. If the scan itself fails, the old `site/plan.json` is left untouched.
- Fixed researched lists live in `data/*.json`, each with top-level `"estimate": true` and `"researched": "YYYY-MM-DD"`.
- Network: `urllib` with a 20 s timeout and User-Agent `Mozilla/5.0 (compatible; taxi-plan/1.0)`.
- Commands: Python tests `python -m unittest discover -s tests -t . -v`; one module `python -m unittest tests.test_<name> -v`; JS tests `node --test "tests/js/*.test.js"`.
- Commit after each task with a conventional message (`feat:`, `test:`, `data:`, `chore:`).

## Review Focus

1. Claude CLI fails (auth expired, `is_error: true` with `subtype: "success"`, max turns hit, timeout, prose or fenced JSON instead of bare JSON) → the scan still writes a plan from the other sources, marks `status: "partial"`, and the page header turns red. Tests: Task 6 runner tests, Task 14 `test_claude_failure_marks_partial`.
2. The phone stays open in the cradle across a block boundary or midnight → Go Now and the header move on within a minute without a reload, and cards he opened stay open. Tests: Task 16 `go now moves with the clock`, Task 15 `locateNow` cases; `app.js` re-renders every 60 s.
3. Ticketmaster junk (parking passes, VIP packages, duplicate listings for the same show, TBA times, morning kids' shows, venues outside Sydney) → dropped before the Claude estimate, so they waste no tokens and never become fake crowds. Test: Task 9 `test_to_candidates_filters_junk`.
4. Claude-written text (desc, wait, names) containing `<`, `&` or quotes → shown literally on the page, never as markup. Test: Task 16 `escapes Claude text`.
5. A Ticketmaster HTTP error → the API key never appears in `plan.json` (public) or logs. Test: Task 9 `test_error_message_hides_query`.

## File Structure

| Path | Responsibility |
|---|---|
| `scan.py` | Entry point and pipeline orchestration (`run`, `main`, `load_secrets`) |
| `run_scan.cmd` | Wrapper that Task Scheduler runs |
| `weights.json` | Score weights and every other tunable number |
| `requirements.txt`, `.gitignore`, `secrets.example.json` | Setup |
| `taxi/model.py` | `Candidate`, `SYD`, shift/block/time helpers, `slug` |
| `taxi/data.py` | Load and validate `weights.json`, `site/strings.json`, `data/*.json` |
| `taxi/score.py` | Taxi Score |
| `taxi/drive.py` | Drive times, nearest area, distance |
| `taxi/plan.py` | Itinerary optimiser, quiet blocks, fallbacks |
| `taxi/claude.py` | Headless CLI runner and JSON extraction |
| `taxi/cache.py` | `cache/estimates.json` load/save/prune |
| `taxi/estimate.py` | Batched estimate call, validation, retry |
| `taxi/gapfill.py` | Capped gap-fill call (venues, races, trackwork/strikes) |
| `taxi/net.py` | HTTP helpers, `SourceError` |
| `taxi/sources/ticketmaster.py`, `cruise.py`, `weather.py`, `offices.py` | Sources |
| `taxi/publish.py` | Atomic write of `plan.json`, git commit + push |
| `data/areas.json`, `offices.json`, `steady.json`, `gapfill_venues.json` | Researched fixed lists (estimates) |
| `site/index.html`, `style.css`, `strings.json`, `plan-view.js`, `app.js`, `sw.js`, `manifest.webmanifest`, `icon.svg`, `plan.json` | Phone page |
| `.github/workflows/pages.yml` | Deploys `site/` to GitHub Pages |
| `tests/…` | `unittest` tests, fixtures, `tests/js/*.test.js` |
| `cache/`, `logs/`, `secrets.json` | Local only, gitignored |

## Shared Shapes

**`Candidate`** (`taxi/model.py`, a `@dataclass`):

```python
id: str; kind: str            # "event" | "race" | "office" | "cruise"
name: str; venue: str; address: str
area: str | None; lat: float | None; lon: float | None
source_url: str
start: datetime | None = None; exit: datetime | None = None   # aware, SYD
info: str = ""               # listing facts for the estimate prompt
size: int | None = None; median_age: float | None = None
age_lo: int | None = None; age_hi: int | None = None
pays: float | None = None; spend: float | None = None
wait: str = ""; desc: str = ""; score: int = 0
```

IDs: `tm:<ticketmaster id>`, `office:<office id>:normal|late:<YYYY-MM-DD>`, `cruise:<slug(ship)>:<YYYY-MM-DD>`, `gf:<slug(venue-date-name)[:80]>`.

**Area table `t`** (returned by `taxi.data.parse_areas`): `{"areas": {name: (lat, lon)}, "minutes": {(a, b): int}` (both orders), `"same_area_min": int, "peak": (start_min, end_min, factor), "late": (start_min, factor)}` with peak/late already in shift minutes.

**`site/plan.json`**:

```json
{"schema": 1, "generated_at": "2026-11-23T10:02:13+11:00", "status": "ok | partial",
 "sources": {"ticketmaster": "ok", "cruise": "error: …", "weather": "ok", "offices": "ok", "estimate": "ok", "gapfill": "ok"},
 "days": [{"date": "2026-11-23", "entries": [Entry, …]}]}
```

Entries of a day cover shift minutes 0–900 with no gaps, in order. Two kinds:

```json
{"type": "stop", "block": [240, 360], "id": "…", "kind": "office", "name": "…", "score": 60,
 "exit": "17:30", "start": "19:30 | null", "desc": "…", "address": "…", "lat": -33.86, "lon": 151.2,
 "size": 3000, "age_lo": 30, "age_hi": 55, "wait": "…", "drive_min": 6, "drive_from": "KPMG | null", "url": "…"}
{"type": "quiet", "block": [360, 600], "until": "22:00 | null", "next": "Opera House | null", "nearby": ["The Star", "…"]}
```

`drive_from: null` means "from the CBD". Times are local Sydney `"HH:MM"`.

**`cache/estimates.json`**: `{"estimates": {id: {"est": {…estimate fields…}, "seen": "YYYY-MM-DD"}}, "gapfill": {id: {"event": {…validated gap-fill event…}, "seen": "YYYY-MM-DD"}}}`.

**Estimate fields** (`EST_KEYS`): `median_age` (number 5–95), `age_lo`, `age_hi` (int 0–100, `age_lo ≤ median_age ≤ age_hi`), `size` (int 20–150000), `pays`, `spend` (number 0–1), `exit` (`"HH:MM"`), `wait` (str 1–120 chars), `desc` (str 1–200 chars).

---

### Task 1: Repo scaffold and time model

**Files:**
- Create: `.gitignore`, `requirements.txt`, `secrets.example.json`, `taxi/__init__.py`, `taxi/sources/__init__.py`, `taxi/model.py`
- Test: `tests/__init__.py`, `tests/helpers.py`, `tests/test_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SYD`; `BLOCKS: list[tuple[int, int]]`; `Candidate`; `shift_slot(t: datetime) -> tuple[date, int] | None`; `block_index(minute: int) -> int`; `working_days(start: date, n: int = 5) -> list[date]`; `at_shift(d: date, hm: str) -> datetime`; `exit_after(start: datetime, hm: str) -> datetime`; `shift_minute(hm: str) -> int`; `hm_of(minute: int) -> str`; `fmt12(hm: str, S: dict) -> str`; `slug(s: str) -> str`. `tests.helpers.cand(**kw) -> Candidate`.

- [ ] **Step 1: Initialise git with a placeholder identity**

```bash
git init -b main
git config user.name "taxi-plan"
git config user.email "taxi-plan@users.noreply.github.com"
```

Run: `git config user.email` → Expected: `taxi-plan@users.noreply.github.com` (repo-local, so no personal email reaches the public history).

- [ ] **Step 2: Write `.gitignore`, `requirements.txt`, `secrets.example.json`, install**

`.gitignore`:
```
.superpowers/
cache/
logs/
secrets.json
__pycache__/
*.pyc
*.tmp
```
`requirements.txt`: `tzdata>=2024.1`. `secrets.example.json`: `{"ticketmaster_key": "", "claude_oauth_token": ""}`.

Run: `python -m pip install -r requirements.txt` → Expected: tzdata installed or "already satisfied".

- [ ] **Step 3: Write the failing tests** in `tests/test_model.py` (`tests/helpers.py`: `cand(**kw)` builds a `Candidate` with defaults `id="x", kind="event", name="X", venue="V", address="A", area="CBD", lat=-33.8688, lon=151.2093, source_url="https://example.com"`, overridden by `kw`).

```python
def dt(*a): return datetime(*a, tzinfo=SYD)
class TestModel(unittest.TestCase):
    def test_shift_slot(self):
        self.assertEqual(shift_slot(dt(2026,11,23,22,15)), (date(2026,11,23), 615))
        self.assertEqual(shift_slot(dt(2026,11,24,1,0)), (date(2026,11,23), 780))
        self.assertEqual(shift_slot(dt(2026,11,24,3,0)), (date(2026,11,23), 900))
        self.assertIsNone(shift_slot(dt(2026,11,24,3,1)))
        self.assertIsNone(shift_slot(dt(2026,11,23,11,59)))
        self.assertEqual(shift_slot(dt(2026,11,23,12,0)), (date(2026,11,23), 0))
        self.assertEqual(shift_slot(datetime(2026,11,23,11,15,tzinfo=timezone.utc)), (date(2026,11,23), 615))
    def test_sunday_rule(self):
        self.assertEqual(shift_slot(dt(2026,11,29,1,0)), (date(2026,11,28), 780))  # Sun 1am = Saturday shift
        self.assertIsNone(shift_slot(dt(2026,11,29,20,0)))                          # Sunday shift
        self.assertIsNone(shift_slot(dt(2026,11,30,1,0)))                           # Mon 1am = Sunday shift
    def test_dst_days(self):
        self.assertEqual(shift_slot(dt(2026,10,4,1,30)), (date(2026,10,3), 810))
        self.assertEqual(shift_slot(dt(2026,4,5,1,30)), (date(2026,4,4), 810))
    def test_block_index(self):
        self.assertEqual([block_index(m) for m in (0,119,120,615,839,840,900)], [0,0,1,5,6,7,7])
    def test_working_days(self):
        self.assertEqual(working_days(date(2026,11,23)), [date(2026,11,d) for d in (23,24,25,26,27)])
        self.assertEqual(working_days(date(2026,11,26)), [date(2026,11,26),date(2026,11,27),date(2026,11,28),date(2026,11,30),date(2026,12,1)])
        self.assertEqual(working_days(date(2026,11,29)), [date(2026,11,30)] + [date(2026,12,d) for d in (1,2,3,4)])
    def test_time_helpers(self):
        self.assertEqual(at_shift(date(2026,11,23), "17:30"), dt(2026,11,23,17,30))
        self.assertEqual(at_shift(date(2026,11,23), "01:00"), dt(2026,11,24,1,0))
        self.assertEqual(exit_after(dt(2026,11,23,19,30), "22:15"), dt(2026,11,23,22,15))
        self.assertEqual(exit_after(dt(2026,11,23,19,30), "01:00"), dt(2026,11,24,1,0))
        self.assertEqual(exit_after(dt(2026,11,23,10,0), "11:30"), dt(2026,11,23,11,30))
        self.assertEqual([shift_minute(h) for h in ("12:00","02:00","03:00","23:00")], [0,840,900,660])
        self.assertEqual((hm_of(615), hm_of(780)), ("22:15", "01:00"))
        S = {"am": "am", "pm": "pm"}
        self.assertEqual([fmt12(h, S) for h in ("18:00","16:45","00:00","12:30")], ["6pm","4:45pm","12am","12:30pm"])
        self.assertEqual(slug("Anthem of the Seas"), "anthem-of-the-seas")
        self.assertEqual(slug("ICC Sydney – Day 1!"), "icc-sydney-day-1")
```

- [ ] **Step 4: Run to verify it fails**

Run: `python -m unittest tests.test_model -v` → Expected: FAIL / ImportError (`taxi.model` missing).

- [ ] **Step 5: Implement `taxi/model.py`**

`SYD = ZoneInfo("Australia/Sydney")`; `shift_slot` converts to SYD first, maps 12:00–23:59 to the same date and 00:00–03:00 to the previous date (minute 720 + h·60 + m), returns `None` outside that or when the shift date is a Sunday. `at_shift` puts times before 12:00 on the next calendar day; `exit_after` uses the start's date and adds a day if the result is before `start`. `shift_minute(hm) = ((h*60+m) - 720) % 1440`. `fmt12` drops `:00`. `slug`: lowercase, runs of non-`[a-z0-9]` → `-`, strip `-`.

- [ ] **Step 6: Run to verify it passes**

Run: `python -m unittest tests.test_model -v` → Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add .gitignore requirements.txt secrets.example.json taxi tests docs
git commit -m "chore: scaffold repo and add Sydney shift time model"
```

---

### Task 2: Data loaders, `weights.json`, `site/strings.json`

**Files:**
- Create: `taxi/data.py`, `weights.json`, `site/strings.json`
- Modify: `tests/helpers.py` (add `AREAS_JSON`, `TABLE`, `W`, `S`)
- Test: `tests/test_data.py`

**Interfaces:**
- Consumes: `taxi.model.shift_minute`.
- Produces: `DataError(Exception)`; `load_json(path) -> Any`; `parse_areas(obj: dict) -> dict` (shape `t`); `load_areas(path) -> dict`; `load_offices(path, area_names: set[str]) -> list[dict]`; `load_steady(path, area_names) -> list[dict]`; `load_venues(path, area_names) -> list[dict]`; `load_weights(path) -> dict`; `load_strings(path, lang: str | None = None) -> dict` (returns the language object; default lang = file's `"lang"`). `tests.helpers`: `AREAS_JSON` (dict below), `TABLE = parse_areas(AREAS_JSON)`, `W = load_weights("weights.json")`, `S = load_strings("site/strings.json")`.

- [ ] **Step 1: Write `weights.json`** (exact):

```json
{
 "points": {"age": 35, "pays": 25, "size": 20, "spend": 10, "late": 10},
 "age_curve": [[22, 0.1], [30, 0.25], [40, 0.55], [45, 0.85], [50, 1.0]],
 "size": {"zero_at": 200, "full_at": 80000},
 "late": {"full_from": "22:00", "half_from": "21:00"},
 "boost": {"rain": 1.15, "disruption": 1.2},
 "rain": {"min_mm": 0.5, "min_prob": 60},
 "plan": {"big_threshold": 40, "far_minutes": 30, "far_threshold": 55, "load_minutes": 25, "fallbacks": 3, "area_max_km": 12},
 "office": {"late_crowd_share": 0.2, "late_pays": 1.0},
 "cruise": {"exit": "13:00", "min_departure": "14:00", "size": 3000, "median_age": 55, "age_lo": 45, "age_hi": 75, "pays": 0.1, "spend": 0.7,
   "terminals": {
     "Overseas Passenger Terminal": {"address": "Circular Quay West, The Rocks NSW 2000", "area": "Circular Quay/The Rocks", "lat": -33.8583, "lon": 151.2099},
     "White Bay Cruise Terminal": {"address": "5 Robert St, Rozelle NSW 2039", "area": "Pyrmont", "lat": -33.8665, "lon": 151.1838}}},
 "ticketmaster": {"radius_km": 50, "max_pages": 5, "skip_words": ["parking", "vip", "package", "upgrade", "gift card", "voucher"]},
 "claude": {"estimate_batch_max": 80, "estimate_timeout_s": 300, "estimate_max_turns": 2, "gapfill_timeout_s": 600, "gapfill_max_turns": 12, "gapfill_max_searches": 8, "gapfill_max_events": 40},
 "cache_keep_days": 30
}
```

- [ ] **Step 2: Write `site/strings.json`** (exact; `{…}` are placeholders filled by code):

```json
{"lang": "en",
 "en": {
  "_prompt_language": "English",
  "title": "Taxi Plan", "go_now": "GO NOW", "rest_of_today": "REST OF TODAY",
  "updated_ok": "✓ Updated {time}", "updated_old": "⚠ Old plan, from {day} {time}", "updated_partial": "⚠ Some sources failed · {time}",
  "quiet": "QUIET", "free_until": "Free time until {time} ({name})", "free_rest": "Free time, nothing big later",
  "try_nearby": "Or try nearby: {names}", "tap_open": "▼ tap for more", "tap_close": "▲ tap to close",
  "exit_event": "Comes out ~{time}", "exit_race": "Last race ~{time}", "exit_office": "Staff leave ~{time}", "exit_cruise": "Passengers arrive ~12–3pm",
  "address": "📍 {address}", "starts_ends": "🕖 Starts {start} · ends ~{end}", "crowd": "👥 ~{size} · ages {lo}–{hi}", "wait": "🅿️ Wait: {wait}",
  "from_you": "🚕 ~{min} min from you", "from_prev": "🚕 {min} min from {name}", "from_cbd": "🚕 {min} min from the CBD",
  "navigate": "▶ Navigate (Maps)", "no_plan": "No plan yet. A new plan is made every morning at 10am.", "loading": "Loading…",
  "am": "am", "pm": "pm", "AM": "AM", "PM": "PM",
  "days": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  "office_late": "{name} · late finish", "cruise_name": "Cruise ship boarding · {ship}",
  "cruise_desc": "Ship departs at {time} from the {terminal}. Pick up passengers at city hotels heading to the terminal.",
  "cruise_wait": "City hotels, then the {terminal}"
 }}
```

- [ ] **Step 3: Add `AREAS_JSON` to `tests/helpers.py`** (6 areas, same file format as `data/areas.json`):

areas: `CBD (-33.8688, 151.2093)`, `Barangaroo (-33.8615, 151.2010)`, `Pyrmont (-33.8697, 151.1940)`, `Circular Quay/The Rocks (-33.8599, 151.2090)`, `Olympic Park (-33.8474, 151.0636)`, `Rooty Hill (-33.7707, 150.8440)`. pairs (off-peak minutes): CBD–Barangaroo 6, CBD–Pyrmont 7, CBD–CQ 5, CBD–OP 30, CBD–RH 45, Barangaroo–Pyrmont 6, Barangaroo–CQ 5, Barangaroo–OP 30, Barangaroo–RH 45, Pyrmont–CQ 8, Pyrmont–OP 27, Pyrmont–RH 42, CQ–OP 32, CQ–RH 47, OP–RH 20. `"same_area_min": 5`, `"peak": {"from": "16:00", "to": "19:00", "factor": 1.5}`, `"late": {"from": "21:00", "factor": 0.8}`, `"estimate": true`, `"researched": "2026-11-23"`.

**File formats** (validated by the loaders; Tasks 11–13 fill the real files):

- `data/areas.json`: `{"estimate", "researched", "areas": {name: {"lat", "lon"}}, "pairs": [[a, b, minutes], …], "same_area_min", "peak": {"from", "to", "factor"}, "late": {"from", "factor"}}`. Rules: `"CBD"` present; every unordered pair of distinct areas exactly once; minutes int 1–120.
- `data/offices.json`: `{"estimate", "researched", "offices": [{"id", "name", "address", "area", "lat", "lon", "staff" (int 100–20000), "cabcharge" (0–1), "median_age" (18–70), "age_lo", "age_hi", "spend" (0–1), "normal_finish" ("HH:MM" 16:30–18:59), "late_finish" ("HH:MM" 19:30–22:30), "wait", "desc" (≤160 chars), "source_url"}]}`.
- `data/steady.json`: `{"estimate", "researched", "places": [{"id", "kind" ("hotel"|"casino"|"club"|"hospital"), "name", "address", "area", "lat", "lon", "busy": [["HH:MM", "HH:MM"], …] (non-empty), "wait"}]}`.
- `data/gapfill_venues.json`: `{"estimate", "researched", "venues": [{"name", "kind" ("venue"|"racecourse"), "area", "address", "what_on_url"}]}`.
- Common rules: `"estimate": true`; ids unique; `area` in the area names; lat −34.5…−33.0, lon 150.0…151.5; URLs start `http://` or `https://`. Each `DataError` message names the file and the offending id or pair.
- `load_weights`: all top-level keys of Step 1 present, `points` sum to 100.

- [ ] **Step 4: Write the failing tests** in `tests/test_data.py` (write inline JSON to a `tempfile.TemporaryDirectory`):

```python
def test_parse_areas(self):
    t = parse_areas(AREAS_JSON)
    self.assertEqual(t["minutes"][("Pyrmont","CBD")], 7); self.assertEqual(t["minutes"][("CBD","Pyrmont")], 7)
    self.assertEqual(t["peak"], (240, 420, 1.5)); self.assertEqual(t["late"], (540, 0.8))
    self.assertEqual(t["areas"]["CBD"], (-33.8688, 151.2093)); self.assertEqual(len(t["minutes"]), 30)
def test_missing_pair(self):   # drop the Barangaroo–Pyrmont pair
    with self.assertRaises(DataError) as e: parse_areas(without_pair)
    self.assertIn("Barangaroo", str(e.exception)); self.assertIn("Pyrmont", str(e.exception))
def test_office_bad_area(self):   # one valid office with area "Bondi"
    with self.assertRaises(DataError) as e: load_offices(p, set(TABLE["areas"]))
    self.assertIn("kpmg-barangaroo", str(e.exception))
def test_office_ok(self):  # same office with area "Barangaroo"
    self.assertEqual(load_offices(p, set(TABLE["areas"]))[0]["staff"], 3000)
def test_steady_bad_kind(self):   # kind "pub"
    with self.assertRaises(DataError): load_steady(p, set(TABLE["areas"]))
def test_not_marked_estimate(self):   # offices file with "estimate": false
    with self.assertRaises(DataError): load_offices(p, set(TABLE["areas"]))
def test_real_weights_and_strings(self):
    self.assertEqual(sum(W["points"].values()), 100); self.assertEqual(W["plan"]["big_threshold"], 40)
    for k in ("go_now","free_until","exit_office","cruise_desc","office_late","_prompt_language","am","pm","days","months"):
        self.assertIn(k, S)
```

Office fixture used above: `{"id": "kpmg-barangaroo", "name": "KPMG Barangaroo", "address": "Tower 3, 300 Barangaroo Ave, Barangaroo NSW 2000", "area": "Barangaroo", "lat": -33.8622, "lon": 151.2016, "staff": 3000, "cabcharge": 1.0, "median_age": 40, "age_lo": 25, "age_hi": 55, "spend": 0.7, "normal_finish": "17:30", "late_finish": "20:30", "wait": "Barangaroo Ave rank", "desc": "Big accounting firm, about 3,000 staff. Many use Cabcharge.", "source_url": "https://kpmg.com/au/en/home/contacts/offices.html"}` — save it in `tests/helpers.py` as `OFFICE` (Tasks 10 and 14 reuse it).

- [ ] **Step 5: Run to verify it fails** — `python -m unittest tests.test_data -v` → FAIL (ImportError).
- [ ] **Step 6: Implement `taxi/data.py`** — plain dict checks; `parse_areas` converts peak/late `"HH:MM"` with `shift_minute`.
- [ ] **Step 7: Run to verify it passes** — `python -m unittest tests.test_data tests.test_model -v` → all PASS.
- [ ] **Step 8: Commit** — `git add taxi/data.py weights.json site/strings.json tests && git commit -m "feat: add validated data loaders, weights and UI strings"`

---

### Task 3: Taxi Score

**Files:**
- Create: `taxi/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: `W` shape (Task 2), `shift_slot`, `shift_minute`, `Candidate`; `tests.helpers.cand`, `W`.
- Produces: `age_factor(age: float, curve: list) -> float`; `size_factor(n: int, w: dict) -> float`; `late_factor(exit_minute: int, w: dict) -> float`; `score(median_age: float, pays: float, size: int, spend: float, exit_minute: int, w: dict, rain: bool = False, disrupted: bool = False) -> int`; `score_candidate(c: Candidate, w: dict, rain: set[str], disruptions: list[dict]) -> int` (sets and returns `c.score`). `rain` holds `"YYYY-MM-DDTHH"` keys; a disruption is `{"area", "date", "from", "to", "what", "source_url"}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_regression_examples(self):   # spec 8.2, each within ±1
    self.assertAlmostEqual(score(58, 0.15, 2000, 1.0, 615, W), 66, delta=1)   # Opera House 22:15
    self.assertAlmostEqual(score(40, 1.0, 3000, 0.7, 360, W), 60, delta=1)    # KPMG 18:00
    self.assertAlmostEqual(score(22, 0.0, 20000, 0.15, 780, W), 30, delta=1)  # rave 01:00
def test_factors(self):
    c = W["age_curve"]
    self.assertEqual([age_factor(a, c) for a in (18, 22, 50, 60)], [0.1, 0.1, 1.0, 1.0])
    self.assertAlmostEqual(age_factor(26, c), 0.175); self.assertAlmostEqual(age_factor(42.5, c), 0.7)
    self.assertEqual([size_factor(n, W) for n in (100, 200, 80000, 10**6)], [0.0, 0.0, 1.0, 1.0])
    self.assertAlmostEqual(size_factor(2000, W), 0.3843, places=3)
    self.assertEqual([late_factor(m, W) for m in (0, 539, 540, 599, 600, 780)], [0, 0, 0.5, 0.5, 1, 1])
def test_boosts_and_cap(self):
    self.assertEqual(score(58, 0.15, 2000, 1.0, 615, W, rain=True), 76)
    self.assertEqual(score(58, 0.15, 2000, 1.0, 615, W, rain=True, disrupted=True), 92)
    self.assertEqual(score(60, 1, 80000, 1, 600, W, rain=True, disrupted=True), 100)
def test_score_candidate(self):
    c = cand(area="CBD", exit=datetime(2026,11,23,22,15,tzinfo=SYD), median_age=58, pays=0.15, size=2000, spend=1.0)
    self.assertEqual(score_candidate(c, W, {"2026-11-23T22"}, []), 76)
    strike = {"area": "ALL", "date": "2026-11-23", "from": "20:00", "to": "23:59", "what": "strike", "source_url": "https://x"}
    self.assertEqual(score_candidate(c, W, {"2026-11-23T22"}, [strike]), 92)
    self.assertEqual(score_candidate(c, W, set(), [dict(strike, area="Parramatta")]), 66)
    self.assertEqual(c.score, 66)
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_score -v` → FAIL.
- [ ] **Step 3: Implement `taxi/score.py`** — `score = round(min(100, (35·age + 25·pays + 20·size + 10·spend + 10·late) × boosts))` using `W["points"]`; age is linear interpolation on `age_curve`, clamped at both ends; size `clamp(log10(n/zero_at) / log10(full_at/zero_at), 0, 1)`; late uses `shift_minute(full_from)`/`shift_minute(half_from)`. `score_candidate`: exit minute from `shift_slot(c.exit)`; rain if `c.exit.strftime("%Y-%m-%dT%H")` in `rain`; disrupted if any disruption has `area` in `(c.area, "ALL")`, `date == c.exit.date().isoformat()` and `from ≤ exit "HH:MM" ≤ to`.
- [ ] **Step 4: Run to verify it passes** — same command → PASS.
- [ ] **Step 5: Commit** — `git add taxi/score.py tests/test_score.py && git commit -m "feat: add Taxi Score with spec regression examples"`

---

### Task 4: Drive times

**Files:**
- Create: `taxi/drive.py`
- Test: `tests/test_drive.py`

**Interfaces:**
- Consumes: table `t` (Task 2), `tests.helpers.TABLE`.
- Produces: `haversine_km(lat1, lon1, lat2, lon2) -> float`; `base_minutes(t, a: str, b: str) -> int` (same area → `same_area_min`); `drive_minutes(t, a, b, depart_minute: int) -> int` (shift minutes; ×peak factor if `peak_start ≤ depart < peak_end`, ×late factor if `depart ≥ late_start`; same area is flat `same_area_min`; rounded); `nearest_area(t, lat, lon, max_km: float) -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_drive(self):
    self.assertEqual(drive_minutes(TABLE, "CBD", "Olympic Park", 120), 30)
    self.assertEqual(drive_minutes(TABLE, "CBD", "Olympic Park", 300), 45)   # 17:00 peak
    self.assertEqual(drive_minutes(TABLE, "CBD", "Olympic Park", 600), 24)   # 22:00 late
    self.assertEqual(drive_minutes(TABLE, "Olympic Park", "CBD", 780), 24)   # 01:00
    self.assertEqual(drive_minutes(TABLE, "CBD", "CBD", 300), 5)
    self.assertEqual(base_minutes(TABLE, "Rooty Hill", "CBD"), 45)
def test_nearest_area(self):
    self.assertEqual(nearest_area(TABLE, -33.8473, 151.0628, 12), "Olympic Park")
    self.assertIsNone(nearest_area(TABLE, -37.8136, 144.9631, 12))
    self.assertAlmostEqual(haversine_km(-33.8688, 151.2093, -33.8474, 151.0636), 13.66, delta=0.1)
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_drive -v` → FAIL.
- [ ] **Step 3: Implement `taxi/drive.py`** (`# shortcut: straight-line nearest area, upgrade to suburb polygons if far suburbs get mis-mapped`).
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add taxi/drive.py tests/test_drive.py && git commit -m "feat: add drive-time table lookups"`

---

### Task 5: Itinerary optimiser, quiet blocks, fallbacks

**Files:**
- Create: `taxi/plan.py`
- Modify: `tests/helpers.py` (add `assert_covers(tc, entries)`: blocks contiguous from 0 to 900; Task 14 reuses it)
- Test: `tests/test_plan.py`

**Interfaces:**
- Consumes: `Candidate`, `BLOCKS`, `block_index`, `shift_slot`, `hm_of`, `shift_minute` (Task 1); `base_minutes`, `drive_minutes` (Task 4); `W["plan"]`.
- Produces: `plan_day(cands: list[Candidate], steady: list[dict], t: dict, w: dict) -> list[dict]` (entries per Shared Shapes; all `cands` are scored and on the same shift date); `nearby(steady: list[dict], anchor: str, span: tuple[int, int], t: dict, n: int) -> list[str]`.

Rules: a candidate is **eligible** if `score ≥ big_threshold` and (`base_minutes(t, "CBD", area) ≤ far_minutes` or `score ≥ far_threshold`). Stop B is **reachable** after stop A if `A.exit_min + load + drive_minutes(t, A.area, B.area, A.exit_min + load) ≤ B.exit_min` and B is in a later block. Ineligible or unchosen blocks are quiet; adjacent quiet blocks merge into one entry. Quiet `until` = `hm_of(next stop's block start)`, `next` = next stop's name (both `None` if no later stop). Fallback anchor = next stop's area, else previous stop's area, else `"CBD"`; `nearby` keeps places with a busy window (both ends converted with `shift_minute`) that overlaps `span`, sorts by `(base_minutes(anchor, area), kind_rank, name)` with `kind_rank = {"casino": 0, "hotel": 1, "club": 2, "hospital": 3}`, returns the first `n` names. First stop: `drive_min = base_minutes(t, "CBD", area)`, `drive_from = None`; later stops: `drive_minutes` from the previous stop at its exit + load, `drive_from` = previous stop's name.

Optimiser (maximise the total score; not determined by the tests alone):

```
el = eligible sorted by (exit_min, -score, id)
best[i] = (el[i].score, None)
for i: for j < i with block(j) < block(i) and reachable(el[j], el[i]):
    if best[j][0] + el[i].score > best[i][0]: best[i] = (best[j][0] + el[i].score, j)
end = first i with the max total; follow prev links back → chosen stops in time order
```

- [ ] **Step 1: Write the failing tests** (`c(id, area, hh, mm, score, day=23, name=None)` builds a scored candidate with exit `2026-11-<day> hh:mm` SYD and `name` defaulting to `id`; `place(name, kind, area, from, to)` builds a steady place; `assertCovers(e)` is `assert_covers(self, e)`):

```python
def test_single_stop(self):
    e = plan_day([c("K", "Barangaroo", 17, 30, 60, name="KPMG")], [], TABLE, W)
    self.assertEqual(e[0], {"type": "quiet", "block": [0, 240], "until": "16:00", "next": "KPMG", "nearby": []})
    self.assertEqual((e[1]["type"], e[1]["block"], e[1]["drive_min"], e[1]["drive_from"]), ("stop", [240, 360], 6, None))
    self.assertEqual(e[2], {"type": "quiet", "block": [360, 900], "until": None, "next": None, "nearby": []})
def test_optimiser_beats_greedy(self):
    e = plan_day([c("A", "Olympic Park", 19, 10, 50), c("B", "CBD", 18, 30, 45), c("C", "CBD", 20, 0, 60)], [], TABLE, W)
    self.assertEqual([x["id"] for x in e if x["type"] == "stop"], ["B", "C"]); assertCovers(e)
def test_far_rule(self):
    self.assertEqual([x["type"] for x in plan_day([c("D", "Rooty Hill", 1, 0, 54, day=24)], [], TABLE, W)], ["quiet"])
    self.assertIn("E", [x.get("id") for x in plan_day([c("E", "Rooty Hill", 1, 0, 55, day=24)], [], TABLE, W)])
def test_threshold(self):
    self.assertEqual(plan_day([c("L", "CBD", 18, 0, 39)], [], TABLE, W)[0]["block"], [0, 900])
def test_quiet_merge_and_drive(self):
    e = plan_day([c("S1", "CBD", 13, 0, 50), c("S2", "Circular Quay/The Rocks", 22, 15, 66)], [], TABLE, W)
    self.assertEqual([x["block"] for x in e], [[0, 120], [120, 600], [600, 720], [720, 900]])
    self.assertEqual((e[1]["until"], e[1]["next"]), ("22:00", "S2"))
    self.assertEqual((e[2]["drive_min"], e[2]["drive_from"]), (5, "S1"))
def test_nearby(self):
    steady = [place("H1", "hotel", "Pyrmont", "12:00", "23:00"), place("The Star", "casino", "Pyrmont", "12:00", "03:00"),
              place("RH", "club", "Rooty Hill", "17:00", "02:00"), place("H2", "hotel", "Barangaroo", "12:00", "23:00"),
              place("P", "hospital", "CBD", "12:00", "20:00")]
    self.assertEqual(nearby(steady, "Pyrmont", (120, 600), TABLE, 3), ["The Star", "H1", "H2"])
    self.assertEqual(nearby(steady, "Pyrmont", (720, 900), TABLE, 3), ["The Star", "RH"])
```

Also assert `assertCovers` on every result above.

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_plan -v` → FAIL.
- [ ] **Step 3: Implement `taxi/plan.py`** per the rules and sketch. Stop entries copy fields from the candidate (`exit`/`start` as `"HH:MM"`, `url = source_url`).
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add taxi/plan.py tests/test_plan.py && git commit -m "feat: add day itinerary optimiser with quiet blocks and fallbacks"`

---

### Task 6: Headless Claude runner

**Files:**
- Create: `taxi/claude.py`
- Test: `tests/test_claude.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ClaudeError(Exception)`; `claude_args(tools: list[str], max_turns: int) -> list[str]`; `run_claude(prompt: str, args: list[str], timeout_s: int, token: str | None = None, which=shutil.which) -> str` (returns the `result` text); `extract_json(text: str) -> Any`.

Flags were checked against `claude --help` on CLI 2.1.327 (`--max-turns` is accepted though not listed in help; `--safe-mode` keeps the owner's hooks, plugins, MCP servers and CLAUDE.md out of the call, which saves tokens; `--bare` is not used because it needs an API key). The JSON output is one object: `{"type": "result", "subtype": "success" | "error_…", "is_error": bool, "result": str, …}`. Note: an auth failure comes back as `subtype: "success"` with `is_error: true`.

- [ ] **Step 1: Write the failing tests** (patch `taxi.claude.subprocess.run`; `ok(result)` returns `CompletedProcess([], 0, json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result}), "")`):

```python
def test_args(self):
    self.assertEqual(claude_args([], 2), ["-p","--model","sonnet","--output-format","json","--max-turns","2",
        "--tools","","--permission-prompts","none","--safe-mode","--strict-mcp-config","--no-session-persistence"])
    self.assertEqual(claude_args(["WebSearch","WebFetch"], 12), ["-p","--model","sonnet","--output-format","json","--max-turns","12",
        "--tools","WebSearch,WebFetch","--allowedTools","WebSearch,WebFetch","--permission-prompts","none",
        "--safe-mode","--strict-mcp-config","--no-session-persistence"])
def test_run_ok(self):   # run patched to return ok("[1]")
    out = run_claude("PROMPT", ["-p"], 300, token="TOK", which=lambda n: "C:/fake/claude.exe")
    self.assertEqual(out, "[1]")
    args, kw = run.call_args
    self.assertEqual(args[0], ["C:/fake/claude.exe", "-p"]); self.assertEqual(kw["input"], "PROMPT")
    self.assertEqual((kw["timeout"], kw["encoding"]), (300, "utf-8")); self.assertEqual(kw["env"]["CLAUDE_CODE_OAUTH_TOKEN"], "TOK")
def test_failures(self):
    # each raises ClaudeError: is_error true with subtype "success" and result "Failed to authenticate…" (message kept);
    # subtype "error_max_turns"; TimeoutExpired; returncode 1 with non-JSON stdout; which() returning None ("not found")
def test_extract_json(self):
    self.assertEqual(extract_json('[{"a":1}]'), [{"a": 1}])
    self.assertEqual(extract_json('```json\n{"a":1}\n```'), {"a": 1})
    self.assertEqual(extract_json("Here you go:\n[1,2]\nThanks"), [1, 2])
    with self.assertRaises(ClaudeError): extract_json("no json here")
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_claude -v` → FAIL.
- [ ] **Step 3: Implement `taxi/claude.py`** — `subprocess.run([exe] + args, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s, env=env)`; env = `os.environ` copy plus `CLAUDE_CODE_OAUTH_TOKEN` when `token`. Fail if `is_error` or `subtype != "success"`. `extract_json`: first `[` or `{`, then `json.JSONDecoder().raw_decode`.
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add taxi/claude.py tests/test_claude.py && git commit -m "feat: add headless Claude CLI runner"`

---

### Task 7: Estimate cache and batched estimate

**Files:**
- Create: `taxi/cache.py`, `taxi/estimate.py`
- Test: `tests/test_estimate.py`

**Interfaces:**
- Consumes: `Candidate`, `exit_after` (Task 1); `ClaudeError`, `extract_json` (Task 6).
- Produces: `load_cache(path: Path) -> dict` (missing → empty shape; corrupt → renames the file to `estimates.json.bad`, logs, returns empty); `save_cache(cache: dict, path: Path) -> None` (creates the parent folder; atomic: write `.tmp`, `os.replace`); `prune(cache: dict, today: date, keep_days: int) -> None`; `EST_KEYS`; `validate_estimate(obj: dict) -> dict | None` (checks per Shared Shapes, returns only `EST_KEYS`); `apply_estimate(c: Candidate, e: dict) -> None`; `estimate_prompt(events: list[Candidate], language: str) -> str`; `estimate_events(events: list[Candidate], cache: dict, call: Callable[[str], str] | None, w: dict, today: date, language: str) -> tuple[list[Candidate], str]` (returns the events that now have estimates, and `"ok"`, `"skipped"` when `call is None`, or `"error: <msg>"`).

Behaviour: cached ids are applied and get `seen = today` without a call. Uncached events, sorted by `start`, are capped at `claude.estimate_batch_max` (the rest are logged and dropped for today) and sent in **one** call. Items with an unknown id or failing validation count as missing; if any are missing after a successful call, **one** retry call lists only those. A `ClaudeError` is not retried. Prompt requirements: one line per event `id | name | venue | YYYY-MM-DD HH:MM | info`; ask for a bare JSON array of objects with `id` + `EST_KEYS`; define `size` as expected attendance, `pays` as the share whose taxi an employer or company pays, `spend` as spending power 0–1, `exit` as the local time most of the crowd leaves, `wait` as the best nearby place for a taxi to wait, `desc` as one plain sentence for a taxi driver; write `wait` and `desc` in `{language}`; estimate only the listed events and never add others.

- [ ] **Step 1: Write the failing tests** (events `tm:A` start 2026-11-23 19:30 and `tm:B` start 2026-11-24 20:00; `est(id, **kw)` returns a valid item `median_age 50, age_lo 35, age_hi 65, size 2000, pays 0.1, spend 0.8, exit "22:15", wait "Macquarie St", desc "Opera night."`; `fake(*responses)` records prompts and returns responses in order, raising them if they are exceptions):

```python
def test_one_call_for_uncached(self):
    call = fake(json.dumps([est("tm:A"), est("tm:B", exit="23:00")])); cache = {"estimates": {}, "gapfill": {}}
    got, status = estimate_events([A, B], cache, call, W, date(2026,11,23), "English")
    self.assertEqual((len(call.prompts), status), (1, "ok")); self.assertIn("tm:A", call.prompts[0]); self.assertIn("tm:B", call.prompts[0])
    self.assertEqual(A.exit, datetime(2026,11,23,22,15,tzinfo=SYD)); self.assertEqual(cache["estimates"]["tm:A"]["seen"], "2026-11-23")
def test_cached_needs_no_call(self): ...   # 0 prompts, both returned, seen updated
def test_retry_missing_once(self):         # first response only A, second only B
    self.assertEqual(len(call.prompts), 2); self.assertIn("tm:B", call.prompts[1]); self.assertNotIn("tm:A", call.prompts[1])
def test_still_missing_dropped(self): ...  # both responses only A → returns [A], 2 prompts
def test_claude_error(self):               # call raises ClaudeError("auth") with A cached
    self.assertEqual([c.id for c in got], ["tm:A"]); self.assertTrue(status.startswith("error: auth")); self.assertEqual(len(call.prompts), 1)
def test_batch_cap(self):                  # W copy with estimate_batch_max 1
    self.assertIn("tm:A", call.prompts[0]); self.assertNotIn("tm:B", call.prompts[0])
def test_fenced_reply(self): ...           # "```json\n[...]\n```" is accepted
def test_validate(self):
    self.assertIsNone(validate_estimate(dict(est("x"), pays=1.5)))
    self.assertIsNone(validate_estimate(dict(est("x"), age_lo=60)))      # age_lo > median
    self.assertIsNone(validate_estimate(dict(est("x"), exit="25:00")))
    self.assertIsNone(validate_estimate(dict(est("x"), desc="x" * 201)))
    self.assertNotIn("foo", validate_estimate(dict(est("x"), foo=1)))
def test_cache_file(self):
    # missing file → {"estimates": {}, "gapfill": {}}; "{not json" → same and estimates.json.bad exists; save→load round trip
def test_prune(self):
    # today 2026-11-23, keep 30: estimate seen 2026-10-01 removed, seen 2026-11-01 kept;
    # gapfill event date 2026-11-22 removed, 2026-11-23 kept
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_estimate -v` → FAIL.
- [ ] **Step 3: Implement `taxi/cache.py` and `taxi/estimate.py`.**
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add taxi/cache.py taxi/estimate.py tests/test_estimate.py && git commit -m "feat: add cached batched Claude estimates"`

---

### Task 8: Capped gap-fill (venues, race days, trackwork and strikes)

**Files:**
- Create: `taxi/gapfill.py`
- Test: `tests/test_gapfill.py`

**Interfaces:**
- Consumes: `validate_estimate`, `EST_KEYS` (Task 7); `ClaudeError`, `extract_json` (Task 6); `Candidate`, `exit_after`, `slug`, `SYD` (Task 1); table `t`. `alive` is a required parameter (Task 14 passes `taxi.net.url_alive`; tests pass a lambda), so this module does not import `taxi.net`.
- Produces: `gapfill_prompt(venues: list[dict], days: list[date], known: list[str], area_names: list[str], max_searches: int, language: str) -> str`; `validate_event(obj: dict, days: set[date], area_names: set[str]) -> dict | None`; `validate_disruption(obj: dict, days: set[date], area_names: set[str]) -> dict | None`; `event_to_candidate(ev: dict, t: dict) -> Candidate`; `gapfill(call: Callable[[str], str] | None, venues: list[dict], days: list[date], existing: list[Candidate], t: dict, cache: dict, today: date, w: dict, language: str, alive: Callable[[str], bool]) -> tuple[list[Candidate], list[dict], str]`.

Race days and trackwork/strikes go through this one call because the Racing NSW / ATC and Transport for NSW pages were 404, rate-limited (429) or script-rendered when checked on 2026-11-23. The call returns `{"events": [...], "disruptions": [...]}`. Event = `{name, venue, address, area, kind ("event"|"race"), date, start, exit, source_url}` + `EST_KEYS`; disruption = `{area (name or "ALL"), date, from, to, what ("trackwork"|"strike"), source_url}` (same-day ranges only). Validation: strings non-empty ≤120 chars, date in `days`, times `"HH:MM"`, area in names, `source_url` http(s), estimate fields via `validate_estimate`; an event is also dropped if `alive(source_url)` is False, if an `existing` candidate in the same area starts within 60 min on that date, or beyond `claude.gapfill_max_events`. Valid events go into `cache["gapfill"]` keyed by id with `seen = today`; cached events dated today or later are returned even when the call fails. Exactly **one** call, never retried. Prompt requirements: list venues with their `what_on_url`, the dates, the "already known — skip" list (`"venue | YYYY-MM-DD"` from `existing`), the allowed area names; ask for events expecting at least 500 people, race meetings at the racecourses, and Sydney train trackwork or transport strikes; every item needs a real `source_url` from the page it came from; "use at most {max_searches} web searches or fetches in total"; write `wait`/`desc` in `{language}`; reply with the bare JSON object.

Candidates: `id = "gf:" + slug(f"{venue}-{date}-{name}")[:80]`, `lat/lon` = the area's centroid, `start = datetime(date, start, SYD)`, `exit = exit_after(start, exit)`.

- [ ] **Step 1: Write the failing tests** (`GOOD = {"name": "Medical Congress", "venue": "ICC Sydney", "address": "14 Darling Dr, Sydney NSW 2000", "area": "Pyrmont", "kind": "event", "date": "2026-11-24", "start": "09:00", "exit": "18:30", "source_url": "https://www.iccsydney.com.au/whats-on/x", **valid estimate fields**}`; days = Mon 23–Fri 27 Nov 2026):

```python
def test_prompt(self):
    p = gapfill_prompt([{"name": "Sydney Opera House", "what_on_url": "https://www.sydneyoperahouse.com/whats-on", ...}],
                       DAYS, ["Opera House | 2026-11-24"], ["CBD", "Pyrmont"], 8, "English")
    for s in ("Sydney Opera House", "2026-11-24", "at most 8", "Opera House | 2026-11-24", "Pyrmont", "English"): self.assertIn(s, p)
def test_valid_event(self):
    cands, dis, status = gapfill(fake(json.dumps({"events": [GOOD], "disruptions": []})), VENUES, DAYS, [], TABLE, cache, TODAY, W, "English", alive=lambda u: True)
    c = cands[0]; self.assertTrue(c.id.startswith("gf:")); self.assertEqual((c.lat, c.lon), TABLE["areas"]["Pyrmont"])
    self.assertEqual(c.exit, datetime(2026,11,24,18,30,tzinfo=SYD)); self.assertIn(c.id, cache["gapfill"]); self.assertEqual(status, "ok")
def test_drops(self):
    # each dropped: no source_url; date "2026-11-29"; area "Bondi"; size -5; alive() False;
    #   an existing Pyrmont candidate starting 2026-11-24 09:30 (GOOD starts 09:00)
    # kept: an existing Pyrmont candidate starting 2026-11-24 14:00
def test_disruptions(self):
    ok = {"area": "ALL", "date": "2026-11-24", "from": "00:00", "to": "23:59", "what": "strike", "source_url": "https://transportnsw.info/x"}
    self.assertIsNotNone(validate_disruption(ok, set(DAYS), set(TABLE["areas"])))
    self.assertIsNone(validate_disruption(dict(ok, area="Mars"), set(DAYS), set(TABLE["areas"])))
    self.assertIsNone(validate_disruption(dict(ok, what="party"), set(DAYS), set(TABLE["areas"])))
def test_error_keeps_cached_future(self):   # cache holds a gap-fill event dated 2026-11-25; call raises ClaudeError
    self.assertEqual(len(cands), 1); self.assertEqual(dis, []); self.assertTrue(status.startswith("error")); self.assertEqual(len(call.prompts), 1)
def test_skipped_without_call(self): ...    # call None → cached future events, status "skipped"
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_gapfill -v` → FAIL.
- [ ] **Step 3: Implement `taxi/gapfill.py`.**
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add taxi/gapfill.py tests/test_gapfill.py && git commit -m "feat: add capped Claude gap-fill for venues, races and disruptions"`

---

### Task 9: HTTP helpers and Ticketmaster

**Files:**
- Create: `taxi/net.py`, `taxi/sources/ticketmaster.py`, `tests/fixtures/tm_page.json`
- Test: `tests/test_ticketmaster.py`

**Interfaces:**
- Consumes: `Candidate`, `SYD` (Task 1); `nearest_area` (Task 4); `W["ticketmaster"]`, `W["plan"]["area_max_km"]`.
- Produces: `SourceError(Exception)`; `get_text(url: str, timeout: int = 20) -> str`; `url_alive(url: str, timeout: int = 10) -> bool` (HEAD request; False only on HTTP 404/410 or `URLError`); `fetch_events(key: str, days: list[date], get_text: Callable[[str], str], w: dict) -> list[dict]`; `to_candidates(events: list[dict], t: dict, w: dict) -> list[Candidate]`.

Discovery API v2: `https://app.ticketmaster.com/discovery/v2/events.json?apikey=…&latlong=-33.8688,151.2093&radius=50&unit=km&countryCode=AU&size=200&sort=date,asc&startDateTime=…&endDateTime=…&page=N`. Range: first day 00:00 SYD to the day after the last day 03:00 SYD, as UTC `YYYY-MM-DDTHH:MM:SSZ`. Pages 0…`min(totalPages, max_pages) - 1`, `time.sleep(0.25)` between pages (rate limit 5/s). Events are in `_embedded.events` (key absent when there are none). Fields used: `id`, `name`, `url`, `dates.start.localDate`, `dates.start.localTime`, `_embedded.venues[0].name`, `.address.line1`, `.city.name`, `.location.latitude`/`.longitude` (strings), `classifications[0].segment.name`, `.genre.name`, `priceRanges[0].min`/`.max` (optional).

`to_candidates` drops: names containing any `skip_words` (case-insensitive); no `localTime`; start between 03:00 and 09:59; venue with no area within `area_max_km`; repeats of the same (venue, localDate, localTime) after the first. Kept: `id "tm:<id>"`, `kind "event"`, `address "<line1>, <city>"`, `start` aware SYD, `info "<segment> / <genre> · $<min>–<max>"` (price part omitted when absent, numbers without decimals).

- [ ] **Step 1: Write the fixture** `tests/fixtures/tm_page.json` in Discovery shape, `page: {"totalPages": 1, "number": 0}`, six events: `Z1` "Qudos concert" at Qudos Bank Arena (`-33.8473`, `151.0628`, line1 "Olympic Blvd", city "Sydney Olympic Park"), 2026-11-25 19:30:00, Music/Rock, price 89–189, url `https://www.ticketmaster.com.au/event/Z1`; `Z2` "Parking Pass - Qudos" same venue/date; `Z3` "Qudos concert" same venue, date and time as Z1; `Z4` "Mystery show" with no `localTime`; `Z5` "Melbourne gig" at `-37.8136`, `144.9631`; `Z6` "Morning kids show" at 09:30:00.

- [ ] **Step 2: Write the failing tests**

```python
def test_to_candidates_filters_junk(self):
    cs = to_candidates(load("tm_page.json")["_embedded"]["events"], TABLE, W)
    self.assertEqual([c.id for c in cs], ["tm:Z1"]); c = cs[0]
    self.assertEqual((c.area, c.start, c.info), ("Olympic Park", datetime(2026,11,25,19,30,tzinfo=SYD), "Music / Rock · $89–189"))
    self.assertEqual((c.address, c.source_url), ("Olympic Blvd, Sydney Olympic Park", "https://www.ticketmaster.com.au/event/Z1"))
def test_fetch_events_url_and_paging(self):   # fake get_text returns totalPages 2; time.sleep patched
    evs = fetch_events("KEY", [date(2026,11,d) for d in (23,24,25,26,27)], get, W)
    u = get.urls[0]
    for s in ("apikey=KEY", "latlong=-33.8688,151.2093", "radius=50", "unit=km", "size=200",
              "startDateTime=2026-11-22T13:00:00Z", "endDateTime=2026-11-27T16:00:00Z", "page=0"): self.assertIn(s, u)
    self.assertIn("page=1", get.urls[1]); self.assertEqual(len(get.urls), 2)
def test_no_events_key(self): ...   # response without "_embedded" → []
def test_error_message_hides_query(self):   # urlopen patched to raise HTTPError(url, 401, "Unauthorized", {}, None)
    with self.assertRaises(SourceError) as e: get_text("https://app.ticketmaster.com/x?apikey=SECRET123")
    self.assertNotIn("SECRET123", str(e.exception)); self.assertIn("401", str(e.exception))
def test_url_alive(self): ...       # 200 → True, 403 → True, 404 → False, URLError → False
```

- [ ] **Step 3: Run to verify it fails** — `python -m unittest tests.test_ticketmaster -v` → FAIL.
- [ ] **Step 4: Implement `taxi/net.py` and `taxi/sources/ticketmaster.py`.** `SourceError` messages use only the URL's host.
- [ ] **Step 5: Run to verify it passes** → PASS.
- [ ] **Step 6: Commit** — `git add taxi/net.py taxi/sources/ticketmaster.py tests && git commit -m "feat: add Ticketmaster source with junk filtering"`

---

### Task 10: Cruise, weather and office sources

**Files:**
- Create: `taxi/sources/cruise.py`, `taxi/sources/weather.py`, `taxi/sources/offices.py`, `tests/fixtures/cruise.html`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `Candidate`, `at_shift`, `fmt12`, `slug`, `shift_minute`, `SYD` (Task 1); `SourceError` (Task 9); `W`, `S`.
- Produces: `CRUISE_URL = "https://www.portauthoritynsw.com.au/cruise/cruise-schedule/"`; `parse_schedule(html: str, today: date) -> list[dict]` (`{"ship", "departure": datetime, "berth"}`); `fetch_departures(get_text, today) -> list[dict]` (pages `CRUISE_URL` and `CRUISE_URL + "?page=1"`; a failing page 1 is ignored); `boarding_candidates(deps: list[dict], days: list[date], w: dict, S: dict) -> list[Candidate]`; `WEATHER_URL = "https://api.open-meteo.com/v1/forecast?latitude=-33.87&longitude=151.21&hourly=precipitation_probability,precipitation&timezone=Australia%2FSydney&forecast_days=7"`; `rain_hours(data: dict, w: dict) -> set[str]`; `fetch_rain(get_text, w) -> set[str]`; `office_candidates(offices: list[dict], days: list[date], w: dict, S: dict) -> list[Candidate]`.

Cruise page (checked 2026-11-23): one `<table class="cols-6">`; each row has `<td class="views-field views-field-vessel-name">`, `…views-field-departure-time">Mon 23 Nov<br>18:00</td>` (no year) and `…views-field-berth">`. Parse with `html.parser`; pick the year that puts the date within 180 days of `today`. No rows → `SourceError("cruise: no rows")`. A boarding candidate is made for a departure on one of `days` with departure time ≥ `cruise.min_departure` and a berth in `cruise.terminals` (others logged and skipped): exit `at_shift(date, cruise.exit)`, size/ages/pays/spend from `cruise`, terminal address/area/lat/lon, `name = S["cruise_name"]`, `desc = S["cruise_desc"]` with `time = fmt12(departure.strftime("%H:%M"), S)` and `terminal` = berth name, `wait = S["cruise_wait"]`, `source_url = CRUISE_URL`, `kind "cruise"`. Rain: an hour key `"YYYY-MM-DDTHH"` is rainy if `precipitation ≥ min_mm` or `precipitation_probability ≥ min_prob` (`# shortcut: one CBD forecast point; upgrade to one point per area if suburbs disagree`). Offices: for each weekday (Mon–Fri) in `days`, a normal candidate (`exit = normal_finish`, `size = staff`, `pays = cabcharge`) and a late one (`exit = late_finish`, `size = round(staff × late_crowd_share)`, `pays = late_pays`, `name = S["office_late"]`); `kind "office"`, `start None`.

- [ ] **Step 1: Write the fixture** `tests/fixtures/cruise.html`: the real table structure above with four rows — "Viking Venus" `Mon 23 Nov<br>18:00` White Bay Cruise Terminal; "Anthem of the Seas" `Mon 23 Nov<br>16:45` Overseas Passenger Terminal; "Early Ship" `Tue 24 Nov<br>12:30` Overseas Passenger Terminal; "Sea Ship" `Sun 29 Nov<br>17:00` Overseas Passenger Terminal.

- [ ] **Step 2: Write the failing tests**

```python
def test_parse_and_board(self):
    deps = parse_schedule(read("cruise.html"), date(2026,11,23)); self.assertEqual(len(deps), 4)
    cs = boarding_candidates(deps, DAYS, W, S)
    self.assertEqual(sorted(c.id for c in cs), ["cruise:anthem-of-the-seas:2026-11-23", "cruise:viking-venus:2026-11-23"])
    v = next(c for c in cs if "viking" in c.id)
    self.assertEqual((v.exit, v.size, v.area), (datetime(2026,11,23,13,0,tzinfo=SYD), 3000, "Pyrmont"))
    self.assertEqual(v.desc, "Ship departs at 6pm from the White Bay Cruise Terminal. Pick up passengers at city hotels heading to the terminal.")
    self.assertEqual(v.name, "Cruise ship boarding · Viking Venus")
def test_year_rollover(self):   # one row "Fri 1 Jan<br>17:00", today 2026-12-30
    self.assertEqual(parse_schedule(row_html, date(2026,12,30))[0]["departure"].year, 2027)
def test_no_rows(self):
    with self.assertRaises(SourceError): parse_schedule("<html></html>", date(2026,11,23))
def test_rain_hours(self):
    data = {"hourly": {"time": ["2026-11-23T18:00", "2026-11-23T19:00", "2026-11-23T20:00"],
                       "precipitation_probability": [70, 10, 40], "precipitation": [0.1, 0.6, 0.2]}}
    self.assertEqual(rain_hours(data, W), {"2026-11-23T18", "2026-11-23T19"})
def test_offices(self):
    cs = office_candidates([dict(OFFICE, cabcharge=0.6)], [date(2026,11,23), date(2026,11,28)], W, S)
    self.assertEqual([c.id for c in cs], ["office:kpmg-barangaroo:normal:2026-11-23", "office:kpmg-barangaroo:late:2026-11-23"])
    n, l = cs
    self.assertEqual((n.pays, n.size, n.exit), (0.6, 3000, datetime(2026,11,23,17,30,tzinfo=SYD)))
    self.assertEqual((l.pays, l.size, l.name, l.exit), (1.0, 600, "KPMG Barangaroo · late finish", datetime(2026,11,23,20,30,tzinfo=SYD)))
```

- [ ] **Step 3: Run to verify it fails** — `python -m unittest tests.test_sources -v` → FAIL.
- [ ] **Step 4: Implement the three source modules.**
- [ ] **Step 5: Run to verify it passes** → PASS.
- [ ] **Step 6: Commit** — `git add taxi/sources tests && git commit -m "feat: add cruise boarding, rain and office finish sources"`

---

### Task 11: Research — drive-time table (`data/areas.json`)

**Files:**
- Create: `data/areas.json`
- Test: `tests/test_data_files.py`

**Interfaces:**
- Consumes: `load_areas`, `base_minutes`, `haversine_km`.
- Produces: the real area table, exactly these 15 names: `"CBD", "Barangaroo", "Darling Harbour", "Circular Quay/The Rocks", "Moore Park", "Randwick", "Olympic Park", "Parramatta", "Rosehill", "North Sydney", "Chatswood", "Macquarie Park", "Rooty Hill", "Canterbury", "Pyrmont"`.

- [ ] **Step 1: Write the failing test** `tests/test_data_files.py`:

```python
AREAS = {"CBD", "Barangaroo", "Darling Harbour", "Circular Quay/The Rocks", "Moore Park", "Randwick", "Olympic Park",
         "Parramatta", "Rosehill", "North Sydney", "Chatswood", "Macquarie Park", "Rooty Hill", "Canterbury", "Pyrmont"}
class TestAreasFile(unittest.TestCase):
    def test_areas(self):
        t = load_areas("data/areas.json"); m = lambda a, b: base_minutes(t, a, b)
        self.assertEqual(set(t["areas"]), AREAS); self.assertEqual(len(t["minutes"]), 210)
        for lat, lon in t["areas"].values(): self.assertTrue(-34.1 < lat < -33.6 and 150.7 < lon < 151.35)
        for a in AREAS:
            for b in AREAS:
                for c in AREAS:
                    if len({a, b, c}) == 3: self.assertLessEqual(m(a, c), m(a, b) + m(b, c) + 10)
        self.assertLessEqual(m("CBD", "Barangaroo"), 10); self.assertTrue(20 <= m("CBD", "Olympic Park") <= 35)
        self.assertTrue(25 <= m("CBD", "Parramatta") <= 45); self.assertTrue(35 <= m("CBD", "Rooty Hill") <= 55)
        self.assertTrue(10 <= m("CBD", "Randwick") <= 25)
        self.assertEqual((t["peak"], t["late"]), ((240, 420, 1.5), (540, 0.8)))
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_data_files -v` → FAIL (file missing).
- [ ] **Step 3: Research and write `data/areas.json`** — centroid lat/lon of each area's main destination (e.g. Olympic Park = Qudos Bank Arena, Moore Park = Allianz Stadium, Rosehill = Rosehill Gardens, Rooty Hill = Rooty Hill RSL); off-peak midday car minutes for all 105 pairs from public route information (web search) and judgement; `same_area_min 5`, `peak 16:00–19:00 ×1.5`, `late from 21:00 ×0.8`; `"estimate": true`, `"researched": "<today>"`, plus `"note": "Off-peak car minutes, researched estimates."`.
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add data/areas.json tests/test_data_files.py && git commit -m "data: add researched drive-time table"`

---

### Task 12: Research — Cabcharge-heavy offices (`data/offices.json`)

**Files:**
- Create: `data/offices.json`
- Modify: `tests/test_data_files.py`

**Interfaces:**
- Consumes: `load_offices`, `load_areas`, `nearest_area`; offices format (Task 2).
- Produces: 20–30 office entries.

- [ ] **Step 1: Add the failing test**

```python
class TestOfficesFile(unittest.TestCase):
    def test_offices(self):
        t = load_areas("data/areas.json"); offs = load_offices("data/offices.json", set(t["areas"]))
        self.assertTrue(20 <= len(offs) <= 30)
        for area in ("CBD", "Barangaroo"): self.assertGreaterEqual(sum(o["area"] == area for o in offs), 3)
        for o in offs: self.assertEqual(o["area"], nearest_area(t, o["lat"], o["lon"], 60), o["id"])
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_data_files -v` → FAIL.
- [ ] **Step 3: Research and write `data/offices.json`** — large Sydney offices whose staff commonly travel on employer-paid Cabcharge/corporate taxi accounts: Big Four accounting firms, top-tier law firms, major banks and investment banks, strategy consultancies, large insurers, big NSW government departments (Parramatta included), with a few in North Sydney, Chatswood and Macquarie Park. Per office: street address (from the company's own contact/office page, used as `source_url`), lat/lon, rough Sydney staff count, `cabcharge` (law/consulting/investment banking ~0.8–1.0, accounting ~0.7–1.0, government ~0.3–0.5), ages, `spend`, normal finish (17:00–18:30) and late finish (20:00–22:00), nearest taxi rank or kerb as `wait`, one-sentence `desc` (no people's names). `"estimate": true`.
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add data/offices.json tests/test_data_files.py && git commit -m "data: add researched Cabcharge-heavy office list"`

---

### Task 13: Research — steady places and gap-fill venues

**Files:**
- Create: `data/steady.json`, `data/gapfill_venues.json`
- Modify: `tests/test_data_files.py`

**Interfaces:**
- Consumes: `load_steady`, `load_venues`, `load_areas`, `nearest_area`.
- Produces: hotels 15–20, casinos exactly 2, RSL/leagues clubs 10–15, private hospitals 5–8; venues 10–14 plus the 4 racecourses.

- [ ] **Step 1: Add the failing test**

```python
class TestSteadyAndVenues(unittest.TestCase):
    def test_steady(self):
        t = load_areas("data/areas.json"); ps = load_steady("data/steady.json", set(t["areas"]))
        n = lambda k: sum(p["kind"] == k for p in ps)
        self.assertTrue(15 <= n("hotel") <= 20 and 10 <= n("club") <= 15 and 5 <= n("hospital") <= 8)
        self.assertEqual({p["name"] for p in ps if p["kind"] == "casino"}, {"The Star Sydney", "Crown Sydney"})
        for p in ps: self.assertEqual(p["area"], nearest_area(t, p["lat"], p["lon"], 60), p["id"])
    def test_venues(self):
        t = load_areas("data/areas.json"); vs = load_venues("data/gapfill_venues.json", set(t["areas"]))
        names = {v["name"] for v in vs}
        self.assertTrue({"Sydney Opera House", "ICC Sydney"} <= names); self.assertTrue(10 <= sum(v["kind"] == "venue" for v in vs) <= 14)
        self.assertEqual({v["name"] for v in vs if v["kind"] == "racecourse"}, {"Royal Randwick", "Rosehill Gardens", "Canterbury Park", "Warwick Farm"})
```

- [ ] **Step 2: Run to verify it fails** → FAIL.
- [ ] **Step 3: Research and write both files** — Steady: big CBD/Darling Harbour/Barangaroo/Circular Quay business hotels (busy windows like `["12:00","14:00"]`, `["17:00","23:00"]`), The Star Sydney and Crown Sydney (`["12:00","03:00"]`), large RSL/leagues clubs within about 50 minutes of the CBD (e.g. Rooty Hill RSL, Canterbury League Club, Parramatta Leagues, Wests Ashfield, Club Burwood, City Tattersalls, Easts Leagues, Souths Juniors, St George Leagues, Mounties), private hospitals (e.g. St Vincent's Private, Mater North Sydney, Prince of Wales Private, Macquarie University Hospital, Norwest Private, Strathfield Private) with discharge/visiting-end windows. Venues: big venues often missing from Ticketmaster (Sydney Opera House, ICC Sydney, Capitol Theatre, State Theatre, Theatre Royal, Lyric Theatre, Roslyn Packer Theatre, City Recital Hall, Sydney Town Hall, Riverside Theatres, Enmore Theatre, Hordern Pavilion …) with each venue's own "what's on" URL; racecourses Royal Randwick, Rosehill Gardens, Canterbury Park, Warwick Farm with the Australian Turf Club race-day URL. Set every `area` to the nearest centroid. `"estimate": true` in both.
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add data tests/test_data_files.py && git commit -m "data: add steady fallback places and gap-fill venues"`

---

### Task 14: Scan pipeline, publish, scheduler wrapper, Pages workflow

**Files:**
- Create: `scan.py`, `taxi/publish.py`, `run_scan.cmd`, `.github/workflows/pages.yml`, `tests/fixtures/weather_dry.json`
- Test: `tests/test_scan.py`, `tests/test_publish.py`

**Interfaces:**
- Consumes: everything above: `taxi.data` loaders, `working_days`, `shift_slot`, `fetch_events`/`to_candidates`, `fetch_departures`/`boarding_candidates`, `fetch_rain`, `office_candidates`, `load_cache`/`save_cache`/`prune`, `estimate_events`, `gapfill`, `score_candidate`, `plan_day`, `claude_args`, `run_claude`, `url_alive`, `get_text`.
- Produces: `load_secrets(root: Path) -> dict` (keys `ticketmaster_key`, `claude_oauth_token`; env `TICKETMASTER_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` override the file); `run(now: datetime, root: Path, get_text=None, call_claude=None, publish_fn=None, use_claude: bool = True, do_publish: bool = True) -> dict` (each `None` means `taxi.net.get_text` / `taxi.claude.run_claude` / `taxi.publish.publish`, looked up at call time; `scan.py` imports modules — `from taxi import net, plan as planner, …` — and calls `planner.plan_day`, so tests can patch `taxi.net.get_text` and `taxi.plan.plan_day`); `main(argv: list[str] | None = None) -> int` (flags `--no-claude`, `--no-publish`, `--root PATH`); `write_plan(plan: dict, path: Path) -> None` (atomic, UTF-8, `ensure_ascii=False`); `publish(root: Path, today: date, run=subprocess.run) -> str`.

`run` order: load weights/strings/data from `root`; `days = working_days(now.date())`; sources `ticketmaster` (no key → error `"no Ticketmaster key"`), `cruise`, `offices`, `weather`, each in its own `try/except Exception` that logs and sets `sources[name] = "error: " + str(e)[:120]`, else `"ok"`; logs one line per source `<name>: ok, <n> candidates` or `<name>: error: <msg>`. Then `estimate_events` on the Ticketmaster candidates and `gapfill` with `existing` = those candidates, where `call_claude(prompt, args, timeout) -> str` (default `run_claude` with the secrets token) is wrapped as `lambda p: call_claude(p, claude_args([], est_turns), est_timeout)` and `lambda p: call_claude(p, claude_args(["WebSearch", "WebFetch"], gf_turns), gf_timeout)`; with `use_claude=False` both get `call=None`. `prune` then `save_cache(root/"cache"/"estimates.json")`. Score every candidate; keep those with `shift_slot(exit)` on one of `days`; `plan_day` per day. `status = "ok"` if `sources["ticketmaster"] == "ok"` and `sources["estimate"] == "ok"`, else `"partial"`. `generated_at = now.isoformat(timespec="seconds")`. `write_plan(root/"site"/"plan.json")`; then `publish_fn(root, now.date())` if `do_publish` (result logged). `main` logs to `root/logs/scan.log` (creating `logs/`), calls `run(datetime.now(SYD), …)`, returns 0, or logs the traceback and returns 1 without touching `plan.json`.

`publish` runs, with `cwd=root, capture_output=True, text=True, timeout=120`: `["git","add","site/plan.json"]`, `["git","diff","--cached","--quiet"]` (exit 0 → return `"no changes"`), `["git","commit","-m","plan: <YYYY-MM-DD>"]`, `["git","push","origin","main"]`; returns `"ok"` or `"error: <step> failed"`.

- [ ] **Step 1: Write the failing tests.** `make_root(tmp)` writes `data/areas.json` (`AREAS_JSON`), `data/offices.json` (`[OFFICE]`), `data/steady.json` (two places), `data/gapfill_venues.json` (one venue), copies `weights.json` and `site/strings.json`, writes `secrets.json` `{"ticketmaster_key": "SECRETKEY123"}`. `get(url)` returns `tm_page.json` for `ticketmaster`, `cruise.html` for `portauthoritynsw`, `weather_dry.json` (`{"hourly": {"time": [], "precipitation_probability": [], "precipitation": []}}`) for `open-meteo`. `fake_claude(prompt, args, timeout)` returns `{"events": [], "disruptions": []}` JSON when `"WebSearch,WebFetch"` is in `args`, else `[{"id": "tm:Z1", "median_age": 45, "age_lo": 35, "age_hi": 60, "size": 18000, "pays": 0.05, "spend": 0.6, "exit": "22:45", "wait": "Olympic Blvd rank", "desc": "Rock concert."}]`. `NOW = datetime(2026,11,23,10,0,tzinfo=SYD)`. `stops(plan, ymd)` returns that day's `"stop"` entries; `pub` is a `Mock(return_value="ok")`.

```python
def test_end_to_end(self):
    plan = run(NOW, root, get_text=get, call_claude=fake_claude, publish_fn=pub)
    self.assertEqual(plan["status"], "ok"); self.assertEqual([d["date"] for d in plan["days"]], ["2026-11-23","2026-11-24","2026-11-25","2026-11-26","2026-11-27"])
    wed = stops(plan, "2026-11-25"); z = next(s for s in wed if s["id"] == "tm:Z1")
    self.assertEqual((z["score"], z["block"]), (62, [600, 720]))
    self.assertEqual([s["id"] for s in stops(plan, "2026-11-23")],
        ["cruise:anthem-of-the-seas:2026-11-23", "office:kpmg-barangaroo:normal:2026-11-23", "office:kpmg-barangaroo:late:2026-11-23"])
    self.assertEqual(json.loads((root/"site"/"plan.json").read_text("utf-8")), plan)
    self.assertIn("tm:Z1", json.loads((root/"cache"/"estimates.json").read_text("utf-8"))["estimates"])
    pub.assert_called_once(); self.assertNotIn("SECRETKEY123", json.dumps(plan))
    for d in plan["days"]: assert_covers(self, d["entries"])
def test_ticketmaster_failure_is_partial(self):   # get raises SourceError for ticketmaster URLs
    plan = run(NOW, root, get_text=bad_tm, call_claude=fake_claude, publish_fn=pub)
    self.assertEqual(plan["status"], "partial"); self.assertTrue(plan["sources"]["ticketmaster"].startswith("error")); self.assertEqual(len(plan["days"]), 5)
def test_claude_failure_marks_partial(self):     # call_claude raises ClaudeError("Failed to authenticate")
    self.assertEqual(plan["status"], "partial"); self.assertTrue(plan["sources"]["estimate"].startswith("error"))
    self.assertIn("office:kpmg-barangaroo:normal:2026-11-23", [s["id"] for s in stops(plan, "2026-11-23")])
def test_fatal_keeps_old_plan(self):   # site/plan.json holds '{"old": true}'; patch taxi.net.get_text with get (no network) and taxi.plan.plan_day to raise
    self.assertEqual(main(["--root", str(root), "--no-claude", "--no-publish"]), 1)
    self.assertEqual((root/"site"/"plan.json").read_text("utf-8"), '{"old": true}')
def test_load_secrets_env_override(self): ...   # env TICKETMASTER_KEY=ENVKEY beats the file
```

`tests/test_publish.py` (fake `run` records argv lists and returns `CompletedProcess` with chosen return codes):

```python
def test_publish_commits_and_pushes(self):   # diff returns 1
    self.assertEqual(publish(root, date(2026,11,23), run=r), "ok")
    self.assertEqual(r.argvs, [["git","add","site/plan.json"], ["git","diff","--cached","--quiet"],
                               ["git","commit","-m","plan: 2026-11-23"], ["git","push","origin","main"]])
def test_no_changes(self): ...      # diff returns 0 → "no changes", 2 calls
def test_push_fails(self): ...      # push returns 128 → "error: push failed"
def test_write_plan_atomic(self): ...  # writes valid UTF-8 JSON, keeps "✓", leaves no .tmp file
```

- [ ] **Step 2: Run to verify it fails** — `python -m unittest tests.test_scan tests.test_publish -v` → FAIL.
- [ ] **Step 3: Implement `taxi/publish.py` and `scan.py`.**
- [ ] **Step 4: Write `run_scan.cmd`** (exact):

```bat
@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
python scan.py >> "logs\scheduler.log" 2>&1
```

- [ ] **Step 5: Write `.github/workflows/pages.yml`** (exact):

```yaml
name: pages
on:
  push:
    branches: [main]
    paths: ["site/**"]
  workflow_dispatch:
permissions: {contents: read, pages: write, id-token: write}
concurrency: {group: pages, cancel-in-progress: true}
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: {name: github-pages, url: "${{ steps.deploy.outputs.page_url }}"}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with: {path: site}
      - id: deploy
        uses: actions/deploy-pages@v4
```

- [ ] **Step 6: Run the whole suite** — `python -m unittest discover -s tests -t . -v` → all PASS.
- [ ] **Step 7: Smoke-run on the real data without Claude or publishing**

Run: `python scan.py --no-claude --no-publish` → Expected: exit code 0; `logs/scan.log` has a line per source (`cruise: ok, …`, `offices: ok, …`; `ticketmaster: error: no Ticketmaster key` unless a key is configured); `site/plan.json` has 5 days. Then delete it (`Remove-Item site/plan.json`) so the smoke output is never committed.

- [ ] **Step 8: Commit** — `git add scan.py taxi/publish.py run_scan.cmd .github tests && git commit -m "feat: add scan pipeline, git publish and Pages deploy"`

---

### Task 15: Page logic (`site/plan-view.js`, pure functions)

**Files:**
- Create: `site/plan-view.js`
- Test: `tests/js/plan_view.test.js`

**Interfaces:**
- Consumes: `site/strings.json` (`S` = its `"en"` object), the `plan.json` shape.
- Produces (exported as `module.exports` in Node and `window.PlanView` in the browser, via `(function (root) { … })(this)`): `sydNow(d: Date) -> {ymd, hm, dow}`; `fmtTime(hm, S) -> string`; `fmtDate(ymd, S, upper = false) -> string`; `blockLabel(block, S) -> string`; `isStale(generatedAt: string, status: string, now: Date) -> boolean`; `headerStamp(plan, now, S) -> {text, cls: "ok" | "bad"}`; `locateNow(days, now: Date) -> {day, entry} | null`; `minutesFromYou(lat1, lon1, lat2, lon2) -> number` (`max(1, round(km × 1.3 / 35 × 60))`); `esc(s) -> string` (escapes `& < > " '`); `mapsUrl(address) -> string` (`https://www.google.com/maps/dir/?api=1&destination=` + `encodeURIComponent`). Task 16 adds `renderPage` to the same file.

`sydNow` uses `new Intl.DateTimeFormat("en-CA", {timeZone: "Australia/Sydney", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23"}).formatToParts`; `dow` from `Date.UTC(y, m-1, d)`.

Stale check (spec 8.4; not determined by its signature):

```
n = sydNow(now); g = sydNow(new Date(generatedAt))
cutDay = n.hm >= "10:45" ? n.ymd : previousYmd(n.ymd)      // latest 10:45 already passed
return status !== "ok" || (g.ymd + " " + g.hm) < (cutDay + " 10:00")
```

`locateNow`: from `sydNow(now)`: if `hm ≤ "03:00"` the shift date is the previous day and minute = 720 + minutes(hm); else if `hm < "12:00"` the shift date is today and minute = 0; else today and minute = minutes(hm) − 720. Find the day with that date and the entry whose block holds the minute (`start ≤ m < end`, or `m == 900 == end`); if there is no such day, the first entry of the first later day; if none, `null`.

- [ ] **Step 1: Write the failing tests** (`node:test`; `S = JSON.parse(fs.readFileSync("site/strings.json")).en`; `at = s => new Date(s)`):

```js
test("time formats", () => {
  assert.deepEqual(["22:00","17:30","00:00","12:00","01:05"].map(h => fmtTime(h, S)), ["10pm","5:30pm","12am","12pm","1:05am"]);
  assert.deepEqual([[240,360],[600,720],[720,840],[0,120],[840,900],[120,600],[360,900]].map(b => blockLabel(b, S)),
    ["4 – 6 PM","10 PM – 12 AM","12 – 2 AM","12 – 2 PM","2 – 3 AM","2 – 10 PM","6 PM – 3 AM"]);
  assert.equal(fmtDate("2026-11-23", S), "Mon 23 Nov"); assert.equal(fmtDate("2026-11-24", S, true), "TUE 24 NOV");
  assert.deepEqual(sydNow(at("2026-11-23T03:30:00Z")), {ymd: "2026-11-23", hm: "14:30", dow: 1});
  assert.equal(sydNow(at("2026-04-05T00:00:00Z")).hm, "10:00");   // after DST ends
});
test("stale check", () => {
  const g = "2026-11-23T10:02:00+11:00";
  assert.equal(isStale(g, "ok", at("2026-11-23T14:00:00+11:00")), false);
  assert.equal(isStale(g, "ok", at("2026-11-24T01:30:00+11:00")), false);
  assert.equal(isStale(g, "ok", at("2026-11-24T10:44:00+11:00")), false);
  assert.equal(isStale(g, "ok", at("2026-11-24T10:46:00+11:00")), true);
  assert.equal(isStale(g, "partial", at("2026-11-23T14:00:00+11:00")), true);
  assert.equal(isStale("2026-04-04T10:02:00+11:00", "ok", at("2026-04-05T09:00:00+10:00")), false);
});
test("header stamp", () => {
  const p = {generated_at: "2026-11-23T10:02:00+11:00", status: "ok"};
  assert.deepEqual(headerStamp(p, at("2026-11-23T14:00:00+11:00"), S), {text: "✓ Updated 10:02am", cls: "ok"});
  assert.deepEqual(headerStamp(p, at("2026-11-24T11:00:00+11:00"), S), {text: "⚠ Old plan, from Mon 10:02am", cls: "bad"});
  assert.deepEqual(headerStamp({...p, status: "partial"}, at("2026-11-23T14:00:00+11:00"), S), {text: "⚠ Some sources failed · 10:02am", cls: "bad"});
});
test("locateNow", () => {
  const days = [{date: "2026-11-23", entries: [{block: [0,240]}, {block: [240,360]}, {block: [360,900]}]},
                {date: "2026-11-24", entries: [{block: [0,900]}]}];
  const L = s => locateNow(days, at(s));
  assert.deepEqual(L("2026-11-23T09:00:00+11:00"), {day: 0, entry: 0});
  assert.deepEqual(L("2026-11-23T17:00:00+11:00"), {day: 0, entry: 1});
  assert.deepEqual(L("2026-11-23T23:59:00+11:00"), {day: 0, entry: 2});
  assert.deepEqual(L("2026-11-24T02:30:00+11:00"), {day: 0, entry: 2});
  assert.deepEqual(L("2026-11-24T03:00:00+11:00"), {day: 0, entry: 2});
  assert.deepEqual(L("2026-11-24T03:30:00+11:00"), {day: 1, entry: 0});
  assert.equal(L("2026-11-25T10:00:00+11:00"), null);
  const wk = [{date: "2026-11-28", entries: [{block: [0,900]}]}, {date: "2026-11-30", entries: [{block: [0,900]}]}];
  assert.deepEqual(locateNow(wk, at("2026-11-29T01:00:00+11:00")), {day: 0, entry: 0});   // Sat overtime
  assert.deepEqual(locateNow(wk, at("2026-11-29T14:00:00+11:00")), {day: 1, entry: 0});   // Sunday → Monday
});
test("helpers", () => {
  const m = minutesFromYou(-33.8688, 151.2093, -33.8474, 151.0636); assert.ok(m >= 29 && m <= 32);
  assert.equal(minutesFromYou(-33.8, 151.2, -33.8, 151.2), 1);
  assert.equal(esc(`<a href="x">&'`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
  assert.equal(mapsUrl("Bennelong Point, Sydney NSW 2000"), "https://www.google.com/maps/dir/?api=1&destination=Bennelong%20Point%2C%20Sydney%20NSW%202000");
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test "tests/js/*.test.js"` → FAIL (cannot find module).
- [ ] **Step 3: Implement `site/plan-view.js`.** Block labels: hour of each end = `(12 + m/60) % 24` shown 12-hour; `"4 – 6 PM"` when both ends share AM/PM, else `"10 PM – 12 AM"`.
- [ ] **Step 4: Run to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git add site/plan-view.js tests/js && git commit -m "feat: add page time, stale and Go Now logic"`

---

### Task 16: Phone page (render, shell, offline, home screen)

**Files:**
- Create: `site/index.html`, `site/style.css`, `site/app.js`, `site/sw.js`, `site/manifest.webmanifest`, `site/icon.svg`, `tests/fixtures/sample_plan.json`, `site/plan.json` (copy of the sample)
- Modify: `site/plan-view.js` (add `renderPage`)
- Test: `tests/js/render.test.js`

**Interfaces:**
- Consumes: Task 15 functions; `S`; plan shape.
- Produces: `renderPage(plan, S, now: Date, pos: {lat, lon} | null, toggled: Set<string>) -> string`. A card is open when `(isGoNow !== toggled.has(entry.id))`, so the Go Now card starts open and any card he toggles keeps its state.

Markup follows `.superpowers/brainstorm/1255-1795389082/content/full-ui.html` (the approved mockup; gitignored, so read it locally) exactly, with these changes: no phone frame or note; `body` background `#000`; `.lbl` and `.tap` at 20 px (spec: body text ≥ 20 px); header stamp `<span class="upd ok">` green `#30d158` or `<span class="upd bad">` red `#ff453a`; no score breakdown and no Refresh button. Structure: `.top` header (`fmtDate(today)` + stamp) → `GO NOW` heading + the Go Now entry (stop as `<details class="now" data-id>` with the one-line `desc` in the summary; quiet as `.quiet`) → `REST OF TODAY` heading (or the day heading when Go Now's day is not the current shift date) + the later entries of that day → for each later day a `.hd` heading `fmtDate(date, S, true)` + all its entries. Past days and past entries are not shown. If `locateNow` is `null` or there are no days: header + `S.no_plan`. Closed card: `.lbl` block label, `.row1` name + `.sc` score (`class="sc"` when score ≥ 55, else `class="sc mid"`), `.p` exit phrase (`S["exit_" + kind]`), `.tap` (`tap_close` when open, else `tap_open`). Open part `.more`: `.s` desc (non-Go-Now cards), `.f` lines — address; `starts_ends` when `start`; `crowd`; `wait` when non-empty; drive line (`from_you` on the Go Now card when `pos` and the stop has lat/lon, else `from_prev` with `drive_from`, or `from_cbd` when `drive_from` is null) — then `<a class="go" href="mapsUrl(address)" target="_blank" rel="noopener">` with `S.navigate`. Quiet: `.lbl` `"<blockLabel> · QUIET"`, `<b>` `free_until` (`fmtTime(until)`, `next`) or `free_rest`, `.alt` `try_nearby` with names joined by `" · "` (omitted when empty). Every value from the plan goes through `esc()`.

`app.js` (browser glue, no logic worth unit-testing): register `sw.js`; fetch `strings.json` once and `plan.json?t=<Date.now()>` with `{cache: "no-store"}` on load and on `visibilitychange` to visible; on fetch failure keep what is on screen; ask `navigator.geolocation.getCurrentPosition` (timeout 10 s, maximumAge 5 min) on each load and re-render when it answers, ignoring a refusal; re-render every 60 s; keep `toggled` up to date from each `<details>` `toggle` event; skip DOM writes when the HTML string is unchanged. All URLs relative (the site lives under `/<repo>/`).

`sw.js`: network-first for same-origin GET; successful responses stored with `cache.put` under the URL without its query string; on network failure `caches.match(request, {ignoreSearch: true})`. `manifest.webmanifest`: `name`/`short_name` "Taxi Plan", `start_url "."`, `display "standalone"`, `background_color`/`theme_color "#000000"`, one icon `icon.svg` (`sizes "any"`, `type "image/svg+xml"`; a yellow rounded square with black "TAXI"). `index.html`: `lang="en"`, viewport meta, `theme-color`, manifest link, `apple-mobile-web-app-capable`, `<div id="app">`, scripts `plan-view.js` then `app.js`.

- [ ] **Step 1: Write `tests/fixtures/sample_plan.json`** from the mockup data: `generated_at "2026-11-23T10:02:00+11:00"`, `status "ok"`. Day `2026-11-23`: quiet `[0,240]` until `"16:00"` next `"KPMG Barangaroo"`; stop `office:kpmg-barangaroo:normal:2026-11-23` `[240,360]` "KPMG Barangaroo" score 60 kind office exit `"17:30"` desc "Big accounting firm, about 3,000 staff. Many use Cabcharge." address "Tower 3, 300 Barangaroo Ave, Barangaroo NSW 2000", size 3000, ages 30–55, wait "Barangaroo Ave rank", drive 6 from null, lat/lon set; stop `gf:icc` `[360,480]` "ICC Sydney conference" 58 exit `"18:30"` drive 8 from "KPMG Barangaroo"; quiet `[480,600]` until `"22:00"` next `"Opera House"` nearby `["The Star", "Shangri-La", "Four Seasons"]`; stop `tm:opera1` `[600,720]` "Opera House" 66 kind event start `"19:30"` exit `"22:15"` address "Bennelong Point, Sydney NSW 2000"; quiet `[720,900]` nulls. Day `2026-11-24`: stop cruise `[0,120]` score 45; quiet `[120,240]` until `"16:00"` next "Deloitte · Quay Quarter" nearby `["Hilton", "Westin"]`; stop Deloitte `[240,360]` 57; quiet `[360,900]`. Day `2026-11-25`: quiet `[0,600]`; stop "Concert · Qudos Arena" `[600,720]` 72; quiet `[720,900]`. Copy it to `site/plan.json` (the first real scan replaces it).

- [ ] **Step 2: Write the failing tests** `tests/js/render.test.js`:

```js
const P = JSON.parse(fs.readFileSync("tests/fixtures/sample_plan.json")), five = at("2026-11-23T17:00:00+11:00");
test("layout at 5pm", () => {
  const h = renderPage(P, S, five, null, new Set());
  for (const s of ["GO NOW", "REST OF TODAY", "TUE 24 NOV", "WED 25 NOV", "✓ Updated 10:02am", 'class="sc mid">45', 'class="sc">60',
                   "Free time until 10pm (Opera House)", "Or try nearby: The Star · Shangri-La · Four Seasons", "🚕 6 min from the CBD",
                   "dir/?api=1&amp;destination=Bennelong%20Point%2C%20Sydney%20NSW%202000"]) assert.ok(h.includes(s), s);
  assert.equal(h.split('<details class="now" open').length - 1, 1);
  assert.ok(h.indexOf("KPMG Barangaroo") < h.indexOf("REST OF TODAY"));
  assert.ok(!h.includes("Free time until 4pm (KPMG Barangaroo)"));          // past entry hidden
});
test("go now moves with the clock", () => {
  const h = renderPage(P, S, at("2026-11-23T18:30:00+11:00"), null, new Set());
  assert.ok(h.indexOf("ICC Sydney conference") < h.indexOf("REST OF TODAY"));
  const q = renderPage(P, S, at("2026-11-23T21:00:00+11:00"), null, new Set());
  assert.ok(q.indexOf('class="quiet"') < q.indexOf("REST OF TODAY"));
});
test("toggled go-now card stays closed", () => {
  const h = renderPage(P, S, five, null, new Set(["office:kpmg-barangaroo:normal:2026-11-23"]));
  assert.ok(!h.includes('<details class="now" open'));
});
test("location shows min from you", () => {
  assert.ok(renderPage(P, S, five, {lat: -33.8688, lon: 151.2093}, new Set()).includes("min from you"));
});
test("escapes Claude text", () => {
  const p = structuredClone(P); p.days[0].entries[2].desc = '<img src=x onerror=alert(1)> & "q"';
  const h = renderPage(p, S, five, null, new Set());
  assert.ok(h.includes("&lt;img src=x onerror=alert(1)&gt; &amp; &quot;q&quot;")); assert.ok(!h.includes("<img"));
});
test("stale and empty", () => {
  assert.ok(renderPage(P, S, at("2026-11-24T11:00:00+11:00"), null, new Set()).includes('class="upd bad"'));
  assert.ok(renderPage({...P, days: []}, S, five, null, new Set()).includes(S.no_plan));
});
```

- [ ] **Step 3: Run to verify it fails** — `node --test "tests/js/*.test.js"` → FAIL (`renderPage` not a function).
- [ ] **Step 4: Implement `renderPage` and the page files.**
- [ ] **Step 5: Run to verify it passes** — `node --test "tests/js/*.test.js"` → all PASS.
- [ ] **Step 6: Check it in a browser**

Run: `python -m http.server 8000 -d site`, open `http://localhost:8000/` at 390×800 (mobile emulation) next to the mockup. Expected: same black/yellow look and text sizes as the mockup; tapping a card opens it in place and tapping again closes it; Navigate opens Google Maps directions; the header shows a red "⚠ Old plan…" stamp when today is after 24 Nov 2026 10:45 (sample data); no console errors. Stop the server.

- [ ] **Step 7: Commit** — `git add site tests && git commit -m "feat: add phone page with Go Now, quiet blocks and offline support"`

---

### Task 17: Owner's one-time setup (done by the owner, by hand)

**Files:** `secrets.json` (local only), Windows Task Scheduler, GitHub settings. Nothing new is committed except the daily `site/plan.json`.

**Interfaces:**
- Consumes: `scan.py`, `run_scan.cmd`, `.github/workflows/pages.yml`, `secrets.example.json`.
- Produces: a public Pages URL `https://<username>.github.io/taxi-plan/`, a daily 10:00 task, the page on the phone's home screen.

All commands run in PowerShell from the project folder.

- [ ] **Step 1: GitHub account and repo** — sign up at `https://github.com/signup` (free). Then `https://github.com/new`: name `taxi-plan`, **Public**, no README/.gitignore/licence. Optional for privacy: GitHub → Settings → Emails → tick "Keep my email addresses private", copy the `…@users.noreply.github.com` address and run `git config user.email "<that address>"` in the project.
- [ ] **Step 2: First push without `gh`** — Git for Windows already includes Git Credential Manager (`git config --show-origin --get credential.helper` prints `manager`).

```powershell
git remote add origin https://github.com/<username>/taxi-plan.git
git push -u origin main
```

A browser window opens to sign in to GitHub; approve it. The credential is stored in Windows Credential Manager, so the daily scan pushes without asking again. Expected: `branch 'main' set up to track 'origin/main'`.

- [ ] **Step 3: Turn on Pages** — repo → Settings → Pages → Build and deployment → Source: **GitHub Actions**. Then repo → Actions → "pages" → Run workflow. Expected: a green run and the site at `https://<username>.github.io/taxi-plan/` (showing the sample plan with a red "Old plan" stamp).
- [ ] **Step 4: Ticketmaster key** — sign up at `https://developer.ticketmaster.com/` → My Apps → the default app → copy the **Consumer Key**. `Copy-Item secrets.example.json secrets.json` and paste the key as `"ticketmaster_key"` (this file is gitignored; check with `git status` that it is not listed).
- [ ] **Step 5: Claude token for unattended runs** — run `claude setup-token`, sign in, and paste the printed token into `secrets.json` as `"claude_oauth_token"`. (Scheduled runs cannot open a sign-in window; the CLI recommends this token for unattended jobs.)
- [ ] **Step 6: First live scan** — `python -m pip install -r requirements.txt`, then `python scan.py --no-publish`. Expected: exit code 0; `logs/scan.log` shows `ticketmaster: ok, <n> candidates` with n > 0 and every source `ok`; `site/plan.json` has `"status": "ok"`. If any line says `error`, send `logs/scan.log` to the developer before continuing.
- [ ] **Step 7: Schedule 10:00 daily, catching up after a missed start** — check `Get-TimeZone` shows `AUS Eastern Standard Time` (the trigger uses the laptop's clock), then:

```powershell
$dir = (Get-Location).Path
$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"`"$dir\run_scan.cmd`"`"" -WorkingDirectory $dir
$trigger  = New-ScheduledTaskTrigger -Daily -At "10:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "TaxiPlanScan" -Action $action -Trigger $trigger -Settings $settings -Description "Daily taxi plan scan"
Start-ScheduledTask -TaskName "TaxiPlanScan"
```

`-StartWhenAvailable` is "Run task as soon as possible after a scheduled start is missed". The task runs while the owner is logged in (the laptop stays on and logged in). Expected after a few minutes: `(Get-ScheduledTaskInfo -TaskName TaxiPlanScan).LastTaskResult` is `0`, `logs/scan.log` has a new run, GitHub shows a commit `plan: <date>`, and the page header turns green ("✓ Updated …") about a minute later.
- [ ] **Step 8: Phone home screen** — open `https://<username>.github.io/taxi-plan/` on the phone. Android Chrome: ⋮ → **Add to Home screen** → Install. iPhone Safari: Share → **Add to Home Screen** → Add. Open it from the icon and tap **Allow** when it asks for location (for "min from you"; the page works without it).

---

## After the build (not tasks in this plan)

Per spec 8.5, once all tasks pass, a bug-finding code reviewer and a separate improvement reviewer (Opus) each go over the whole repo. Their findings are merged into one fix list, the fixes are made (Sonnet implementers, same TDD steps), and the loop repeats a few times until it is ready to ship.
