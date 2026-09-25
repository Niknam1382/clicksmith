import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clicksmith.core import paths
from clicksmith.core.models import Profile, RunMode, Step, StepType
from clicksmith.core.storage import (
    AppSettings,
    ProfileStore,
    SettingsStore,
    safe_filename,
)


class ProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = ProfileStore(Path(self._tmp.name))

    def test_save_load_roundtrip_with_unicode_name(self):
        profile = Profile(name="پروفایل من", mode=RunMode.MACRO)
        profile.steps.append(Step(type=StepType.TEXT, text="سلام 👋"))
        self.store.save(profile)
        self.assertEqual(self.store.names(), ["پروفایل من"])
        self.assertEqual(self.store.load("پروفایل من"), profile.normalize())

    def test_no_temp_files_are_left_behind(self):
        self.store.save(Profile(name="A"))
        self.assertEqual([p.suffix for p in Path(self._tmp.name).iterdir()], [".json"])

    def test_names_are_sorted_case_insensitively(self):
        for name in ("beta", "Alpha", "gamma"):
            self.store.save(Profile(name=name))
        self.assertEqual(self.store.names(), ["Alpha", "beta", "gamma"])

    def test_unique_name_import_and_rename_and_delete(self):
        self.store.save(Profile(name="Clicker"))
        self.assertEqual(self.store.unique_name("Clicker"), "Clicker (2)")
        exported = Path(self._tmp.name) / "elsewhere.json"
        exported.write_text('{"name": "Clicker", "mode": "macro"}', encoding="utf-8")
        imported = self.store.import_file(exported)
        self.assertEqual((imported.name, imported.mode), ("Clicker (2)", RunMode.MACRO))
        self.store.rename("Clicker (2)", "Renamed")
        self.assertIn("Renamed", self.store.names())
        self.assertNotIn("Clicker (2)", self.store.names())
        self.store.delete("Renamed")
        self.assertNotIn("Renamed", self.store.names())

    def test_import_without_a_name_uses_the_file_name(self):
        source = Path(self._tmp.name) / "my-preset.json"
        source.write_text("{}", encoding="utf-8")
        self.assertEqual(self.store.import_file(source).name, "my-preset (2)")

    def test_corrupt_file_raises_value_error(self):
        (Path(self._tmp.name) / "bad.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.load("bad")

    def test_safe_filename(self):
        self.assertEqual(safe_filename('a/b:c*"d'), "a_b_c__d")
        self.assertEqual(safe_filename(".."), "profile")
        self.assertEqual(safe_filename("x" * 200), "x" * 80)


class SettingsAndPathsTests(unittest.TestCase):
    def test_settings_roundtrip_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            self.assertEqual(store.load(), AppSettings())  # missing file
            store.save(AppSettings(language="fa", hotkey_toggle="Ctrl+F6", close_to_tray=False))
            loaded = store.load()
            self.assertEqual((loaded.language, loaded.hotkey_toggle, loaded.close_to_tray), ("fa", "Ctrl+F6", False))
            store.path.write_text("garbage", encoding="utf-8")
            self.assertEqual(store.load(), AppSettings())  # corrupt file

    def test_data_dir_override_and_portable_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CLICKSMITH_HOME": tmp}):
                self.assertEqual(paths.data_dir(), Path(tmp))
                self.assertTrue(paths.profiles_dir().is_dir())
                self.assertTrue(paths.logs_dir().is_dir())
            env = {k: v for k, v in os.environ.items() if k != "CLICKSMITH_HOME"}
            env["CLICKSMITH_PORTABLE"] = "1"
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertTrue(paths.is_portable())
                self.assertEqual(paths.data_dir().name, "data")
                self.assertEqual(paths.data_dir().parent, paths.app_dir())


if __name__ == "__main__":
    unittest.main()
