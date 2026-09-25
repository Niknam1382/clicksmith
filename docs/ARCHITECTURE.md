# Architecture

Clicksmith is split into a GUI-free **core** and a **PySide6 UI** that is, deliberately, a thin
layer on top of it. The goal: every rule about *what* Clicksmith does (timing, safety limits,
what a macro step means) lives in one place, is unit-testable without a display, mouse, or
keyboard, and is reusable from the headless CLI.

```
                      ┌────────────────────────┐
                      │   ui/main_window.py     │   PySide6 widgets only.
                      │   ui/dialogs.py         │   Reads/writes a Profile;
                      │   ui/picker.py, ...     │   never contains automation logic.
                      └───────────┬─────────────┘
                                  │ Profile, Engine, HotkeyManager, Recorder
                      ┌───────────▼─────────────┐
                      │        core/            │   No PySide6 import anywhere in here.
                      │  models · engine · ...  │   Exercised directly by cli.py too.
                      └───────────┬─────────────┘
                                  │ InputBackend
                 ┌────────────────┼─────────────────┐
                 ▼                ▼                 ▼
           win32.py         pynput_backend.py     fake.py
        (Windows SendInput)   (Linux/macOS)     (used by tests)
```

## `core/models.py` - the data

A `Profile` is a plain dataclass tree (`Interval`, `ClickSpec`, `Target`, `StopRule`, `Safety`,
`Step`, `Schedule`). `Profile.to_dict()` / `.from_dict()` (de)serialize it to the JSON that's
saved to disk - see [PROFILE_FORMAT.md](PROFILE_FORMAT.md).

Deserialization is deliberately forgiving: `dataclass_from_dict` drops unknown keys and falls back
to field defaults on a bad value, so a hand-edited or older profile file never crashes the app -
it just loses the one field that didn't parse. `Profile.normalize()` then clamps every numeric
field into a sane range. The engine calls `normalize()` on the profile it's given, so it never has
to defend against a negative interval or a click count of zero.

## `core/engine.py` - running a profile

`Engine` runs one `Profile` on a background `threading.Thread` and reports state transitions
(`idle → waiting → running → idle`) through a single callback, so the UI thread never blocks.
Two run loops share one class: `_loop_clicker` (interval + target + stop rule) and `_loop_macro`
(step list, repeated per the same interval/stop rule). Both loops call `_check()` between every
action, which raises an internal `_Halt` exception the instant a stop condition is met -
`engine.stop()`, the failsafe corner, or "the mouse moved" - so a run stops within one polling
tick even in the middle of a long wait or a slow drag, and a drag's mouse-button-up always runs
via `finally`.

Timing (`core/timing.py`) sleeps in chunks and busy-waits only the last ~2 ms, so a "click every
100 ms" profile is accurate to a couple of milliseconds without pinning a CPU core - important
since a naive `time.sleep()` loop drifts, and a naive spin loop wastes a whole core doing nothing.

## `core/input/` - one interface, three backends

Every backend implements `InputBackend` (`move_to`, `click`, `type_char`, ...). The engine and
recorder only ever talk to that interface:

- **`win32.py`** - the primary backend. Calls `SendInput` directly via `ctypes`, using a
  *private* `WinDLL` handle so its argument-type declarations can't collide with another
  library's (relevant because `pynput` is also loaded, for hotkeys/recording, and configures the
  shared `ctypes.windll.user32` object). Unicode text is typed with `KEYEVENTF_UNICODE`, so it
  works regardless of the active keyboard layout - this is how Clicksmith types Persian, Arabic,
  or emoji even on an English keyboard layout.
- **`pynput_backend.py`** - a cross-platform fallback for Linux/macOS. Marked experimental
  because `pynput`'s Unicode typing and global-hotkey support vary by platform/display server.
- **`fake.py`** - a no-op backend that records every call it received. Used by the entire test
  suite (`tests/test_engine.py`, `tests/test_cli.py`, ...) and by `--dry-run`, so tests never move
  a real mouse.

## `core/recorder.py` - turning input into steps

`Recorder` wraps two `pynput` listeners and timestamps every raw event. The actual conversion,
`events_to_steps()`, is a pure function (`Iterable[RecEvent] -> list[Step]`) so it's tested with
plain data, no listeners involved: quick repeated clicks near the same point become one
double/triple-click step, a press-drag-release beyond a small threshold becomes a `drag` step,
consecutive character keys become one `text` step (so typing "hello" is one step, not five), and
the gap between events becomes each step's recorded `delay_after_ms`.

## `core/hotkeys.py` and the recorder run on pynput's threads

Global hotkeys and the recorder's listeners fire their callbacks on a `pynput`-owned thread, not
the Qt GUI thread. `ui/bridge.py`'s `Bridge` (a `QObject` with `Signal`s) is the only bridge
between them: a hotkey callback does nothing but `bridge.hotkey.emit(name)`, and Qt's queued
connections deliver it to `MainWindow` on the GUI thread. The engine's `on_state` callback and the
Python `logging` handler (`QtLogHandler`) follow the same pattern. **Rule of thumb: nothing off
the GUI thread ever touches a widget directly.**

## Why PySide6 over PyQt6

Both bind the same Qt 6 widgets and would have worked. PySide6 is chosen because it's
LGPL-licensed (Qt Company's own binding), which lets Clicksmith be MIT-licensed and distribute a
built `.exe` without triggering PyQt6's GPL/commercial dual-license terms.

## The CLI (`cli.py`) is not a thin wrapper around the GUI

`clicksmith run <profile.json>` builds the exact same `Engine` + `Profile` + real
`InputBackend` the GUI uses - it imports nothing from `ui/`. This is why `core/` having zero
PySide6 dependency matters: the same automation logic is reachable from a script, a scheduled
task, or CI, with no Qt runtime required.
