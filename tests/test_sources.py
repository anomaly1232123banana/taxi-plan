import json
import unittest
from datetime import date, datetime

from taxi.model import SYD, working_days
from taxi.net import SourceError
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
        self.assertEqual((l.pays, l.size, l.name, l.exit), (0.6, 600, "KPMG Barangaroo · late finish", datetime(2026, 11, 23, 20, 30, tzinfo=SYD)))

    def test_no_offices_on_holidays_or_shutdown(self):
        from taxi.data import load_holidays
        hol = load_holidays(ROOT / "data" / "holidays.json")
        days = [date(2026, 12, 25), date(2026, 12, 28), date(2026, 12, 29), date(2027, 1, 4)]
        cs = office_candidates([OFFICE], days, W, S, hol)
        self.assertEqual({c.exit.date().isoformat() for c in cs}, {"2027-01-04"})
        self.assertEqual(len(office_candidates([OFFICE], days, W, S)), 8)


if __name__ == "__main__":
    unittest.main()
