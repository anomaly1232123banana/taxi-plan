import copy
import json
import tempfile
import unittest
from pathlib import Path

from taxi.data import (DataError, load_areas, load_offices, load_steady, load_venues, load_weights,
                       parse_areas)
from tests.helpers import AREAS_JSON, OFFICE, ROOT, S, TABLE, W

AREAS = set(TABLE["areas"])
STEADY = {"id": "star", "kind": "casino", "name": "The Star", "address": "80 Pyrmont St", "area": "Pyrmont",
          "lat": -33.8691, "lon": 151.1951, "busy": [["12:00", "03:00"]], "wait": "Rank"}
VENUE = {"name": "Royal Randwick", "kind": "racecourse", "area": "Pyrmont", "address": "Alison Rd",
         "what_on_url": "https://example.com/races"}


class TestData(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def write(self, obj, name="f.json"):
        p = Path(self._tmp.name) / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def wrap(self, key, items, **extra):
        return {"estimate": True, "researched": "2026-11-23", key: items, **extra}

    def test_parse_areas(self):
        t = parse_areas(AREAS_JSON)
        self.assertEqual(t["minutes"][("Pyrmont", "CBD")], 7)
        self.assertEqual(t["minutes"][("CBD", "Pyrmont")], 7)
        self.assertEqual(t["peak"], (240, 420, 1.5))
        self.assertEqual(t["late"], (540, 0.8))
        self.assertEqual(t["areas"]["CBD"], (-33.8688, 151.2093))
        self.assertEqual(len(t["minutes"]), 30)

    def test_missing_pair(self):
        bad = copy.deepcopy(AREAS_JSON)
        bad["pairs"] = [p for p in bad["pairs"] if p[:2] != ["Barangaroo", "Pyrmont"]]
        with self.assertRaises(DataError) as e:
            parse_areas(bad)
        self.assertIn("Barangaroo", str(e.exception))
        self.assertIn("Pyrmont", str(e.exception))

    def test_areas_rules(self):
        for mutate in (lambda a: a["areas"].pop("CBD"),
                       lambda a: a["pairs"].append(["CBD", "Pyrmont", 9]),
                       lambda a: a["pairs"].__setitem__(0, ["CBD", "Barangaroo", 500])):
            bad = copy.deepcopy(AREAS_JSON)
            mutate(bad)
            with self.assertRaises(DataError):
                parse_areas(bad)

    def test_office_bad_area(self):
        p = self.write(self.wrap("offices", [dict(OFFICE, area="Bondi")]))
        with self.assertRaises(DataError) as e:
            load_offices(p, AREAS)
        self.assertIn("kpmg-barangaroo", str(e.exception))

    def test_office_ok(self):
        p = self.write(self.wrap("offices", [OFFICE]), "offices.json")
        self.assertEqual(load_offices(p, AREAS)[0]["staff"], 3000)

    def test_office_bad_values(self):
        for bad in (dict(OFFICE, staff=50), dict(OFFICE, normal_finish="15:00"), dict(OFFICE, late_finish="23:30"),
                    dict(OFFICE, desc="x" * 161), dict(OFFICE, source_url="ftp://x")):
            with self.assertRaises(DataError, msg=bad):
                load_offices(self.write(self.wrap("offices", [bad])), AREAS)

    def test_steady_bad_kind(self):
        with self.assertRaises(DataError):
            load_steady(self.write(self.wrap("places", [dict(STEADY, kind="pub")])), AREAS)

    def test_steady_ok_and_duplicate_id(self):
        self.assertEqual(load_steady(self.write(self.wrap("places", [STEADY])), AREAS)[0]["name"], "The Star")
        with self.assertRaises(DataError) as e:
            load_steady(self.write(self.wrap("places", [STEADY, STEADY])), AREAS)
        self.assertIn("star", str(e.exception))

    def test_venues_keyed_by_name_and_unknown_keys_ignored(self):
        p = self.write(self.wrap("venues", [VENUE], note="ignored"))
        self.assertEqual(load_venues(p, AREAS)[0]["name"], "Royal Randwick")
        with self.assertRaises(DataError):
            load_venues(self.write(self.wrap("venues", [VENUE, VENUE])), AREAS)
        with self.assertRaises(DataError):
            load_venues(self.write(self.wrap("venues", [dict(VENUE, kind="pub")])), AREAS)

    def test_not_marked_estimate(self):
        p = self.write(dict(self.wrap("offices", [OFFICE]), estimate=False))
        with self.assertRaises(DataError):
            load_offices(p, AREAS)

    def test_real_weights_and_strings(self):
        self.assertEqual(sum(W["points"].values()), 100)
        self.assertEqual(W["plan"]["big_threshold"], 40)
        for k in ("go_now", "free_until", "exit_office", "office_late", "_prompt_language", "am", "pm", "days", "months"):
            self.assertIn(k, S)

    def test_weights_rules(self):
        w = copy.deepcopy(W)
        w["points"]["age"] = 30
        with self.assertRaises(DataError):
            load_weights(self.write(w))
        del w["points"]
        with self.assertRaises(DataError):
            load_weights(self.write(w))

    def test_real_data_files_load(self):
        t = load_areas(ROOT / "data" / "areas.json")
        names = set(t["areas"])
        self.assertTrue(load_offices(ROOT / "data" / "offices.json", names))
        self.assertTrue(load_steady(ROOT / "data" / "steady.json", names))
        self.assertTrue(load_venues(ROOT / "data" / "gapfill_venues.json", names))


if __name__ == "__main__":
    unittest.main()
