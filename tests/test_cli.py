import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clicksmith import __version__
from clicksmith.cli import build_parser, main
from clicksmith.core.models import Profile, RunMode, StopMode, StopRule


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with mock.patch("clicksmith.core.log.setup_logging"):
            code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write_profile(self, profile: Profile) -> str:
        path = self.dir / "p.json"
        path.write_text(json.dumps(profile.to_dict()), encoding="utf-8")
        return str(path)

    def test_parser(self):
        args = build_parser().parse_args(["run", "x.json", "--dry-run", "--count", "3"])
        self.assertEqual((args.command, args.profile, args.dry_run, args.count), ("run", "x.json", True, 3))
        self.assertFalse(build_parser().parse_args([]).minimized)

    def test_version(self):
        with self.assertRaises(SystemExit) as raised:
            run_cli("--version")
        self.assertEqual(raised.exception.code, 0)

    def test_dry_run_executes_the_profile_without_touching_input(self):
        profile = Profile(name="cli")
        profile.interval.millis = 1
        profile.stop = StopRule(StopMode.COUNT, count=3)
        profile.safety.failsafe_corner = False
        profile.safety.prevent_sleep = False
        profile.safety.start_delay_s = 0
        code, out, _ = run_cli("run", self.write_profile(profile), "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("[dry-run] click left 1"), 3)

    def test_count_and_delay_overrides(self):
        profile = Profile(name="cli")
        profile.interval.millis = 1
        profile.safety.failsafe_corner = False
        profile.safety.prevent_sleep = False
        code, out, _ = run_cli("run", self.write_profile(profile), "--dry-run", "--count", "2", "--delay", "0")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("[dry-run] click"), 2)

    def test_missing_profile_is_a_clean_error(self):
        code, _, err = run_cli("run", str(self.dir / "nope.json"), "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("No profile", err)

    def test_invalid_profile_is_rejected_before_running(self):
        profile = Profile(name="empty", mode=RunMode.MACRO)  # macro with no steps
        code, _, err = run_cli("run", self.write_profile(profile), "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("no steps", err)

    def test_version_constant_is_semver_like(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
