"""Command line entry point: launches the GUI by default, or runs a profile headless."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import APP_NAME, __version__

_CONSOLE_COMMANDS = {"run", "list", "-h", "--help", "--version"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clicksmith",
        description=f"{APP_NAME}: auto clicker, macro recorder, Unicode typing and scheduler.",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "--portable", action="store_true", help="keep settings and profiles next to the program"
    )
    parser.add_argument("--minimized", action="store_true", help="start hidden in the tray")
    parser.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--wait-lock", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run a profile without the GUI")
    run.add_argument("profile", help="path to a profile .json file, or a saved profile name")
    run.add_argument("--delay", type=float, help="start delay in seconds (overrides the profile)")
    run.add_argument("--count", type=int, help="stop after this many repetitions")
    run.add_argument("--dry-run", action="store_true", help="print the actions instead of doing them")
    run.add_argument("--no-hotkeys", action="store_true", help="do not register the panic hotkey")

    sub.add_parser("list", help="list saved profiles")
    return parser


def _load_profile(arg: str):
    from .core.storage import ProfileStore, load_profile_file

    path = Path(arg)
    if path.suffix.lower() == ".json" and path.exists():
        return load_profile_file(path)
    store = ProfileStore()
    if store.exists(arg):
        return store.load(arg)
    raise FileNotFoundError(f"No profile file or saved profile named '{arg}'")


def _cmd_list() -> int:
    from .core.storage import ProfileStore

    for name in ProfileStore().names():
        print(name)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from .core.engine import Engine, StopReason
    from .core.hotkeys import HotkeyManager
    from .core.input import FakeBackend, create_backend
    from .core.log import setup_logging
    from .core.models import StopMode, StopRule
    from .core.storage import SettingsStore
    from .core.sysutils import enable_dpi_awareness
    from .core.validation import problems

    enable_dpi_awareness()
    setup_logging(console=True)
    try:
        profile = _load_profile(args.profile)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.count:
        profile.stop = StopRule(StopMode.COUNT, count=args.count)
    issues = problems(profile)
    if issues:
        for issue in issues:
            print(f"error: {issue}", file=sys.stderr)
        return 2

    backend = FakeBackend(verbose=True) if args.dry_run else create_backend()
    engine = Engine(backend)
    hotkeys = None
    if not args.dry_run and not args.no_hotkeys:
        panic = SettingsStore().load().hotkey_panic
        hotkeys = HotkeyManager()
        errors = hotkeys.register({panic: engine.stop})
        for message in errors:
            print(f"warning: {message}", file=sys.stderr)
        if not errors:
            print(f"Press {panic} (or Ctrl+C) to stop.")
    engine.start(profile, start_delay=args.delay)
    try:
        while not engine.wait(0.2):
            pass
    except KeyboardInterrupt:
        engine.stop()
        engine.wait(3)
    finally:
        if hotkeys is not None:
            hotkeys.stop()
    return 1 if engine.snapshot().reason == StopReason.ERROR else 0


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] in _CONSOLE_COMMANDS or not args_list and sys.stdout is None:
        from .core.sysutils import attach_parent_console

        attach_parent_console()
    args = build_parser().parse_args(args_list)
    if args.portable:
        os.environ["CLICKSMITH_PORTABLE"] = "1"
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "list":
        return _cmd_list()
    from .app import run_gui

    return run_gui(minimized=args.minimized, selftest=args.selftest, wait_lock=args.wait_lock)


if __name__ == "__main__":
    raise SystemExit(main())
