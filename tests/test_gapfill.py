import copy
import json
import unittest
from datetime import date, datetime

from taxi.claude import ClaudeError
from taxi.gapfill import event_to_candidate, gapfill, gapfill_prompt, validate_disruption, validate_event
from taxi.model import SYD, working_days
from tests.helpers import TABLE, W, cand

TODAY = date(2026, 11, 23)
DAYS = working_days(date(2026, 11, 23))
AREAS = set(TABLE["areas"])
GOOD = {"name": "Medical Congress", "venue": "ICC Sydney", "address": "14 Darling Dr, Sydney NSW 2000", "area": "Pyrmont",
        "kind": "event", "date": "2026-11-24", "start": "09:00", "exit": "18:30",
        "source_url": "https://www.iccsydney.com.au/whats-on/x",
        "median_age": 45, "age_lo": 30, "age_hi": 60, "size": 3000, "pays": 0.6, "spend": 0.8,
        "wait": "Darling Dr", "desc": "Big medical congress."}
VENUES = [{"name": "ICC Sydney", "what_on_url": "https://www.iccsydney.com.au/whats-on"}]


def fake(*responses):
    def call(prompt):
        call.prompts.append(prompt)
        r = responses[len(call.prompts) - 1]
        if isinstance(r, Exception):
            raise r
        return r
    call.prompts = []
    return call


def reply(events=(), disruptions=()):
    return json.dumps({"events": list(events), "disruptions": list(disruptions)})


def empty():
    return {"estimates": {}, "gapfill": {}}


def run(call, existing=(), cache=None, alive=lambda u: True, w=W):
    cache = empty() if cache is None else cache
    return gapfill(call, VENUES, DAYS, list(existing), TABLE, cache, TODAY, w, "English", alive=alive), cache


