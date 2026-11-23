import unittest

from taxi.drive import base_minutes, drive_minutes, haversine_km, nearest_area
from tests.helpers import TABLE


class TestDrive(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
