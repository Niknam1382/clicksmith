import unittest

from clicksmith.core.updater import is_newer, parse_version


class UpdaterTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.10-rc1"), (1, 10))
        self.assertEqual(parse_version("garbage"), (0,))

    def test_is_newer(self):
        self.assertTrue(is_newer("v1.0.1", "1.0.0"))
        self.assertTrue(is_newer("1.10.0", "1.9.9"))
        self.assertTrue(is_newer("2.0", "1.9.9"))
        self.assertFalse(is_newer("1.0.0", "1.0.0"))
        self.assertFalse(is_newer("v1.0", "1.0.0"))
        self.assertFalse(is_newer("0.9.9", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
