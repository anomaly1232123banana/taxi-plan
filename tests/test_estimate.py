import copy
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from taxi.cache import load_cache, prune, save_cache
from taxi.claude import ClaudeError
from taxi.estimate import EST_KEYS, estimate_events, validate_estimate
from taxi.model import SYD
from tests.helpers import W, cand

TODAY = date(2026, 11, 23)


def est(id, **kw):
    return {"id": id, **dict(median_age=50, age_lo=35, age_hi=65, size=2000, pays=0.1, spend=0.8,
                             exit="22:15", wait="Macquarie St", desc="Opera night."), **kw}


def fake(*responses):
    def call(prompt):
        call.prompts.append(prompt)
        r = responses[len(call.prompts) - 1]
        if isinstance(r, Exception):
            raise r
        return r
    call.prompts = []
    return call


def empty():
    return {"estimates": {}, "gapfill": {}}


class EstimateTests(unittest.TestCase):
    def setUp(self):
        self.A = cand(id="tm:A", name="Opera A", start=datetime(2026, 11, 23, 19, 30, tzinfo=SYD))
        self.B = cand(id="tm:B", name="Opera B", start=datetime(2026, 11, 24, 20, 0, tzinfo=SYD))

    def cached(self, *ids):
        cache = empty()
        for i in ids:
            cache["estimates"][i] = {"est": validate_estimate(est(i)), "seen": "2026-11-01"}
        return cache

    def test_one_call_for_uncached(self):
        call = fake(json.dumps([est("tm:A"), est("tm:B", exit="23:00")]))
        cache = empty()
        got, status = estimate_events([self.A, self.B], cache, call, W, TODAY, "English")
        self.assertEqual((len(call.prompts), status), (1, "ok"))
        self.assertIn("tm:A", call.prompts[0])
        self.assertIn("tm:B", call.prompts[0])
        self.assertIn("English", call.prompts[0])
        self.assertEqual(self.A.exit, datetime(2026, 11, 23, 22, 15, tzinfo=SYD))
        self.assertEqual(self.B.exit, datetime(2026, 11, 24, 23, 0, tzinfo=SYD))
        self.assertEqual(cache["estimates"]["tm:A"]["seen"], "2026-11-23")

    def test_cached_needs_no_call(self):
        call = fake()
        cache = self.cached("tm:A", "tm:B")
        got, status = estimate_events([self.A, self.B], cache, call, W, TODAY, "English")
        self.assertEqual(len(call.prompts), 0)
        self.assertEqual([c.id for c in got], ["tm:A", "tm:B"])
        self.assertEqual(status, "ok")
        self.assertEqual((self.A.size, self.A.desc), (2000, "Opera night."))
        self.assertEqual(cache["estimates"]["tm:A"]["seen"], "2026-11-23")
        self.assertEqual(cache["estimates"]["tm:B"]["seen"], "2026-11-23")

    def test_retry_missing_once(self):
        call = fake(json.dumps([est("tm:A")]), json.dumps([est("tm:B")]))
        got, status = estimate_events([self.A, self.B], empty(), call, W, TODAY, "English")
        self.assertEqual(len(call.prompts), 2)
        self.assertIn("tm:B", call.prompts[1])
        self.assertNotIn("tm:A", call.prompts[1])
        self.assertEqual([c.id for c in got], ["tm:A", "tm:B"])

    def test_still_missing_dropped(self):
        call = fake(json.dumps([est("tm:A")]), json.dumps([est("tm:A")]))
        got, status = estimate_events([self.A, self.B], empty(), call, W, TODAY, "English")
        self.assertEqual([c.id for c in got], ["tm:A"])
        self.assertEqual((len(call.prompts), status), (2, "ok"))
        self.assertIsNone(self.B.size)

    def test_invalid_and_unknown_count_as_missing(self):
        call = fake(json.dumps([est("tm:A", pays=1.5), est("tm:ZZZ")]), json.dumps([est("tm:A")]))
        got, _ = estimate_events([self.A], empty(), call, W, TODAY, "English")
        self.assertEqual(len(call.prompts), 2)
        self.assertEqual([c.id for c in got], ["tm:A"])

    def test_non_string_id_ignored(self):
        call = fake(json.dumps([dict(est("tm:A"), id=["tm:A"])]), json.dumps([est("tm:A")]))
        got, _ = estimate_events([self.A], empty(), call, W, TODAY, "English")
        self.assertEqual(([c.id for c in got], len(call.prompts)), (["tm:A"], 2))

    def test_nothing_valid_is_error(self):
        call = fake(json.dumps([est("tm:A", pays=9)]), json.dumps([]))
        got, status = estimate_events([self.A], empty(), call, W, TODAY, "English")
        self.assertEqual((got, status), ([], "error: no valid estimates"))

    def test_claude_error(self):
        call = fake(ClaudeError("auth"))
        got, status = estimate_events([self.A, self.B], self.cached("tm:A"), call, W, TODAY, "English")
        self.assertEqual([c.id for c in got], ["tm:A"])
        self.assertTrue(status.startswith("error: auth"))
        self.assertEqual(len(call.prompts), 1)

    def test_skipped_without_call(self):
        got, status = estimate_events([self.A, self.B], self.cached("tm:A"), None, W, TODAY, "English")
        self.assertEqual(([c.id for c in got], status), (["tm:A"], "skipped"))

    def test_batch_cap(self):
        w = copy.deepcopy(W)
        w["claude"]["estimate_batch_max"] = 1
        call = fake(json.dumps([est("tm:A")]))
        with self.assertLogs("taxi.estimate", "WARNING"):
            got, _ = estimate_events([self.B, self.A], empty(), call, w, TODAY, "English")
        self.assertIn("tm:A", call.prompts[0])
        self.assertNotIn("tm:B", call.prompts[0])
        self.assertEqual([c.id for c in got], ["tm:A"])

    def test_fenced_reply(self):
        call = fake("```json\n" + json.dumps([est("tm:A")]) + "\n```")
        got, status = estimate_events([self.A], empty(), call, W, TODAY, "English")
        self.assertEqual(([c.id for c in got], status, len(call.prompts)), (["tm:A"], "ok", 1))

    def test_validate(self):
        self.assertIsNone(validate_estimate(dict(est("x"), pays=1.5)))
        self.assertIsNone(validate_estimate(dict(est("x"), age_lo=60)))
        self.assertIsNone(validate_estimate(dict(est("x"), exit="25:00")))
        self.assertIsNone(validate_estimate(dict(est("x"), desc="x" * 201)))
        self.assertNotIn("foo", validate_estimate(dict(est("x"), foo=1)))
        self.assertEqual(set(validate_estimate(est("x"))), set(EST_KEYS))

    def test_cache_file(self):
        with tempfile.TemporaryDirectory() as d, self.assertLogs("taxi.cache", "WARNING"):
            p = Path(d) / "cache" / "estimates.json"
            self.assertEqual(load_cache(p), empty())
            p.parent.mkdir()
            p.write_text("{not json", encoding="utf-8")
            self.assertEqual(load_cache(p), empty())
            self.assertTrue((p.parent / "estimates.json.bad").exists())
            self.assertFalse(p.exists())
            # a second corrupt file replaces the old .bad (os.replace)
            p.write_text("[1]", encoding="utf-8")
            self.assertEqual(load_cache(p), empty())
            c = self.cached("tm:A")
            save_cache(c, Path(d) / "new" / "estimates.json")
            self.assertEqual(load_cache(Path(d) / "new" / "estimates.json"), c)
            self.assertFalse((Path(d) / "new" / "estimates.json.tmp").exists())

    def test_prune(self):
        ev = {"event": {"date": "2026-11-24"}}
        cache = {"estimates": {"old": {"est": {}, "seen": "2026-10-01"}, "new": {"est": {}, "seen": "2026-11-01"}},
                 "gapfill": {"past": {**ev, "event": {"date": "2026-11-22"}, "seen": "2026-11-20"},
                             "today": {"event": {"date": "2026-11-23"}, "seen": "2026-11-20"}}}
        prune(cache, TODAY, 30)
        self.assertEqual(list(cache["estimates"]), ["new"])
        self.assertEqual(list(cache["gapfill"]), ["today"])


    def test_prompt_has_calibration_anchors(self):
        from taxi.estimate import estimate_prompt
        p = estimate_prompt([], "English")
        self.assertIn("Opera House", p)
        self.assertIn("rave", p)


if __name__ == "__main__":
    unittest.main()
