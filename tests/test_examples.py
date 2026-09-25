import importlib.util
import json
import unittest
from pathlib import Path

from clicksmith.core.storage import load_profile_file
from clicksmith.core.validation import problems

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "profiles" / "examples"


class ExampleProfileTests(unittest.TestCase):
    def test_every_example_loads_and_is_runnable(self):
        files = sorted(EXAMPLES.glob("*.json"))
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with self.subTest(path.name):
                self.assertEqual(problems(load_profile_file(path)), [])

    def test_examples_are_in_sync_with_the_generator(self):
        spec = importlib.util.spec_from_file_location(
            "generate_examples", ROOT / "scripts" / "generate_examples.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for filename, profile in module.examples().items():
            with self.subTest(filename):
                on_disk = json.loads((EXAMPLES / f"{filename}.json").read_text(encoding="utf-8"))
                self.assertEqual(on_disk, profile.normalize().to_dict())


if __name__ == "__main__":
    unittest.main()
