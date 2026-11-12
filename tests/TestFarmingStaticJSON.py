"""Hermetic read-only calibration JSON parser tests; no game imports."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.automation.farming_static_json import read_static_json


class TestFarmingStaticJSON(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "candidate.json"

    def read(self, content, limit=1024):
        self.path.write_bytes(content.encode("utf-8"))
        return read_static_json(self.path, max_bytes=limit)

    def test_valid_nested_metadata_is_preserved(self):
        self.assertEqual(
            {"schema_version": 1, "source": {"game_mob_id": "12345"}},
            self.read('{"schema_version":1,"source":{"game_mob_id":"12345"}}'),
        )

    def test_duplicate_root_or_nested_keys_rejected(self):
        for content in (
            '{"id":"first","id":"second"}',
            '{"source":{"mob_id":"123","mob_id":"456"}}',
            '{"nested":{"x":1},"nested":{"x":1}}',
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.read(content)

    def test_nonstandard_json_constants_rejected(self):
        for content in ('{"n":NaN}', '{"n":Infinity}', '{"n":-Infinity}'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.read(content)

    def test_file_byte_limit_and_object_shape_enforced(self):
        for content in ("[]", "null", "true", '"text"', '42', ''):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.read(content)
        with self.assertRaises(ValueError):
            self.read('{"long":"' + "a" * 100 + '"}', limit=40)
        with self.assertRaises(ValueError):
            self.read('{"ok":true}', limit=0)
        with self.assertRaises(ValueError):
            self.read('{"ok":true}', limit=True)


if __name__ == "__main__":
    unittest.main()
