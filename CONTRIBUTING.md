# Contributing to Clicksmith

Thanks for considering a contribution! This project welcomes bug reports, feature ideas, example
profiles, translations, and code.

## Ground rules

- Be kind - see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Open an issue before starting a large change, so we can agree on the approach first.
- Small, focused pull requests are much easier to review than large ones.

## Project layout

```
src/clicksmith/
  core/        GUI-free logic: models, the automation engine, input backends, storage,
               scheduling, hotkeys, the recorder, i18n. No PySide6 import belongs in here.
  core/input/  One backend per platform behind the same InputBackend interface
               (win32.py = native Windows SendInput, pynput_backend.py = Linux/macOS,
               fake.py = used by every automated test).
  ui/          PySide6 widgets, dialogs, the main window and theming. Talks to core/ only
               through Engine, Profile, and the storage/i18n modules.
  cli.py       `clicksmith` console entry point (launches the GUI, or `clicksmith run ...`).
  app.py       GUI bootstrap (logging, single-instance lock, QApplication, main window).
tests/         unittest-style tests; a fake input backend and a fake PySide6 (see below) let
               almost everything run without a real display, mouse, or keyboard.
packaging/     the PyInstaller spec and the Inno Setup installer script.
profiles/examples/  ready-made profiles + the script that generates them from the data model.
docs/          architecture notes, the profile JSON format, and the FAQ.
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together.

## Setting up a dev environment

You can edit and run the test suite on Linux, macOS, or Windows; building `Clicksmith.exe`
itself requires Windows (see [docs/BUILDING.md](docs/BUILDING.md)).

```bash
git clone https://github.com/OWNER/clicksmith.git
cd clicksmith
./scripts/dev_setup.sh          # Linux/macOS
# or, on Windows:
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements-dev.txt

python -m clicksmith             # run the GUI from source
python -m pytest -q              # run the test suite
ruff check .                     # pyflakes: undefined names, unused imports/variables
mypy                              # type-checks src/clicksmith/core
```

`ruff check .` and `mypy` run in CI too, but as informational jobs (`continue-on-error`), not merge
gates - only the test suite and the Windows build blocking a release. That's deliberate for now:
this codebase has never been run through `ruff format`, so turning on formatting-opinionated rule
sets (or `ruff format --check`) before that would fail on style noise rather than real problems.
If you'd like to help: run `ruff format .` once locally, open a PR with just that diff, then
`select` in `pyproject.toml`'s `[tool.ruff.lint]` can grow from `["F"]` to include `E`/`W`/`I` and
`ruff format --check .` can become a real, passing gate.

## Testing without a display, mouse, or keyboard

- `core/input/fake.py` is a no-op `InputBackend` that just records what it was asked to do.
  Every engine/CLI test uses it, so tests never move your real mouse.
- GUI tests (`tests/test_ui_smoke.py`) run with `QT_QPA_PLATFORM=offscreen` and are skipped
  automatically if PySide6 isn't installed.
- `python -m clicksmith run some_profile.json --dry-run` prints what the engine *would* do
  instead of doing it - handy for testing a profile without triggering real clicks.

## Adding a feature

1. Add/extend the data model in `core/models.py` if it needs new profile fields (keep
   `normalize()` clamping values to sane ranges - the engine trusts normalized input).
2. Implement the behaviour in `core/engine.py` (or the relevant `core/` module).
3. Wire it into the UI (`ui/main_window.py`, `ui/dialogs.py`).
4. Add both an English string and its Persian translation - `tests/test_i18n.py` fails the
   build if a UI string has no `translations.FA` entry.
5. Add tests. Aim to test `core/` logic directly (fast, no Qt needed) rather than only through
   the UI.
6. Update `CHANGELOG.md` under **Unreleased**.

## Adding a language

1. Add `"<code>": "<Native name>"` to `LANGUAGES` in `core/i18n.py` (and to `RTL_LANGUAGES` if
   it's right-to-left).
2. Add a `<CODE>: dict[str, str] = {...}` to `core/translations.py` and register it in
   `TRANSLATIONS`.
3. `pytest tests/test_i18n.py` tells you exactly which English strings still need a translation.

## Adding an example profile

Add a `Profile(...)` to `examples()` in `scripts/generate_examples.py`, run
`python scripts/generate_examples.py`, and add a row to `profiles/examples/README.md`. Don't
hand-edit the JSON files in `profiles/examples/` - they're generated, and `tests/test_examples.py`
checks they stay in sync with the generator.

## Commit / PR style

- Write commit messages and PR descriptions in plain, specific English (what changed and why).
- Fill in the PR template's testing checklist honestly - "not tested" is a fine answer if true.
