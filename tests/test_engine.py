import random
import time
import unittest

from clicksmith.core.engine import Engine, RunState, StopReason
from clicksmith.core.input import FakeBackend
from clicksmith.core.models import (
    Interval,
    Profile,
    RunMode,
    Safety,
    Step,
    StepType,
    StopMode,
    StopRule,
    Target,
    TargetMode,
)


def make_profile(count=5, **overrides) -> Profile:
    profile = Profile()
    profile.interval = Interval(millis=1)
    profile.stop = StopRule(StopMode.COUNT, count=count)
    profile.safety = Safety(failsafe_corner=False, prevent_sleep=False, start_delay_s=0)
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


class ClickerTests(unittest.TestCase):
    def test_count_mode_performs_exact_number_of_clicks(self):
        backend = FakeBackend()
        engine = Engine(backend)
        self.assertTrue(engine.start(make_profile(5)))
        self.assertTrue(engine.wait(5))
        snap = engine.snapshot()
        self.assertEqual(backend.click_count, 5)
        self.assertEqual((snap.state, snap.reason, snap.count), (RunState.IDLE, StopReason.COMPLETED, 5))

    def test_zero_interval_is_clamped_not_a_busy_loop_bug(self):
        backend = FakeBackend()
        engine = Engine(backend)
        engine.start(make_profile(20, interval=Interval(millis=0)))
        self.assertTrue(engine.wait(5))
        self.assertEqual(backend.click_count, 20)

    def test_second_start_is_rejected_and_stop_works(self):
        backend = FakeBackend()
        engine = Engine(backend)
        profile = make_profile(interval=Interval(millis=5), stop=StopRule())
        self.assertTrue(engine.start(profile))
        self.assertFalse(engine.start(profile))
        time.sleep(0.15)
        self.assertGreater(engine.snapshot().cps, 5)
        engine.stop()
        self.assertTrue(engine.wait(3))
        self.assertEqual(engine.snapshot().reason, StopReason.USER)
        self.assertGreater(backend.click_count, 0)

    def test_state_callbacks_follow_waiting_running_idle(self):
        seen = []
        engine = Engine(FakeBackend(), on_state=lambda s, r: seen.append((s, r)))
        profile = make_profile(2)
        profile.safety.start_delay_s = 0
        engine.start(profile, start_delay=0.05)
        engine.wait(3)
        self.assertEqual(
            [s for s, _ in seen], [RunState.WAITING, RunState.RUNNING, RunState.IDLE]
        )
        self.assertEqual(seen[-1][1], StopReason.COMPLETED)

    def test_can_stop_during_start_delay(self):
        backend = FakeBackend()
        engine = Engine(backend)
        engine.start(make_profile(5), start_delay=30)
        time.sleep(0.05)
        self.assertEqual(engine.snapshot().state, RunState.WAITING)
        started = time.perf_counter()
        engine.stop()
        self.assertTrue(engine.wait(2))
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertEqual(backend.click_count, 0)

    def test_scheduled_start_waits_until_the_given_moment(self):
        backend = FakeBackend()
        stamps = []
        backend.on_event = lambda e: stamps.append(time.time()) if e[0] == "click" else None
        engine = Engine(backend)
        start_at = time.time() + 0.2
        engine.start(make_profile(1), start_at=start_at)
        time.sleep(0.05)
        snap = engine.snapshot()
        self.assertEqual(snap.state, RunState.WAITING)
        self.assertTrue(0 < snap.next_in <= 0.2)
        engine.wait(3)
        self.assertEqual(len(stamps), 1)
        self.assertGreaterEqual(stamps[0], start_at - 0.02)

    def test_duration_mode_stops_on_time(self):
        backend = FakeBackend()
        engine = Engine(backend)
        profile = make_profile(interval=Interval(millis=20), stop=StopRule(StopMode.DURATION, duration_s=1))
        started = time.perf_counter()
        engine.start(profile)
        self.assertTrue(engine.wait(5))
        elapsed = time.perf_counter() - started
        self.assertTrue(0.8 < elapsed < 1.6, elapsed)
        self.assertTrue(20 <= backend.click_count <= 60, backend.click_count)
        self.assertEqual(engine.snapshot().reason, StopReason.COMPLETED)

    def test_hold_uses_down_and_up(self):
        backend = FakeBackend()
        engine = Engine(backend)
        profile = make_profile(2)
        profile.click.hold_ms = 10
        engine.start(profile)
        engine.wait(3)
        kinds = [e[0] for e in backend.events]
        self.assertEqual(kinds.count("down"), 2)
        self.assertEqual(kinds.count("up"), 2)
        self.assertEqual(kinds.count("click"), 0)

    def test_double_click_is_one_action(self):
        backend = FakeBackend()
        engine = Engine(backend)
        profile = make_profile(3)
        profile.click.clicks = 2
        engine.start(profile)
        engine.wait(3)
        self.assertEqual([e for e in backend.events if e[0] == "click"], [("click", "left", 2)] * 3)
        self.assertEqual(engine.snapshot().count, 3)


