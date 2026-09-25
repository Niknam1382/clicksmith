import unittest
from types import SimpleNamespace

from clicksmith.core.models import Button, StepType
from clicksmith.core.recorder import RecEvent, events_to_steps, key_name


def click(t, x, y, hold=0.05, button="left"):
    return [
        RecEvent(t, "mouse_down", x, y, button=button),
        RecEvent(t + hold, "mouse_up", x, y, button=button),
    ]


def key(t, name):
    return RecEvent(t, "key_down", key=name)


class RecorderTests(unittest.TestCase):
    def test_single_click(self):
        steps = events_to_steps(click(0.0, 120, 340))
        self.assertEqual(len(steps), 1)
        step = steps[0]
        self.assertEqual((step.type, step.x, step.y, step.clicks, step.hold_ms), (StepType.CLICK, 120, 340, 1, 0))
        self.assertEqual(step.delay_after_ms, 0)

    def test_quick_repeat_becomes_a_double_click(self):
        steps = events_to_steps(click(0.0, 50, 50) + click(0.2, 51, 50))
        self.assertEqual([(s.type, s.clicks) for s in steps], [(StepType.CLICK, 2)])

    def test_slow_or_distant_clicks_stay_separate_with_recorded_pause(self):
        steps = events_to_steps(click(0.0, 50, 50) + click(1.05, 400, 300))
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].delay_after_ms, 1000)

    def test_right_click_and_long_press(self):
        steps = events_to_steps(click(0.0, 5, 5, button="right") + click(3.0, 9, 9, hold=1.0))
        self.assertEqual(steps[0].button, Button.RIGHT)
        self.assertEqual(steps[1].hold_ms, 1000)

    def test_drag(self):
        events = [
            RecEvent(0.0, "mouse_down", 10, 10, button="left"),
            RecEvent(0.5, "mouse_up", 210, 110, button="left"),
        ]
        (step,) = events_to_steps(events)
        self.assertEqual(step.type, StepType.DRAG)
        self.assertEqual((step.x, step.y, step.x2, step.y2, step.duration_ms), (10, 10, 210, 110, 500))

    def test_typing_is_merged_into_one_text_step(self):
        events = [
            key(0.0, "shift"),
            key(0.1, "H"),
            RecEvent(0.15, "key_up", key="H"),
            RecEvent(0.16, "key_up", key="shift"),
            key(0.3, "i"),
            key(0.5, "space"),
        ]
        (step,) = events_to_steps(events)
        self.assertEqual((step.type, step.text), (StepType.TEXT, "Hi "))
        self.assertEqual(step.char_delay_ms, 200)

    def test_shortcuts_and_special_keys_become_key_steps(self):
        events = [
            key(0.0, "a"),
            key(0.1, "b"),
            key(0.5, "enter"),
            key(1.0, "ctrl"),
            key(1.1, "c"),
            RecEvent(1.2, "key_up", key="c"),
            RecEvent(1.3, "key_up", key="ctrl"),
            key(1.5, "shift"),
            key(1.6, "tab"),
        ]
        steps = events_to_steps(events)
        self.assertEqual(
            [(s.type, s.text or s.keys) for s in steps],
            [
                (StepType.TEXT, "ab"),
                (StepType.KEY, "enter"),
                (StepType.KEY, "ctrl+c"),
                (StepType.KEY, "shift+tab"),
            ],
        )

    def test_ignored_keys_are_dropped(self):
        steps = events_to_steps([key(0.0, "f8"), key(0.1, "x")], ignore_keys=["F8"])
        self.assertEqual([s.text for s in steps], ["x"])

    def test_scroll_events_merge(self):
        events = [
            RecEvent(0.00, "scroll", 10, 10, dy=-1),
            RecEvent(0.10, "scroll", 10, 10, dy=-1),
            RecEvent(0.20, "scroll", 10, 10, dy=-2),
        ]
        (step,) = events_to_steps(events)
        self.assertEqual((step.type, step.dy), (StepType.SCROLL, -4))

    def test_pauses_are_measured_between_step_boundaries(self):
        steps = events_to_steps(click(0.0, 1, 1) + [key(2.05, "enter")])
        self.assertEqual(steps[0].delay_after_ms, 2000)
        self.assertEqual(steps[1].delay_after_ms, 0)

    def test_key_name_of_pynput_like_objects(self):
        self.assertEqual(key_name(SimpleNamespace(name="ctrl_l")), "ctrl")
        self.assertEqual(key_name(SimpleNamespace(name="page_up")), "pageup")
        self.assertEqual(key_name(SimpleNamespace(char="x")), "x")
        self.assertEqual(key_name(SimpleNamespace(char="\x03", vk=0x43)), "c")
        self.assertIsNone(key_name(SimpleNamespace(char=None, vk=None)))


if __name__ == "__main__":
    unittest.main()
