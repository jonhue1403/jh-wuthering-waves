"""Offline tests for the one-command qualification tool, no game controls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.qualify_farming_one_shot import (
    _catalog_snapshot, _module_counts, _phase, LIVE_GATES, TARGET_MODULES,
)


class TestFarmingOneShot(unittest.TestCase):
    def test_all_27_materials_are_explicitly_blocked_until_live_review(self):
        result = _catalog_snapshot()
        self.assertEqual(27, result["material_count"])
        self.assertEqual("CATALOG_ONLY", result["qualification"])
        self.assertFalse(result["game_input_issued"])
        self.assertEqual(27, len(result["materials"]))
        self.assertEqual(27, len({r["id"] for r in result["materials"]}))
        for item in result["materials"]:
            with self.subTest(item=item["name"]):
                self.assertFalse(item["can_start"])
                self.assertEqual(0, item["qualified_route_count"])
                self.assertEqual("NOT_RUN", item["live_qualification"])
                self.assertIn(item["readiness"],
                              ("SOURCE_DOCUMENTED", "SOURCE_UNRESOLVED"))
        mech = next(r for r in result["materials"] if r["id"] == "ff-mech-core")
        self.assertEqual(5, mech["documented_possible_source_count"])
        self.assertTrue(all(
            r["documented_possible_source_count"] == 0
            for r in result["materials"] if r["id"] != "ff-mech-core"
        ))

    def test_targeted_modules_include_both_frontends(self):
        self.assertIn("tests.TestFarmingAssistantQt", TARGET_MODULES)
        self.assertIn("tests.TestFarmingStandaloneWeb", TARGET_MODULES)
        self.assertIn("tests.TestFarmingSelection", TARGET_MODULES)
        self.assertTrue(any("Terra" in gate for gate in LIVE_GATES))

    @staticmethod
    def sample_result(path, *, sha="abcdef", exit_code=0,
                      tests=4, log="Ran 4 tests in 0.1s\n\nOK (skipped=2)\n"):
        path.mkdir(parents=True, exist_ok=True)
        (path / "results.json").write_text(json.dumps({
            "sha": sha,
            "dirty_at_start": False,
            "results": [{
                "module": "TestSyntheticModule", "exit_code": exit_code,
                "tests": tests,
            }],
        }), encoding="utf-8")
        (path / "TestSyntheticModule.log").write_text(log, encoding="utf-8")

    def test_real_verifier_summary_counts_runs_and_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.sample_result(path)
            summary = _module_counts(path, expected_sha="abcdef")
            self.assertEqual(1, summary["module_count"])
            self.assertEqual(4, summary["tests_run"])
            self.assertEqual(2, summary["skipped"])
            self.assertEqual(2, summary["passed"])
            self.assertEqual([], summary["failed_modules"])
            self.assertFalse(summary["verifier_dirty_at_start"])

    def test_wrong_sha_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.sample_result(path)
            with self.assertRaisesRegex(ValueError, "different commit"):
                _module_counts(path, expected_sha="fedcba")

    def test_failure_is_recorded_not_reported_as_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.sample_result(path, exit_code=1,
                               log="Ran 4 tests in 0.1s\n\nFAILED (failures=1)\n")
            summary = _module_counts(path, expected_sha="abcdef")
            self.assertIsNone(summary["passed"])
            self.assertEqual(4, summary["tests_run"])
            self.assertTrue(summary["failed_modules"])

    def test_missing_test_log_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.sample_result(path)
            (path / "TestSyntheticModule.log").unlink()
            summary = _module_counts(path, expected_sha="abcdef")
            self.assertTrue(any("missing log" in error
                                for error in summary["failed_modules"]))

    def test_malformed_results_do_not_qualify(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.sample_result(path, tests=None)
            summary = _module_counts(path, expected_sha="abcdef")
            self.assertTrue(summary["failed_modules"])

    def test_real_subprocess_records_stdout_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _phase("ok", [sys.executable, "-c", "print('PASSING')"],
                            timeout=30, output=Path(tmp))
            self.assertEqual("PASS", result["state"])
            self.assertEqual(0, result["exit_code"])
            self.assertIn("PASSING", (Path(tmp) / result["log"]).read_text())

    def test_missing_executable_is_blocked_without_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _phase("missing", ["executable-that-does-not-exist-987654321"],
                            timeout=5, output=Path(tmp))
            self.assertEqual("BLOCKED", result["state"])
            self.assertIsNone(result["exit_code"])


if __name__ == "__main__":
    unittest.main()