class TargetTests(unittest.TestCase):
    def test_fixed_target_jitter_stays_within_bounds(self):
        backend = FakeBackend()
        engine = Engine(backend, rng=random.Random(7))
        profile = make_profile(30, target=Target(TargetMode.FIXED, x=400, y=300, jitter_px=10))
        engine.start(profile)
        engine.wait(5)
        points = [(e[1], e[2]) for e in backend.events if e[0] == "move"]
        self.assertEqual(len(points), 30)
        self.assertTrue(all(390 <= x <= 410 and 290 <= y <= 310 for x, y in points))
        self.assertGreater(len(set(points)), 1)

    def test_area_target_stays_inside_the_rectangle(self):
        backend = FakeBackend()
        engine = Engine(backend, rng=random.Random(3))
        profile = make_profile(40, target=Target(TargetMode.AREA, x=300, y=200, x2=100, y2=50))
        engine.start(profile)
        engine.wait(5)
        points = [(e[1], e[2]) for e in backend.events if e[0] == "move"]
        self.assertTrue(all(100 <= x <= 300 and 50 <= y <= 200 for x, y in points))

    def test_cursor_mode_never_moves_the_mouse(self):
        backend = FakeBackend()
        engine = Engine(backend)
        engine.start(make_profile(5))
        engine.wait(3)
        self.assertFalse([e for e in backend.events if e[0] == "move"])


class SafetyTests(unittest.TestCase):
    def test_failsafe_corner_stops_before_any_click(self):
        backend = FakeBackend()
        backend.pos = (0, 0)
        engine = Engine(backend)
        profile = make_profile(5)
        profile.safety.failsafe_corner = True
        engine.start(profile)
        engine.wait(3)
        self.assertEqual(engine.snapshot().reason, StopReason.FAILSAFE)
        self.assertEqual(backend.click_count, 0)

    def test_failsafe_interrupts_a_long_wait(self):
        backend = FakeBackend()
        engine = Engine(backend)
        profile = make_profile(interval=Interval(seconds=30), stop=StopRule())
        profile.safety.failsafe_corner = True
        engine.start(profile)
        time.sleep(0.1)
        backend.pos = (0, 0)  # the user slams the cursor into the corner
        self.assertTrue(engine.wait(3))
        self.assertEqual(engine.snapshot().reason, StopReason.FAILSAFE)

    def test_moving_the_mouse_stops_a_fixed_target_run(self):
        backend = FakeBackend()
        clicks = []

        def hook(event):
            if event[0] == "click":
                clicks.append(event)
                if len(clicks) == 3:
                    backend.pos = (900, 900)  # the user grabs the mouse

        backend.on_event = hook
        engine = Engine(backend)
        profile = make_profile(50, target=Target(TargetMode.FIXED, x=400, y=300))
        profile.safety.stop_on_mouse_move = True
        engine.start(profile)
        engine.wait(3)
        self.assertEqual(engine.snapshot().reason, StopReason.MOUSE_MOVED)
        self.assertEqual(backend.click_count, 3)

    def test_mouse_move_option_is_ignored_when_following_the_cursor(self):
        backend = FakeBackend()
        backend.on_event = lambda e: setattr(backend, "pos", (backend.pos[0] + 50, 700))
        engine = Engine(backend)
        profile = make_profile(5)
        profile.safety.stop_on_mouse_move = True
        engine.start(profile)
        engine.wait(3)
        self.assertEqual(engine.snapshot().reason, StopReason.COMPLETED)
        self.assertEqual(backend.click_count, 5)

    def test_backend_errors_are_reported_not_raised(self):
        class Broken(FakeBackend):
            def click(self, button, count=1):
                raise RuntimeError("boom")

        engine = Engine(Broken())
        with self.assertLogs("clicksmith.engine", level="ERROR"):
            engine.start(make_profile(3))
            self.assertTrue(engine.wait(3))
        self.assertEqual(engine.snapshot().reason, StopReason.ERROR)


