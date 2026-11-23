import unittest
from datetime import datetime

from taxi.model import SYD
from taxi.score import age_factor, late_factor, score, score_candidate, size_factor
from tests.helpers import W, cand


class TestScore(unittest.TestCase):
    def test_regression_examples(self):  # spec 8.2
        self.assertAlmostEqual(score(58, 0.15, 2000, 1.0, 615, W), 66, delta=1)   # Opera House 22:15
        self.assertAlmostEqual(score(40, 1.0, 3000, 0.7, 360, W), 60, delta=1)    # KPMG 18:00
        self.assertAlmostEqual(score(22, 0.0, 20000, 0.15, 780, W), 30, delta=1)  # rave 01:00

    def test_factors(self):
        c = W["age_curve"]
        self.assertEqual([age_factor(a, c) for a in (18, 22, 50, 60)], [0.1, 0.1, 1.0, 1.0])
        self.assertAlmostEqual(age_factor(26, c), 0.175)
        self.assertAlmostEqual(age_factor(42.5, c), 0.7)
        self.assertEqual([size_factor(n, W) for n in (100, 200, 80000, 10**6)], [0.0, 0.0, 1.0, 1.0])
        self.assertAlmostEqual(size_factor(2000, W), 0.3843, places=3)
        self.assertEqual([late_factor(m, W) for m in (0, 539, 540, 599, 600, 780)], [0, 0, 0.5, 0.5, 1, 1])

    def test_boosts_and_cap(self):
        self.assertEqual(score(58, 0.15, 2000, 1.0, 615, W, rain=True), 76)
        self.assertEqual(score(58, 0.15, 2000, 1.0, 615, W, rain=True, disrupted=True), 92)
        self.assertEqual(score(60, 1, 80000, 1, 600, W, rain=True, disrupted=True), 100)

    def test_score_candidate(self):
        c = cand(area="CBD", exit=datetime(2026, 11, 23, 22, 15, tzinfo=SYD), median_age=58, pays=0.15, size=2000, spend=1.0)
        self.assertEqual(score_candidate(c, W, {"2026-11-23T22"}, []), 76)
        strike = {"area": "ALL", "date": "2026-11-23", "from": "20:00", "to": "23:59", "what": "strike", "source_url": "https://x"}
        self.assertEqual(score_candidate(c, W, {"2026-11-23T22"}, [strike]), 92)
        self.assertEqual(score_candidate(c, W, set(), [dict(strike, area="Parramatta")]), 66)
        self.assertEqual(c.score, 66)


if __name__ == "__main__":
    unittest.main()
