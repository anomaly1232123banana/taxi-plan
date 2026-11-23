import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from scan import load_secrets, main, run
from taxi.claude import ClaudeError
from taxi.model import SYD
from taxi.net import SourceError
from tests.helpers import AREAS_JSON, OFFICE, ROOT, assert_covers

NOW = datetime(2026, 11, 23, 10, 0, tzinfo=SYD)
HDR = {"estimate": True, "researched": "2026-11-23"}
EST = [{"id": "tm:Z1", "median_age": 45, "age_lo": 35, "age_hi": 60, "size": 18000, "pays": 0.05, "spend": 0.6,
        "exit": "22:45", "wait": "Olympic Blvd rank", "desc": "Rock concert."}]


def fx(name):
    return (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8")


def wjson(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def make_root(tmp: Path) -> Path:
    wjson(tmp / "data" / "areas.json", AREAS_JSON)
    wjson(tmp / "data" / "offices.json", HDR | {"offices": [OFFICE]})
    place = {"kind": "hotel", "area": "CBD", "lat": -33.8688, "lon": 151.2093, "busy": [["18:00", "23:00"]], "wait": "Front rank"}
    wjson(tmp / "data" / "steady.json", HDR | {"places": [
        place | {"id": "h1", "name": "Hotel One", "address": "1 George St, Sydney NSW 2000"},
        place | {"id": "h2", "name": "Hotel Two", "address": "2 George St, Sydney NSW 2000"}]})
    wjson(tmp / "data" / "gapfill_venues.json", HDR | {"venues": [
        {"name": "ICC Sydney", "kind": "venue", "area": "Pyrmont", "address": "14 Darling Dr, Sydney NSW 2000",
         "what_on_url": "https://www.iccsydney.com.au/whats-on"}]})
    shutil.copy(ROOT / "data" / "holidays.json", tmp / "data" / "holidays.json")
    shutil.copy(ROOT / "weights.json", tmp / "weights.json")
    (tmp / "site").mkdir(exist_ok=True)
    shutil.copy(ROOT / "site" / "strings.json", tmp / "site" / "strings.json")
    wjson(tmp / "secrets.json", {"ticketmaster_key": "SECRETKEY123"})
    return tmp


def get(url):
    if "ticketmaster" in url:
        return fx("tm_page.json")
    if "open-meteo" in url:
        return fx("weather_dry.json")
    raise AssertionError("unexpected url " + url)


def bad_tm(url):
    if "ticketmaster" in url:
        raise SourceError("app.ticketmaster.com: HTTP 500")
    return get(url)


def fake_claude(prompt, args, timeout):
    if "WebSearch,WebFetch" in args:
        return json.dumps({"events": [], "disruptions": []})
    return json.dumps(EST)


def stops(plan, ymd):
    day = next(d for d in plan["days"] if d["date"] == ymd)
    return [e for e in day["entries"] if e["type"] == "stop"]


class TestScan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_root(Path(self._tmp.name))
        self.pub = Mock(return_value="ok")

    def scan(self, **kw):
        kw = {"get_text": get, "call_claude": fake_claude, "publish_fn": self.pub} | kw
        return run(NOW, self.root, **kw)

    def test_end_to_end(self):
        plan = self.scan()
        self.assertEqual(plan["status"], "ok")
        self.assertEqual([d["date"] for d in plan["days"]], ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"])
        z = next(s for s in stops(plan, "2026-11-25") if s["id"] == "tm:Z1")
        self.assertEqual((z["score"], z["block"]), (62, [600, 720]))
        self.assertEqual([s["id"] for s in stops(plan, "2026-11-23")],
                         ["office:kpmg-barangaroo:normal:2026-11-23",
                          "office:kpmg-barangaroo:late:2026-11-23"])
        self.assertEqual(json.loads((self.root / "site" / "plan.json").read_text("utf-8")), plan)
        self.assertIn("tm:Z1", json.loads((self.root / "cache" / "estimates.json").read_text("utf-8"))["estimates"])
        self.pub.assert_called_once()
        self.assertNotIn("SECRETKEY123", json.dumps(plan))
        for d in plan["days"]:
            assert_covers(self, d["entries"])

    def test_page_fields_never_null(self):
        plan = self.scan()
        self.assertTrue(plan["generated_at"])
        for d in plan["days"]:
            for e in d["entries"]:
                if e["type"] == "stop":
                    for k in ("exit", "address", "drive_min", "name", "score", "block"):
                        self.assertIsNotNone(e[k], k)

    def test_ticketmaster_failure_is_partial(self):
        plan = self.scan(get_text=bad_tm)
        self.assertEqual(plan["status"], "partial")
        self.assertTrue(plan["sources"]["ticketmaster"].startswith("error"))
        self.assertEqual(len(plan["days"]), 5)

    def test_claude_failure_marks_partial(self):
        def broken(prompt, args, timeout):
            raise ClaudeError("Failed to authenticate")
        plan = self.scan(call_claude=broken)
        self.assertEqual(plan["status"], "partial")
        self.assertTrue(plan["sources"]["estimate"].startswith("error"))
        self.assertIn("office:kpmg-barangaroo:normal:2026-11-23", [s["id"] for s in stops(plan, "2026-11-23")])
        self.assertNotIn("tm:Z1", [s["id"] for d in plan["days"] for s in stops(plan, d["date"])])

    def test_estimate_exception_marks_partial_and_hides_key(self):
        boom = Mock(side_effect=ValueError("boom https://app.ticketmaster.com/x?apikey=SECRETKEY123"))
        with patch("taxi.estimate.estimate_events", boom):
            plan = self.scan()
        self.assertEqual(plan["status"], "partial")
        self.assertTrue(plan["sources"]["estimate"].startswith("error: boom"))
        self.assertNotIn("SECRETKEY123", json.dumps(plan))
        self.assertIn("office:kpmg-barangaroo:normal:2026-11-23", [s["id"] for s in stops(plan, "2026-11-23")])

    def test_gapfill_exception_marks_partial(self):
        with patch("taxi.gapfill.gapfill", Mock(side_effect=RuntimeError("gf broke"))):
            plan = self.scan()
        self.assertEqual(plan["status"], "partial")
        self.assertEqual(plan["sources"]["gapfill"], "error: gf broke")
        self.assertIn("tm:Z1", [s["id"] for s in stops(plan, "2026-11-25")])

    def test_weather_error_alone_stays_ok(self):
        def no_weather(url):
            if "open-meteo" in url:
                raise SourceError("api.open-meteo.com: HTTP 500")
            return get(url)
        plan = self.scan(get_text=no_weather)
        self.assertEqual(plan["status"], "ok")
        self.assertTrue(plan["sources"]["weather"].startswith("error"))

    def test_gapfill_error_status_is_partial_and_cleaned(self):
        with patch("taxi.gapfill.gapfill", Mock(return_value=([], [], "error: bad https://x.test/p?apikey=SECRETKEY123"))):
            plan = self.scan()
        self.assertEqual(plan["status"], "partial")
        self.assertNotIn("SECRETKEY123", json.dumps(plan))

    def test_cache_save_failure_does_not_stop_scan(self):
        with patch("taxi.cache.save_cache", Mock(side_effect=PermissionError("locked"))):
            plan = self.scan()
        self.assertEqual(plan["status"], "ok")
        self.assertTrue((self.root / "site" / "plan.json").exists())

    def test_no_claude_and_no_publish(self):
        call = Mock()
        plan = self.scan(call_claude=call, use_claude=False, do_publish=False)
        call.assert_not_called()
        self.pub.assert_not_called()
        self.assertEqual(plan["status"], "partial")
        self.assertEqual(plan["sources"]["estimate"], "skipped")

    def test_no_ticketmaster_key(self):
        wjson(self.root / "secrets.json", {})
        with patch.dict(os.environ, {"TICKETMASTER_KEY": ""}):
            plan = self.scan()
        self.assertEqual(plan["sources"]["ticketmaster"], "error: no Ticketmaster key")

    def test_fatal_keeps_old_plan(self):
        (self.root / "site" / "plan.json").write_text('{"old": true}', encoding="utf-8")
        with patch("taxi.net.get_text", get), patch("taxi.plan.plan_day", Mock(side_effect=RuntimeError("boom"))):
            self.assertEqual(main(["--root", str(self.root), "--no-claude", "--no-publish"]), 1)
        self.assertEqual((self.root / "site" / "plan.json").read_text("utf-8"), '{"old": true}')
        log = (self.root / "logs" / "scan.log").read_text("utf-8")
        self.assertIn("scan failed", log)
        self.assertIn("RuntimeError: boom", log)

    def test_main_ok_logs_each_source(self):
        with patch("taxi.net.get_text", get):
            self.assertEqual(main(["--root", str(self.root), "--no-claude", "--no-publish"]), 0)
        log = (self.root / "logs" / "scan.log").read_text("utf-8")
        for s in ("ticketmaster: ok", "offices: ok", "weather: ok"):
            self.assertIn(s, log)
        self.assertNotIn("SECRETKEY123", log)

    def test_source_error_hides_local_paths(self):
        def no_weather(url):
            if "open-meteo" in url:
                raise SourceError(r"cannot open C:\Users\x\foo.txt and /home/bob/.claude/x")
            return get(url)
        text = json.dumps(self.scan(get_text=no_weather))
        self.assertNotIn("x\\\\foo", text)
        self.assertNotIn("bob", text)

    def test_sunday_shift_events_not_estimated(self):
        from scan import drop_sunday_shift
        from tests.helpers import cand
        sat, sun, mon_small = (datetime(2026, 11, 28, 20, 0, tzinfo=SYD), datetime(2026, 11, 29, 20, 0, tzinfo=SYD),
                               datetime(2026, 11, 30, 1, 0, tzinfo=SYD))
        kept = drop_sunday_shift([cand(id=i, start=s) for i, s in (("a", sat), ("b", sun), ("c", mon_small))])
        self.assertEqual([c.id for c in kept], ["a"])

    def test_plan_keys_match_sample_fixture(self):
        """The phone page renders sample_plan.json in the JS tests; its shape must equal what scan.run writes."""
        def shape(plan):
            out = {"top": set(plan)}
            for d in plan["days"]:
                for e in d["entries"]:
                    out.setdefault(e["type"], set()).update(e)
                    if e["type"] == "quiet":
                        for n in e["nearby"]:
                            out.setdefault("nearby", set()).update(n)
            return out
        plan = self.scan()
        sample = json.loads(fx("sample_plan.json"))
        got, want = shape(plan), shape(sample)
        for k in ("top", "stop", "quiet"):
            self.assertEqual(got[k], want[k], k)
        self.assertIn("nearby", got)
        self.assertEqual(got["nearby"], want["nearby"], "nearby")

    def test_freshness_workflow(self):
        y = (ROOT / ".github" / "workflows" / "freshness.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 1 * * *"', y)
        self.assertIn("generated_at", y)
        self.assertNotIn("secrets.", y)

    def test_plan_has_schema(self):
        self.assertEqual(self.scan()["schema"], 1)

    def test_secrets_bom_and_unparsable_warning(self):
        (self.root / "secrets.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"ticketmaster_key": "BOMKEY"}).encode())
        with patch.dict(os.environ, {"TICKETMASTER_KEY": ""}):
            self.assertEqual(load_secrets(self.root)["ticketmaster_key"], "BOMKEY")
            (self.root / "secrets.json").write_text("{not json", encoding="utf-8")
            with self.assertLogs("scan", "WARNING"):
                self.assertEqual(load_secrets(self.root)["ticketmaster_key"], "")

    def test_cache_prune_failure_does_not_stop_scan(self):
        with patch("taxi.cache.prune", Mock(side_effect=KeyError("event"))):
            self.assertEqual(self.scan()["status"], "ok")

    def test_small_hours_scan_uses_previous_shift_day(self):
        plan = run(datetime(2026, 11, 24, 1, 30, tzinfo=SYD), self.root, get_text=get, call_claude=fake_claude,
                   publish_fn=self.pub)
        self.assertEqual(plan["days"][0]["date"], "2026-11-23")

    def test_push_failure_exits_non_zero(self):
        with patch("taxi.net.get_text", get), patch("taxi.publish.publish", Mock(return_value="error: push failed")):
            self.assertEqual(main(["--root", str(self.root), "--no-claude"]), 1)
        self.assertTrue((self.root / "site" / "plan.json").exists())

    def test_load_secrets_env_override(self):
        with patch.dict(os.environ, {"TICKETMASTER_KEY": "ENVKEY"}):
            s = load_secrets(self.root)
        self.assertEqual(s["ticketmaster_key"], "ENVKEY")
        with patch.dict(os.environ, {"TICKETMASTER_KEY": "", "CLAUDE_CODE_OAUTH_TOKEN": ""}):
            s = load_secrets(self.root)
        self.assertEqual((s["ticketmaster_key"], s["claude_oauth_token"]), ("SECRETKEY123", ""))
        with patch.dict(os.environ, {"TICKETMASTER_KEY": ""}):
            self.assertEqual(load_secrets(self.root / "nowhere")["ticketmaster_key"], "")


if __name__ == "__main__":
    unittest.main()