class MacroTests(unittest.TestCase):
    def macro(self, steps, count=1) -> Profile:
        profile = make_profile(count, mode=RunMode.MACRO, interval=Interval(millis=1))
        profile.steps = steps
        return profile

    def test_steps_run_in_order_and_repeat(self):
        backend = FakeBackend()
        steps = [
            Step(type=StepType.CLICK, x=100, y=200, delay_after_ms=1),
            Step(type=StepType.TEXT, text="hi\nthere", delay_after_ms=1),
            Step(type=StepType.KEY, keys="Ctrl+V", delay_after_ms=1),
            Step(type=StepType.SCROLL, x=10, y=10, dy=-3, delay_after_ms=1),
            Step(type=StepType.WAIT, delay_after_ms=2),
        ]
        engine = Engine(backend)
        engine.start(self.macro(steps, count=2))
        self.assertTrue(engine.wait(5))
        one_run = [
            ("move", 100, 200),
            ("click", "left", 1),
            ("text", "hi\nthere"),
            ("keys", "ctrl+v"),
            ("move", 10, 10),
            ("scroll", 0, -3),
        ]
        self.assertEqual(backend.events, one_run * 2)
        self.assertEqual(engine.snapshot().count, 2)

    def test_use_cursor_skips_the_move(self):
        backend = FakeBackend()
        engine = Engine(backend)
        engine.start(self.macro([Step(type=StepType.CLICK, use_cursor=True, delay_after_ms=1)]))
        engine.wait(3)
        self.assertEqual(backend.events, [("click", "left", 1)])

    def test_drag_presses_moves_and_releases(self):
        backend = FakeBackend()
        step = Step(type=StepType.DRAG, x=10, y=10, x2=110, y2=60, duration_ms=60, delay_after_ms=1)
        engine = Engine(backend)
        engine.start(self.macro([step]))
        engine.wait(3)
        kinds = [e[0] for e in backend.events]
        self.assertEqual(kinds[0:2], ["move", "down"])
        self.assertEqual(kinds[-1], "up")
        self.assertEqual(backend.pos, (110, 60))

    def test_stopping_mid_drag_still_releases_the_button(self):
        backend = FakeBackend()
        step = Step(type=StepType.DRAG, x=10, y=10, x2=500, y2=500, duration_ms=5000)
        engine = Engine(backend)
        engine.start(self.macro([step]))
        time.sleep(0.15)
        engine.stop()
        self.assertTrue(engine.wait(3))
        kinds = [e[0] for e in backend.events]
        self.assertIn("down", kinds)
        self.assertEqual(kinds[-1], "up")

    def test_gap_between_runs_is_shown_as_next_run(self):
        backend = FakeBackend()
        engine = Engine(backend)
        profile = self.macro([Step(type=StepType.CLICK, use_cursor=True, delay_after_ms=0)])
        profile.interval = Interval(seconds=30)
        profile.stop = StopRule()
        engine.start(profile)
        time.sleep(0.15)
        snap = engine.snapshot()
        self.assertEqual(snap.count, 1)
        self.assertTrue(20 < snap.next_in <= 30)
        engine.stop()
        self.assertTrue(engine.wait(3))

    def test_empty_macro_is_an_error(self):
        engine = Engine(FakeBackend())
        with self.assertLogs("clicksmith.engine", level="ERROR"):
            engine.start(self.macro([]))
            engine.wait(3)
        self.assertEqual(engine.snapshot().reason, StopReason.ERROR)


if __name__ == "__main__":
    unittest.main()
