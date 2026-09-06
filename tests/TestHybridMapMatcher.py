from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.overworld.models import MapCoordinate
from src.overworld.navigation.image_matcher import HybridMapMatcher, MatcherCalibration, pixel_hash
from src.overworld.navigation.player_locator import LocalizationEvidence, PlayerLocator, SurfaceProfile


class TestHybridMapMatcher(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(12)
        self.reference = cv2.GaussianBlur(rng.integers(0, 256, (384, 384, 3), dtype=np.uint8), (3, 3), 0)
        self.mini = self.reference[70:197, 90:218].copy()
        self.mask = np.zeros(self.mini.shape[:2], dtype=np.uint8)
        cv2.circle(self.mask, (64, 63), 63, 255, -1)
        cv2.rectangle(self.mask, (49, 48), (79, 78), 0, -1)
        # Synthetic fixture policy, unrelated to measured surface-test-01 gates.
        self.policy = MatcherCalibration(pixel_hash(self.reference), pixel_hash(self.mask), (128, 127),
                                         906, "", .7, 8, .2, 5, .01, 1.5)
        self.matcher = HybridMapMatcher(self.reference, self.policy)

    def test_two_signals_localize_without_expected_position(self):
        result = self.matcher.match(self.mini, self.mask)
        self.assertTrue(result.accepted, result)
        self.assertEqual((154, 134), result.pixel_xy)
        self.assertGreater(result.feature_inliers, 5)
        self.assertLess(result.geometry_error, 1)
        self.assertLess(result.agreement_error, 1)
        self.assertEqual("gradient_sift", result.source)

    def test_wrong_gallery_rejects_instead_of_returning_best_bad_location(self):
        wrong = self.reference[:, 218:]
        matcher = HybridMapMatcher(wrong, replace(self.policy, reference_pixel_sha256=pixel_hash(wrong)))
        result = matcher.match(self.mini, self.mask)
        self.assertFalse(result.accepted)
        self.assertIn("gradient_score", result.reason)

    def test_rotation_is_not_silently_corrected(self):
        rotated = cv2.warpAffine(self.mini, cv2.getRotationMatrix2D((64, 63.5), 20, 1), (128, 127))
        self.assertFalse(self.matcher.match(rotated, self.mask).accepted)

    def test_duplicate_terrain_rejects_ambiguous_peak(self):
        reference = self.reference.copy()
        reference[220:347, 220:348] = self.mini
        matcher = HybridMapMatcher(reference, replace(self.policy, reference_pixel_sha256=pixel_hash(reference)))
        result = matcher.match(self.mini, self.mask)
        self.assertFalse(result.accepted)
        self.assertIn("ambiguous_peak", result.reason)

    def test_blank_template_and_nonfinite_correlations_fail_closed(self):
        result = self.matcher.match(np.zeros_like(self.mini), self.mask)
        self.assertFalse(result.accepted)
        self.assertEqual(0, result.feature_inliers)

    def test_reference_mask_and_resolution_are_calibration_bound(self):
        with self.assertRaisesRegex(ValueError, "reference"):
            HybridMapMatcher(np.zeros_like(self.reference), self.policy)
        self.assertFalse(self.matcher.match(self.mini, np.ones_like(self.mask)).accepted)
        self.assertFalse(self.matcher.match(self.mini[:100], self.mask[:100]).accepted)

    def test_each_gate_is_required_even_with_a_good_gradient_score(self):
        good = LocalizationEvidence((10, 20), .9, "gradient_sift", second_best_score=.1, margin=.8,
                                    feature_pixel_xy=(10, 20), feature_matches=20, feature_inliers=18,
                                    geometry_error=.3, agreement_error=.4, feature_coverage=.3)
        self.assertTrue(self.policy.evaluate(good).accepted)
        failures = ({"confidence": .69}, {"confidence": float("nan")}, {"margin": .1},
                    {"feature_inliers": 4}, {"feature_coverage": 0}, {"feature_pixel_xy": None},
                    {"geometry_error": 2}, {"agreement_error": 2}, {"agreement_error": float("inf")})
        for change in failures:
            with self.subTest(change=change):
                self.assertFalse(self.policy.evaluate(replace(good, **change)).accepted)

    def test_invalid_or_weaker_policy_is_not_loaded(self):
        for change in ({"score_threshold": .69}, {"min_inliers": 2}, {"min_margin": 0},
                       {"max_geometry_error": float("nan")}, {"max_geometry_error": 0},
                       {"reference_pixel_sha256": "bad"}, {"minimap_size": (0, 0)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.policy, **change)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps({"schema_version": 1, "scope": "movement"}))
            with self.assertRaisesRegex(ValueError, "localization-only"):
                MatcherCalibration.load(path)

    def test_player_locator_exposes_raw_evidence_without_promoting_rejection(self):
        profile = SurfaceProfile(Path("ref.png"), Path("map.db"), "", 906, "", MapCoordinate(0, 0),
                                 10, (2560, 1440), frozenset())
        good = self.matcher.match(self.mini, self.mask)
        locator = PlayerLocator(profile, match_player=lambda: good, facing=lambda: None, image_size=(384, 384))
        position = locator.locate()
        self.assertEqual(906, position.state_id)
        self.assertEqual("", position.floor_id)
        self.assertIs(good, locator.last_evidence)
        locator.match_player = lambda: replace(good, accepted=False, reason="signals_disagree")
        self.assertIsNone(locator.locate())
        self.assertEqual(good.confidence, locator.last_confidence)
        self.assertEqual("signals_disagree", locator.last_evidence.reason)

    def test_player_locator_still_applies_bounds_and_profile_threshold(self):
        profile = SurfaceProfile(Path("ref.png"), Path("map.db"), "", 906, "", MapCoordinate(0, 0),
                                 10, (2560, 1440), frozenset(), match_threshold=.9)
        match = LocalizationEvidence((10, 20), .8, "gradient_sift", accepted=True)
        locator = PlayerLocator(profile, match_player=lambda: match, facing=lambda: None, image_size=(384, 384))
        self.assertIsNone(locator.locate())
        match = replace(match, confidence=.95, pixel_xy=(400, 10))
        self.assertIsNone(locator.locate())

    def test_test_a_hybrid_profile_cannot_enter_movement_startup(self):
        from src.task.HuntMobTask import HuntMobTask
        task = HuntMobTask(executor=Mock(), app=Mock())
        task.config = {**task.default_config, "Hunt Profile": "profile.json", "Localization Only": False}
        profile = SurfaceProfile(Path("ref.png"), Path("map.db"), "", 906, "", MapCoordinate(0, 0),
                                 10, (2560, 1440), frozenset(), matcher_calibration_path=Path("policy.json"))
        task.executor.reset_mock()  # Constructor reads ordinary framework options.
        with patch("src.task.HuntMobTask.SurfaceProfile.load", return_value=profile):
            with self.assertRaisesRegex(ValueError, "restricted to Localization Only"):
                task.run()
        self.assertEqual([], task.executor.mock_calls)

    def test_duplicate_sift_orientations_cannot_inflate_support(self):
        points = [Mock(pt=(float(i % 2 * 10), 10.0)) for i in range(12)]
        self.matcher.sift = Mock()
        self.matcher.sift.detectAndCompute.return_value = (points, np.zeros((12, 128), np.float32))
        self.matcher.reference_keypoints = [Mock(pt=(100.0 + i % 2 * 10, 80.0)) for i in range(12)]
        matches = [[cv2.DMatch(i, i, 1), cv2.DMatch(i, (i + 1) % 12, 100)] for i in range(12)]
        with patch("src.overworld.navigation.image_matcher.cv2.BFMatcher") as factory:
            factory.return_value.knnMatch.return_value = matches
            result = self.matcher.match(self.mini, self.mask)
        self.assertEqual(2, result.feature_matches)
        self.assertFalse(result.accepted)

    def test_task_frame_adapter_only_calls_matcher_not_inputs(self):
        from src.task.HuntMobTask import HuntMobTask
        task = HuntMobTask(executor=Mock(), app=Mock())
        task.executor.frame = np.zeros((1440, 2560, 3), np.uint8)
        task._hunt_profile = Mock(frame_size=(2560, 1440))
        task._check_hunt_cancel = Mock()
        task.in_team_and_world = Mock(return_value=True)
        task.get_box_by_name = Mock()
        task.get_box_by_name.return_value.crop_frame.return_value = self.mini
        task._hunt_matcher = Mock()
        task.executor.reset_mock()
        task._match_player()
        task._hunt_matcher.match.assert_called_once()
        self.assertEqual(1, task.executor.next_frame.call_count)
        self.assertEqual([], task.executor.interaction.mock_calls)

    def test_mismatched_layer_is_rejected_before_runtime_setup(self):
        from src.task.HuntMobTask import HuntMobTask
        task = HuntMobTask(executor=Mock(), app=Mock())
        task.config = {**task.default_config, "Hunt Profile": "profile.json", "Target Mob": "Target"}
        profile = SurfaceProfile(Path("ref.png"), Path("map.db"), "Target", 8, "", MapCoordinate(0, 0),
                                 10, (2560, 1440), frozenset(), matcher_calibration_path=Path("policy.json"))
        task.executor.reset_mock()
        with patch("src.task.HuntMobTask.SurfaceProfile.load", return_value=profile), \
                patch("src.task.HuntMobTask.np.fromfile", return_value=np.zeros(1, np.uint8)), \
                patch("src.task.HuntMobTask.cv2.imdecode", return_value=self.reference), \
                patch("src.task.HuntMobTask.MatcherCalibration.load", return_value=self.policy):
            with self.assertRaisesRegex(ValueError, "different map layer"):
                task.run()
        self.assertEqual([], task.executor.mock_calls)

    def test_capture_dataset_replay_with_frozen_policy(self):
        folder = Path(__file__).resolve().parents[1] / "assets/overworld/calibration/surface-test-01"
        policy_path = folder / "matcher_diagnosis/matcher_calibration.json"
        if not policy_path.is_file():
            self.skipTest("Private offline calibration dataset is not available")
        from scripts.analyze_surface_test_a import read_image
        from src.task.FarmMapTask import create_circle_mask_with_hole
        policy = MatcherCalibration.load(policy_path)
        matcher = HybridMapMatcher(read_image(folder / "analysis/reference_candidate.png"), policy)
        for index in range(1, 11):
            mini = read_image(folder / f"stationary_{index:03d}.png")[38:285, 48:296]
            evidence = matcher.match(mini, create_circle_mask_with_hole(mini))
            self.assertTrue(evidence.accepted, (index, evidence))
            self.assertEqual((479, 270), evidence.pixel_xy)


if __name__ == "__main__":
    unittest.main()
