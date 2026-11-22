import unittest
from datetime import date, datetime, timezone

from taxi.model import (SYD, at_shift, block_index, exit_after, fmt12, hm_of, shift_minute,
                        shift_slot, slug, working_days)


def dt(*a):
    return datetime(*a, tzinfo=SYD)


class TestModel(unittest.TestCase):
    def test_shift_slot(self):
        self.assertEqual(shift_slot(dt(2026, 11, 23, 22, 15)), (date(2026, 11, 23), 615))
        self.assertEqual(shift_slot(dt(2026, 11, 24, 1, 0)), (date(2026, 11, 23), 780))
        self.assertEqual(shift_slot(dt(2026, 11, 24, 3, 0)), (date(2026, 11, 23), 900))
        self.assertIsNone(shift_slot(dt(2026, 11, 24, 3, 1)))
        self.assertIsNone(shift_slot(dt(2026, 11, 23, 11, 59)))
        self.assertEqual(shift_slot(dt(2026, 11, 23, 12, 0)), (date(2026, 11, 23), 0))
        self.assertEqual(shift_slot(datetime(2026, 11, 23, 11, 15, tzinfo=timezone.utc)), (date(2026, 11, 23), 615))

    def test_sunday_rule(self):
        self.assertEqual(shift_slot(dt(2026, 11, 29, 1, 0)), (date(2026, 11, 28), 780))  # Sun 1am = Saturday shift
        self.assertIsNone(shift_slot(dt(2026, 11, 29, 20, 0)))                           # Sunday shift
        self.assertIsNone(shift_slot(dt(2026, 11, 30, 1, 0)))                            # Mon 1am = Sunday shift

    def test_dst_days(self):
        self.assertEqual(shift_slot(dt(2026, 10, 4, 1, 30)), (date(2026, 10, 3), 810))
        self.assertEqual(shift_slot(dt(2026, 4, 5, 1, 30)), (date(2026, 4, 4), 810))

    def test_block_index(self):
        self.assertEqual([block_index(m) for m in (0, 119, 120, 615, 839, 840, 900)], [0, 0, 1, 5, 6, 7, 7])

    def test_working_days(self):
        self.assertEqual(working_days(date(2026, 11, 23)), [date(2026, 11, d) for d in (23, 24, 25, 26, 27)])
        self.assertEqual(working_days(date(2026, 11, 26)), [date(2026, 11, 26), date(2026, 11, 27), date(2026, 11, 28), date(2026, 11, 30), date(2026, 12, 1)])
        self.assertEqual(working_days(date(2026, 11, 29)), [date(2026, 11, 30)] + [date(2026, 12, d) for d in (1, 2, 3, 4)])

    def test_time_helpers(self):
        self.assertEqual(at_shift(date(2026, 11, 23), "17:30"), dt(2026, 11, 23, 17, 30))
        self.assertEqual(at_shift(date(2026, 11, 23), "01:00"), dt(2026, 11, 24, 1, 0))
        self.assertEqual(exit_after(dt(2026, 11, 23, 19, 30), "22:15"), dt(2026, 11, 23, 22, 15))
        self.assertEqual(exit_after(dt(2026, 11, 23, 19, 30), "01:00"), dt(2026, 11, 24, 1, 0))
        self.assertEqual(exit_after(dt(2026, 11, 23, 10, 0), "11:30"), dt(2026, 11, 23, 11, 30))
        self.assertEqual([shift_minute(h) for h in ("12:00", "02:00", "03:00", "23:00")], [0, 840, 900, 660])
        self.assertEqual((hm_of(615), hm_of(780)), ("22:15", "01:00"))
        S = {"am": "am", "pm": "pm"}
        self.assertEqual([fmt12(h, S) for h in ("18:00", "16:45", "00:00", "12:30")], ["6pm", "4:45pm", "12am", "12:30pm"])
        self.assertEqual(slug("Anthem of the Seas"), "anthem-of-the-seas")
        self.assertEqual(slug("ICC Sydney – Day 1!"), "icc-sydney-day-1")


if __name__ == "__main__":
    unittest.main()
