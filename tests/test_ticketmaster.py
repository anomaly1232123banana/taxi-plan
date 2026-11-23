import http.client
import json
import unittest
from datetime import date, datetime
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from taxi.model import SYD
from taxi.net import SourceError, get_text, url_alive
from taxi.sources.ticketmaster import fetch_events, to_candidates
from tests.helpers import ROOT, TABLE, W


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))


class FakeGet:
    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def __call__(self, url):
        self.urls.append(url)
        return json.dumps(self.pages[min(len(self.urls) - 1, len(self.pages) - 1)])


class TestTicketmaster(unittest.TestCase):
    def test_to_candidates_filters_junk(self):
        cs = to_candidates(load("tm_page.json")["_embedded"]["events"], TABLE, W)
        self.assertEqual([c.id for c in cs], ["tm:Z1"]); c = cs[0]
        self.assertEqual((c.area, c.start, c.info), ("Olympic Park", datetime(2026, 11, 25, 19, 30, tzinfo=SYD), "Music / Rock · $89–189"))
        self.assertEqual((c.address, c.source_url), ("Olympic Blvd, Sydney Olympic Park", "https://www.ticketmaster.com.au/event/Z1"))

    def test_fetch_events_url_and_paging(self):
        ev = {"id": "A"}
        get = FakeGet([{"_embedded": {"events": [ev]}, "page": {"totalPages": 2}},
                       {"_embedded": {"events": [ev]}, "page": {"totalPages": 2}}])
        with patch("taxi.sources.ticketmaster.time.sleep"):
            evs = fetch_events("KEY", [date(2026, 11, d) for d in (23, 24, 25, 26, 27)], get, W)
        u = get.urls[0]
        for s in ("apikey=KEY", "latlong=-33.8688,151.2093", "radius=50", "unit=km", "size=200",
                  "startDateTime=2026-11-22T13:00:00Z", "endDateTime=2026-11-27T16:00:00Z", "page=0"):
            self.assertIn(s, u)
        self.assertIn("page=1", get.urls[1]); self.assertEqual(len(get.urls), 2)
        self.assertEqual(len(evs), 2)

    def test_later_page_failure_keeps_earlier_pages(self):
        pages = [json.dumps({"_embedded": {"events": [{"id": "A"}]}, "page": {"totalPages": 3}})]

        def get(url):
            if "page=0" in url:
                return pages[0]
            raise SourceError("app.ticketmaster.com: HTTP 429")
        with patch("taxi.sources.ticketmaster.time.sleep"), self.assertLogs("taxi.sources.ticketmaster", "WARNING"):
            self.assertEqual(fetch_events("KEY", [date(2026, 11, 23)], get, W), [{"id": "A"}])
        with self.assertRaises(SourceError):
            fetch_events("KEY", [date(2026, 11, 23)], lambda u: (_ for _ in ()).throw(SourceError("x")), W)

    def test_no_events_key(self):
        get = FakeGet([{"page": {"totalPages": 1}}])
        self.assertEqual(fetch_events("KEY", [date(2026, 11, 23)], get, W), [])
        self.assertEqual(len(get.urls), 1)

    def test_error_message_hides_query(self):
        err = HTTPError("https://app.ticketmaster.com/x?apikey=SECRET123", 401, "Unauthorized", {}, None)
        with patch("taxi.net.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(SourceError) as e:
                get_text("https://app.ticketmaster.com/x?apikey=SECRET123")
        self.assertNotIn("SECRET123", str(e.exception)); self.assertIn("401", str(e.exception))

    def test_url_alive(self):
        url = "https://example.com/x"
        for outcome, want in ((None, True), (HTTPError(url, 403, "Forbidden", {}, None), True),
                              (HTTPError(url, 404, "Not Found", {}, None), False),
                              (HTTPError(url, 410, "Gone", {}, None), False), (URLError("down"), False),
                              (TimeoutError(), False), (ConnectionResetError(), False), (http.client.RemoteDisconnected("x"), False)):
            with self.subTest(outcome=outcome), patch("taxi.net.urllib.request.urlopen", side_effect=outcome) as m:
                if outcome is None:
                    m.side_effect = None
                self.assertEqual(url_alive(url), want)
        with self.subTest(outcome="scheme-less"):
            self.assertFalse(url_alive("www.example.com/x"))

    def test_malformed_and_dead_events_skipped(self):
        good = load("tm_page.json")["_embedded"]["events"][0]
        import copy
        def broken(fn, id_):
            e = copy.deepcopy(good); e["id"] = id_; e["dates"]["start"]["localTime"] = "20:%02d:00" % len(id_)
            fn(e); return e
        evs = [broken(lambda e: e["_embedded"]["venues"][0].pop("address"), "B1"),
               broken(lambda e: e["_embedded"].pop("venues"), "B22"),
               broken(lambda e: e.pop("url"), "B333"),
               broken(lambda e: e.__setitem__("priceRanges", [{"max": 5}]), "B4444"),
               broken(lambda e: e["dates"].__setitem__("status", {"code": "cancelled"}), "C1"),
               broken(lambda e: e["dates"].__setitem__("status", {"code": "canceled"}), "C22"),
               broken(lambda e: e["dates"].__setitem__("status", {"code": "postponed"}), "C333"),
               broken(lambda e: e["dates"]["start"].__setitem__("timeTBA", True), "T1"),
               broken(lambda e: e["dates"]["start"].__setitem__("noSpecificTime", True), "T22"),
               good]
        with self.assertLogs("taxi.sources.ticketmaster", "WARNING") as lg:
            cs = to_candidates(evs, TABLE, W)
        self.assertEqual([c.id for c in cs], ["tm:Z1"])
        self.assertEqual(len(lg.records), 4)


if __name__ == "__main__":
    unittest.main()
