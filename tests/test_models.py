import json
import unittest

from clicksmith.core.models import (
    Button,
    ClickSpec,
    Interval,
    Profile,
    RunMode,
    Schedule,
    Step,
    StepType,
    parse_time_str,
)


class ModelTests(unittest.TestCase):
    def test_roundtrip_is_lossless_and_json_safe(self):
        profile = Profile(name="Mine", mode=RunMode.MACRO)
        profile.steps.append(Step(type=StepType.TEXT, text="سلام 👋\nline two"))
        profile.steps.append(Step(type=StepType.CLICK, x=10, y=20, button=Button.RIGHT))
        data = profile.to_dict()
        text = json.dumps(data, ensure_ascii=False)
        self.assertEqual(Profile.from_dict(json.loads(text)), profile.normalize())
        self.assertEqual(data["mode"], "macro")  # enums are stored as plain strings

    def test_loading_is_forgiving(self):
        profile = Profile.from_dict(
            {
                "name": 5,
                "mode": "nonsense",
                "unknown_key": True,
                "interval": {"millis": "250", "hours": "x"},
                "steps": [{"type": "click", "x": 3}, "junk", {"type": "bogus", "y": 9}],
            }
        )
        self.assertEqual(profile.name, "Default")
        self.assertEqual(profile.mode, RunMode.CLICKER)
        self.assertEqual(profile.interval.millis, 250)
        self.assertEqual(profile.interval.hours, 0)
        self.assertEqual(len(profile.steps), 2)  # "junk" dropped, bad fields fall back
        self.assertEqual(profile.steps[0].x, 3)
        self.assertEqual(profile.steps[1].type, StepType.CLICK)
        self.assertEqual(profile.steps[1].y, 9)

    def test_interval_is_normalised_to_canonical_form(self):
        interval = Interval(hours=0, minutes=90, seconds=75, millis=1500)
        interval.normalize()
        self.assertEqual(
            (interval.hours, interval.minutes, interval.seconds, interval.millis), (1, 31, 16, 500)
        )
        self.assertAlmostEqual(interval.total_seconds, 1 * 3600 + 31 * 60 + 16.5)

    def test_values_are_clamped(self):
        profile = Profile()
        profile.click = ClickSpec(clicks=9, hold_ms=-5)
        profile.interval.jitter_pct = 500
        profile.safety.start_delay_s = -3
        profile.target.jitter_px = 99999
        profile.normalize()
        self.assertEqual(profile.click.clicks, 3)
        self.assertEqual(profile.click.hold_ms, 0)
        self.assertEqual(profile.interval.jitter_pct, 100)
        self.assertEqual(profile.safety.start_delay_s, 0)
        self.assertEqual(profile.target.jitter_px, 500)

    def test_schedule_normalisation(self):
        schedule = Schedule(time="25:99", days=[9, -1, 2, 2])
        schedule.normalize()
        self.assertEqual(schedule.time, "00:00:00")
        self.assertEqual(schedule.days, [2])
        empty = Schedule(days=[])
        empty.normalize()
        self.assertEqual(empty.days, list(range(7)))

    def test_parse_time(self):
        self.assertEqual(parse_time_str("09:30"), (9, 30, 0))
        self.assertEqual(parse_time_str("23:59:58"), (23, 59, 58))
        self.assertEqual(parse_time_str("nope"), (0, 0, 0))
        self.assertEqual(parse_time_str("24:00"), (0, 0, 0))

    def test_copy_is_independent(self):
        a = Profile()
        b = a.copy()
        b.steps.append(Step())
        self.assertEqual(a.steps, [])


if __name__ == "__main__":
    unittest.main()