class GapfillTests(unittest.TestCase):
    def test_prompt(self):
        p = gapfill_prompt([{"name": "Sydney Opera House", "what_on_url": "https://www.sydneyoperahouse.com/whats-on"}],
                           DAYS, ["Opera House | 2026-11-24"], ["CBD", "Pyrmont"], 8, "English")
        for s in ("Sydney Opera House", "https://www.sydneyoperahouse.com/whats-on", "2026-11-24", "at most 8",
                  "Opera House | 2026-11-24", "Pyrmont", "English", "source_url", "trackwork"):
            self.assertIn(s, p)

    def test_valid_event(self):
        (cands, dis, status), cache = run(fake(reply([GOOD])))
        c = cands[0]
        self.assertTrue(c.id.startswith("gf:"))
        self.assertEqual((c.lat, c.lon), TABLE["areas"]["Pyrmont"])
        self.assertEqual(c.start, datetime(2026, 11, 24, 9, 0, tzinfo=SYD))
        self.assertEqual(c.exit, datetime(2026, 11, 24, 18, 30, tzinfo=SYD))
        self.assertEqual((c.kind, c.size), ("event", 3000))
        self.assertIn(c.id, cache["gapfill"])
        self.assertEqual(cache["gapfill"][c.id]["seen"], "2026-11-23")
        self.assertEqual(status, "ok")

    def test_drops(self):
        bad = [{k: v for k, v in GOOD.items() if k != "source_url"} | {"name": "no url"},
               dict(GOOD, name="bad date", date="2026-11-29"),
               dict(GOOD, name="bad area", area="Bondi"),
               dict(GOOD, name="bad size", size=-5),
               dict(GOOD, name="long name " * 20)]
        (cands, _, _), cache = run(fake(reply(bad)))
        self.assertEqual((cands, cache["gapfill"]), ([], {}))
        # dead link
        (cands, _, _), cache = run(fake(reply([GOOD])), alive=lambda u: False)
        self.assertEqual((cands, cache["gapfill"]), ([], {}))
        # overlaps an existing Pyrmont candidate starting 30 min later; one at 14:00 does not
        near = cand(id="tm:N", area="Pyrmont", start=datetime(2026, 11, 24, 9, 30, tzinfo=SYD))
        far = cand(id="tm:F", area="Pyrmont", start=datetime(2026, 11, 24, 14, 0, tzinfo=SYD))
        other_area = cand(id="tm:O", area="CBD", start=datetime(2026, 11, 24, 9, 30, tzinfo=SYD))
        (cands, _, _), _ = run(fake(reply([GOOD])), existing=[near])
        self.assertEqual(cands, [])
        (cands, _, _), _ = run(fake(reply([GOOD])), existing=[far, other_area])
        self.assertEqual(len(cands), 1)

    def test_cap(self):
        w = copy.deepcopy(W)
        w["claude"]["gapfill_max_events"] = 2
        evs = [dict(GOOD, name=f"Show {i}", start=f"{9 + i * 3:02d}:00", exit=f"{10 + i * 3:02d}:00") for i in range(4)]
        with self.assertLogs("taxi.gapfill", "WARNING"):
            (cands, _, _), _ = run(fake(reply(evs)), w=w)
        self.assertEqual(len(cands), 2)

    def test_disruptions(self):
        ok = {"area": "ALL", "date": "2026-11-24", "from": "00:00", "to": "23:59", "what": "strike",
              "source_url": "https://transportnsw.info/x"}
        self.assertIsNotNone(validate_disruption(ok, set(DAYS), AREAS))
        self.assertIsNone(validate_disruption(dict(ok, area="ALL", what="trackwork"), set(DAYS), AREAS))
        self.assertIsNotNone(validate_disruption(dict(ok, area="CBD", what="trackwork"), set(DAYS), AREAS))
        self.assertIsNone(validate_disruption(dict(ok, area="Mars"), set(DAYS), AREAS))
        self.assertIsNone(validate_disruption(dict(ok, what="party"), set(DAYS), AREAS))
        self.assertIsNone(validate_disruption(dict(ok, **{"from": "20:00", "to": "10:00"}), set(DAYS), AREAS))
        self.assertIsNone(validate_disruption(dict(ok, source_url="ftp://x"), set(DAYS), AREAS))
        (_, dis, _), _ = run(fake(reply(disruptions=[ok, dict(ok, area="Mars")])))
        self.assertEqual(dis, [ok])

    def test_hostile_values_do_not_crash(self):
        ok = {"area": "ALL", "date": "2026-11-24", "from": "00:00", "to": "23:59", "what": "strike", "source_url": "https://t.nsw/x"}
        self.assertIsNone(validate_event(dict(GOOD, area=["Pyrmont"]), set(DAYS), AREAS))
        self.assertIsNone(validate_disruption(dict(ok, area=["ALL"]), set(DAYS), AREAS))
        self.assertIsNone(validate_event(dict(GOOD, date="20261124"), set(DAYS), AREAS))

        def boom(u):
            raise ValueError("bad url")
        with self.assertLogs("taxi.gapfill", "INFO"):
            (cands, _, status), cache = run(fake(reply([GOOD])), alive=boom)
        self.assertEqual((cands, cache["gapfill"], status), ([], {}, "ok"))

    def test_dedupes_against_own_cache(self):
        cache, cid = self.cached("2026-11-24")
        call = fake(reply([dict(GOOD, name="Medical Congress 2026")]))
        (cands, _, _), cache = run(call, cache=cache)
        self.assertIn("ICC Sydney | 2026-11-24", call.prompts[0])
        self.assertEqual([c.id for c in cands], [cid])
        self.assertEqual(list(cache["gapfill"]), [cid])

    def test_cached_dropped_when_existing_now_covers_it(self):
        cache, _ = self.cached("2026-11-24")
        tm = cand(id="tm:N", area="Pyrmont", start=datetime(2026, 11, 24, 9, 15, tzinfo=SYD))
        (cands, _, _), _ = run(None, existing=[tm], cache=cache)
        self.assertEqual(cands, [])

    def test_validate_event_returns_fields(self):
        ev = validate_event(dict(GOOD, junk=1), set(DAYS), AREAS)
        self.assertNotIn("junk", ev)
        self.assertEqual(event_to_candidate(ev, TABLE).name, "Medical Congress")

    def cached(self, day):
        ev = validate_event(dict(GOOD, date=day), set(DAYS), AREAS) or dict(GOOD, date=day)
        c = event_to_candidate(ev, TABLE)
        return {"estimates": {}, "gapfill": {c.id: {"event": ev, "seen": "2026-11-23"}}}, c.id

    def test_error_keeps_cached_future(self):
        cache, cid = self.cached("2026-11-25")
        call = fake(ClaudeError("auth"))
        (cands, dis, status), _ = run(call, cache=cache)
        self.assertEqual([c.id for c in cands], [cid])
        self.assertEqual(dis, [])
        self.assertTrue(status.startswith("error"))
        self.assertEqual(len(call.prompts), 1)

    def test_skipped_without_call(self):
        cache, cid = self.cached("2026-11-25")
        (cands, dis, status), _ = run(None, cache=cache)
        self.assertEqual(([c.id for c in cands], dis, status), ([cid], [], "skipped"))

    def test_cached_past_not_returned(self):
        cache, _ = self.cached("2026-11-22")
        (cands, _, _), _ = run(None, cache=cache)
        self.assertEqual(cands, [])


if __name__ == "__main__":
    unittest.main()
