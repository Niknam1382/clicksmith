# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet.

## [1.0.0] - 2026-09-25

### Added

- Clicker mode: left/right/middle button, single/double/triple click, click-and-hold, a
  configurable interval (h/m/s/ms) with a percentage of random jitter, and three targeting modes
  (follow the cursor, a fixed point, or a random point inside an area).
- Macro mode: a recorder that turns real mouse/keyboard input into an editable step list
  (click, move, drag, scroll, type Unicode text, press a key combination, wait), plus a manual
  step editor with an on-screen position picker.
- Full Unicode text typing on Windows via `SendInput` (`KEYEVENTF_UNICODE`), independent of the
  active keyboard layout - Persian, Arabic, CJK, emoji, all work.
- Three stop conditions (until stopped / a number of repetitions / a duration), a start delay,
  a failsafe corner, and an optional "stop if the mouse moves" guard.
- A daily/weekly scheduler (specific days and time), running from the system tray.
- Multiple named, importable/exportable JSON profiles.
- Global hotkeys (start/stop, capture position, emergency stop), configurable in Settings.
- A `clicksmith run <profile.json>` headless CLI mode with `--dry-run`, for scripting or CI.
- A full Persian (فارسی) translation with right-to-left layout, alongside English.
- Dark and light themes.
- An opt-in, privacy-respecting update check against GitHub Releases (off by default).

### Notes

- Windows is the primary supported platform (native `SendInput` backend). An experimental
  cross-platform backend for Linux/macOS is included, built on `pynput`; see the README.

[Unreleased]: https://github.com/OWNER/clicksmith/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/OWNER/clicksmith/releases/tag/v1.0.0
