import datetime as dt
import unittest

from clicksmith.core.models import Schedule
from clicksmith.core.scheduler import fmt_hms, next_run

THU = dt.datetime(2026, 9, 24, 8, 0, 0)  # 2026-09-24 is a Thursday


class SchedulerTests(unittest.TestCase):
    def test_disabled_schedule_never_fires(self):
        self.assertIsNone(next_run(Schedule(enabled=False), THU))

    def test_later_today(self):
        s = Schedule(enabled=True, time="09:00:00")
        self.assertEqual(next_run(s, THU), dt.datetime(2026, 9, 24, 9, 0, 0))

    def test_already_passed_rolls_to_tomorrow(self):
        s = Schedule(enabled=True, time="09:00:00")
        now = dt.datetime(2026, 9, 24, 10, 0, 0)
        self.assertEqual(next_run(s, now), dt.datetime(2026, 9, 25, 9, 0, 0))

    def test_exact_moment_counts_as_passed(self):
        s = Schedule(enabled=True, time="08:00:00")
        self.assertEqual(next_run(s, THU), dt.datetime(2026, 9, 25, 8, 0, 0))

    def test_weekdays_skip_the_weekend(self):
        s = Schedule(enabled=True, time="09:00:00", days=[0, 1, 2, 3, 4])
        friday_late = dt.datetime(2026, 9, 25, 10, 0, 0)
        self.assertEqual(next_run(s, friday_late), dt.datetime(2026, 9, 28, 9, 0, 0))

    def test_single_weekday(self):
        s = Schedule(enabled=True, time="21:30:15", days=[6])  # Sunday
        self.assertEqual(next_run(s, THU), dt.datetime(2026, 9, 27, 21, 30, 15))

    def test_fmt_hms(self):
        self.assertEqual(fmt_hms(3661), "01:01:01")
        self.assertEqual(fmt_hms(90061.9), "25:01:01")
        self.assertEqual(fmt_hms(-5), "00:00:00")


if __name__ == "__main__":
    unittest.main()
