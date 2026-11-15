"""Validate current OK-WW OCR item binding, not a separate OCR engine."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.automation.observations import RoutineObserver
from src.automation.resource_policy import ClaimIdentity, ResourcePolicyError


class TestRoutineOCRItemBinding(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        screenshot = b"unit-test calibration screenshot bytes"
        (self.root / "source.png").write_bytes(screenshot)
        self.profile_path = self.root / "observation.json"
        self.profile = {
            "schema_version": 1,
            "qualified": True,
            "framework_version": "unit-runtime",
            "language": "en_US",
            "resolution": [1280, 720],
            "activity": "overworld",
            "qualification_evidence": "synthetic-test-not-live",
            "screenshot": "source.png",
            "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
            "page_feature": "observed_item_page",
            "identity_profile": "observed-identity.json",
            "status": {
                "box": [0.05, 0.05, 0.25, 0.15],
                "eligible_text": "READY",
                "completed_text": "DONE",
            },
            "inventory": {
                "FF Mech Core": {
                    "item_text": "FF Mech Core",
                    "label_box": [0.1, 0.2, 0.4, 0.3],
                    "box": [0.6, 0.2, 0.85, 0.3],
                },
            },
        }
        self.task = SimpleNamespace(
            game_lang="en_US", width=1280, height=720,
            find_one=Mock(return_value=True),
            ocr=Mock(), sleep=Mock(),
        )

    def make_observer(self):
        self.profile_path.write_text(
            json.dumps(self.profile), encoding="utf-8")
        with patch("src.automation.observations.importlib.metadata.version",
                   return_value="unit-runtime"):
            return RoutineObserver(
                self.task, self.profile_path, "overworld")

    def test_matching_label_is_accepted_as_configured_not_live_verified(self):
        observer = self.make_observer()
        self.assertEqual("FF Mech Core",
                         observer.profile["inventory"]["FF Mech Core"]["item_text"])

    def test_misbound_item_label_rejected_before_capture(self):
        self.profile["inventory"]["FF Mech Core"]["item_text"] = "Premium Tuner"
        with self.assertRaisesRegex(ResourcePolicyError, "not bound"):
            self.make_observer()
        self.task.ocr.assert_not_called()
        self.task.find_one.assert_not_called()

    def test_alias_duplicate_material_name_rejected(self):
        self.profile["inventory"]["FF  Mech Core"] = dict(
            self.profile["inventory"]["FF Mech Core"],
            item_text="FF  Mech Core",
        )
        with self.assertRaisesRegex(ResourcePolicyError, "Ambiguous duplicate"):
            self.make_observer()

    def test_two_fresh_frames_reuse_existing_task_ocr(self):
        observer = self.make_observer()
        specs = self.profile
        positions = {
            tuple(specs["status"]["box"]): "READY",
            tuple(specs["inventory"]["FF Mech Core"]["label_box"]): "FF Mech Core",
            tuple(specs["inventory"]["FF Mech Core"]["box"]): "4",
        }
        self.task.ocr.side_effect = lambda *rect: [
            SimpleNamespace(name=positions[tuple(rect)])
        ]
        identity = ClaimIdentity("test-user", "test-server", "overworld", "cycle-1")
        with patch("src.automation.observations.observe_identity",
                   return_value=identity), patch(
                   "src.automation.observations.fresh_observation",
                   side_effect=["frame-01", "frame-02"]) as frames:
            observed, inventory = observer.observe()
        self.assertEqual({"FF Mech Core": 4}, inventory)
        self.assertFalse(observed.reward_received)
        self.assertTrue(observed.qualified)
        self.assertEqual(2, frames.call_count)
        self.assertEqual(6, self.task.ocr.call_count)
        self.task.sleep.assert_called_once_with(0.3)

    def test_ocr_label_mismatch_rejected_without_receipt(self):
        observer = self.make_observer()
        specs = self.profile
        positions = {
            tuple(specs["status"]["box"]): "READY",
            tuple(specs["inventory"]["FF Mech Core"]["label_box"]): "Premium Tuner",
            tuple(specs["inventory"]["FF Mech Core"]["box"]): "5",
        }
        self.task.ocr.side_effect = lambda *rect: [
            SimpleNamespace(name=positions[tuple(rect)])
        ]
        identity = ClaimIdentity("test-user", "test-server", "overworld", "cycle-1")
        with patch("src.automation.observations.observe_identity",
                   return_value=identity), patch(
                   "src.automation.observations.fresh_observation",
                   return_value="frame-01"):
            with self.assertRaisesRegex(ResourcePolicyError, "does not match"):
                observer.observe({"FF Mech Core": 4})


if __name__ == "__main__":
    unittest.main()
