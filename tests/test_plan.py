import unittest
from datetime import datetime

from taxi.model import SYD
from taxi.plan import nearby, plan_day
from tests.helpers import TABLE, W, assert_covers, cand


def c(id, area, hh, mm, score, day=23, name=None):
    return cand(id=id, name=name or id, area=area, score=score,
                exit=datetime(2026, 11, day, hh, mm, tzinfo=SYD))


def place(name, kind, area, frm, to):
    return {"id": name, "kind": kind, "name": name, "area": area, "busy": [[frm, to]]}


class TestPlan(unittest.TestCase):
    def covers(self, e):
        assert_covers(self, e)

    def test_single_stop(self):
        e = plan_day([c("K", "Barangaroo", 17, 30, 60, name="KPMG")], [], TABLE, W)
        self.assertEqual(e[0], {"type": "quiet", "block": [0, 240], "until": "16:00", "next": "KPMG", "nearby": []})
        self.assertEqual((e[1]["type"], e[1]["block"], e[1]["drive_min"], e[1]["drive_from"]), ("stop", [240, 360], 6, None))
        self.assertEqual(e[2], {"type": "quiet", "block": [360, 900], "until": None, "next": None, "nearby": []})
        self.covers(e)

    def test_stop_fields(self):
        k = c("K", "Barangaroo", 17, 30, 60, name="KPMG")
        k.start, k.size, k.age_lo, k.age_hi = datetime(2026, 11, 23, 15, 0, tzinfo=SYD), 3000, 30, 55
        s = plan_day([k], [], TABLE, W)[1]
        self.assertEqual((s["id"], s["name"], s["score"], s["exit"], s["start"], s["size"], s["url"]),
                         ("K", "KPMG", 60, "17:30", "15:00", 3000, "https://example.com"))

    def test_optimiser_beats_greedy(self):
        e = plan_day([c("A", "Olympic Park", 19, 10, 50), c("B", "CBD", 18, 30, 45), c("C", "CBD", 20, 0, 60)], [], TABLE, W)
        self.assertEqual([x["id"] for x in e if x["type"] == "stop"], ["B", "C"])
        self.covers(e)

    def test_far_rule(self):
        e = plan_day([c("D", "Rooty Hill", 1, 0, 54, day=24)], [], TABLE, W)
        self.assertEqual([x["type"] for x in e], ["quiet"])
        self.covers(e)
        e = plan_day([c("E", "Rooty Hill", 1, 0, 55, day=24)], [], TABLE, W)
        self.assertIn("E", [x.get("id") for x in e])
        self.covers(e)

    def test_threshold(self):
        e = plan_day([c("L", "CBD", 18, 0, 39)], [], TABLE, W)
        self.assertEqual(e[0]["block"], [0, 900])
        self.covers(e)

    def test_quiet_merge_and_drive(self):
        e = plan_day([c("S1", "CBD", 13, 0, 50), c("S2", "Circular Quay/The Rocks", 22, 15, 66)], [], TABLE, W)
        self.assertEqual([x["block"] for x in e], [[0, 120], [120, 600], [600, 720], [720, 900]])
        self.assertEqual((e[1]["until"], e[1]["next"]), ("22:00", "S2"))
        self.assertEqual((e[2]["drive_min"], e[2]["drive_from"]), (5, "S1"))
        self.covers(e)

    def test_quiet_fallback_anchor_and_nearby(self):
        steady = [place("H1", "hotel", "Pyrmont", "12:00", "23:00")]
        e = plan_day([c("P", "Pyrmont", 22, 15, 66)], steady, TABLE, W)
        self.assertEqual(e[0]["nearby"], ["H1"])   # anchor = next stop's area
        self.assertEqual(e[-1]["nearby"], [])      # after the stop: H1 not busy after 23:00 (700 < 720)
        self.covers(e)

    def test_nearby(self):
        steady = [place("H1", "hotel", "Pyrmont", "12:00", "23:00"), place("The Star", "casino", "Pyrmont", "12:00", "03:00"),
                  place("RH", "club", "Rooty Hill", "17:00", "02:00"), place("H2", "hotel", "Barangaroo", "12:00", "23:00"),
                  place("P", "hospital", "CBD", "12:00", "20:00")]
        self.assertEqual(nearby(steady, "Pyrmont", (120, 600), TABLE, 3), ["The Star", "H1", "H2"])
        self.assertEqual(nearby(steady, "Pyrmont", (720, 900), TABLE, 3), ["The Star", "RH"])

    def test_no_candidates(self):
        e = plan_day([], [], TABLE, W)
        self.assertEqual(len(e), 1)
        self.covers(e)


if __name__ == "__main__":
    unittest.main()
