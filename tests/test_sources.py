import json
import unittest
from datetime import date, datetime

from taxi.model import SYD, working_days
from taxi.net import SourceError
from taxi.sources.cruise import CRUISE_URL, boarding_candidates, fetch_departures, parse_schedule
from taxi.sources.offices import office_candidates
from taxi.sources.weather import fetch_rain, rain_hours
from tests.helpers import OFFICE, ROOT, S, W

DAYS = working_days(date(2026, 11, 23))


def read(name):
    return (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8")


def row(ship, when, berth="Overseas Passenger Terminal"):
    return ('<table class="cols-6"><tr><td class="views-field views-field-vessel-name">%s</td>'
            '<td class="views-field views-field-departure-time">%s</td>'
            '<td class="views-field views-field-berth">%s</td></tr></table>' % (ship, when, berth))


class TestSources(unittest.TestCase):
    def test_parse_and_board(self):
        deps = parse_schedule(read("cruise.html"), date(2026, 11, 23)); self.assertEqual(len(deps), 4)
        cs = boarding_candidates(deps, DAYS, W, S)
        self.assertEqual(sorted(c.id for c in cs), ["cruise:anthem-of-the-seas:2026-11-23", "cruise:viking-venus:2026-11-23"])
        v = next(c for c in cs if "viking" in c.id)
        self.assertEqual((v.exit, v.size, v.area), (datetime(2026, 11, 23, 13, 0, tzinfo=SYD), 3000, "Pyrmont"))
        self.assertEqual(v.desc, "Ship departs at 6pm from the White Bay Cruise Terminal. Pick up passengers at city hotels heading to the terminal.")
        self.assertEqual(v.name, "Cruise ship boarding · Viking Venus")

    def test_white_bay_4_is_white_bay_terminal(self):
        deps = parse_schedule(row("Bay Four", "Mon 23 Nov<br>18:00", "White Bay 4"), date(2026, 11, 23))
        c, = boarding_candidates(deps, DAYS, W, S)
        self.assertEqual((c.area, c.address), ("Pyrmont", "5 Robert St, Rozelle NSW 2039"))
        self.assertIn("from the White Bay 4.", c.desc)

    def test_unknown_berth_skipped(self):
        deps = parse_schedule(row("Odd Ship", "Mon 23 Nov<br>18:00", "Mystery Wharf"), date(2026, 11, 23))
        with self.assertLogs("taxi.sources.cruise", "WARNING"):
            self.assertEqual(boarding_candidates(deps, DAYS, W, S), [])

    def test_bad_row_skipped_not_fatal(self):
        html = read("cruise.html").replace("Mon 23 Nov<br>18:00", "Mon 23 Nov").replace("Tue 24 Nov<br>12:30", "Blah")
        with self.assertLogs("taxi.sources.cruise", "WARNING") as lg:
            deps = parse_schedule(html, date(2026, 11, 23))
        self.assertEqual([d["ship"] for d in deps], ["Anthem of the Seas", "Sea Ship"]); self.assertEqual(len(lg.records), 2)
        with self.assertLogs("taxi.sources.cruise", "WARNING"), self.assertRaises(SourceError):
            parse_schedule(row("X", "Mon 23 Nov"), date(2026, 11, 23))

    def test_page1_bad_or_empty_keeps_page0(self):
        html = read("cruise.html")
        for page1, warns in (("<html></html>", False), (row("X", "Mon 23 Nov"), True)):
            get = lambda u, p=page1: html if u == CRUISE_URL else p
            if warns:
                with self.assertLogs("taxi.sources.cruise", "WARNING"):
                    self.assertEqual(len(fetch_departures(get, date(2026, 11, 23))), 4)
            else:
                with self.assertNoLogs("taxi.sources.cruise", "WARNING"):
                    self.assertEqual(len(fetch_departures(get, date(2026, 11, 23))), 4)

    def test_year_rollover(self):
        d = parse_schedule(row("New Year", "Fri 1 Jan<br>17:00"), date(2026, 12, 30))[0]["departure"]
        self.assertEqual(d.year, 2027)

    def test_no_rows(self):
        with self.assertRaises(SourceError):
            parse_schedule("<html></html>", date(2026, 11, 23))

    def test_fetch_departures_dedupes_and_ignores_failing_page1(self):
        html = read("cruise.html")

        def get(url):
            if url == CRUISE_URL:
                return html
            raise SourceError("boom")
        with self.assertLogs("taxi.sources.cruise", "WARNING"):
            self.assertEqual(len(fetch_departures(get, date(2026, 11, 23))), 4)
        urls = []
        self.assertEqual(len(fetch_departures(lambda u: urls.append(u) or html, date(2026, 11, 23))), 4)
        self.assertEqual(urls, [CRUISE_URL, CRUISE_URL + "?page=1"])

    def test_fetch_departures_page0_failure_raises(self):
        def get(url):
            raise SourceError("down")
        with self.assertRaises(SourceError):
            fetch_departures(get, date(2026, 11, 23))

    def test_rain_hours(self):
        data = {"hourly": {"time": ["2026-11-23T18:00", "2026-11-23T19:00", "2026-11-23T20:00"],
                           "precipitation_probability": [70, 10, 40], "precipitation": [0.1, 0.6, 0.2]}}
        self.assertEqual(rain_hours(data, W), {"2026-11-23T18", "2026-11-23T19"})
        self.assertEqual(fetch_rain(lambda u: json.dumps(data), W), {"2026-11-23T18", "2026-11-23T19"})

    def test_offices(self):
        cs = office_candidates([dict(OFFICE, cabcharge=0.6)], [date(2026, 11, 23), date(2026, 11, 28)], W, S)
        self.assertEqual([c.id for c in cs], ["office:kpmg-barangaroo:normal:2026-11-23", "office:kpmg-barangaroo:late:2026-11-23"])
        n, l = cs
        self.assertEqual((n.pays, n.size, n.exit), (0.6, 3000, datetime(2026, 11, 23, 17, 30, tzinfo=SYD)))
        self.assertEqual((l.pays, l.size, l.name, l.exit), (1.0, 600, "KPMG Barangaroo · late finish", datetime(2026, 11, 23, 20, 30, tzinfo=SYD)))


if __name__ == "__main__":
    unittest.main()
