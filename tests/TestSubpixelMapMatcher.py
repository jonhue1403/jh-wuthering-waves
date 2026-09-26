from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from src.overworld.navigation.image_matcher import HybridMapMatcher, MatcherCalibration, gradients, pixel_hash


class TestSubpixelMapMatcher(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(12)
        self.reference = cv2.GaussianBlur(rng.integers(0, 256, (384, 384, 3), dtype=np.uint8), (3, 3), 0)
        yy, xx = np.indices((127, 128), dtype=np.float32)
        self.mini = cv2.remap(self.reference, xx + 90.375, yy + 70.625, cv2.INTER_LINEAR)
        self.mask = np.zeros((127, 128), np.uint8)
        cv2.circle(self.mask, (64, 63), 58, 255, -1)
        cv2.rectangle(self.mask, (49, 48), (79, 78), 0, -1)
        self.policy = MatcherCalibration(pixel_hash(self.reference), pixel_hash(self.mask), (128, 127),
                                         906, "", .7, 8, .2, 5, .01, 1.5, sampling_mode="sift_phase")
        self.matcher = HybridMapMatcher(self.reference, self.policy)

    def test_fractional_crop_localizes_and_preserves_independent_agreement(self):
        evidence = self.matcher.match(self.mini, self.mask)
        self.assertTrue(evidence.accepted, evidence)
        np.testing.assert_allclose(evidence.pixel_xy, (154.375, 134.125), atol=.1)
        self.assertGreater(evidence.confidence, .95)
        integer = HybridMapMatcher(self.reference, replace(self.policy, sampling_mode="integer")).match(self.mini, self.mask)
        self.assertGreater(evidence.confidence, integer.confidence)
        self.assertGreaterEqual(evidence.agreement_error, integer.agreement_error)

    def test_one_phase_scores_competitors_fairly_without_boundary_padding(self):
        evidence, surface = self.matcher.measure(self.mini, self.mask)
        feature = np.asarray(evidence.feature_pixel_xy)
        phase = np.rint(((feature - [64, 63.5]) % 1) * 32) / 32
        self.assertEqual((258 - int(phase[1] > 0), 257 - int(phase[0] > 0)), surface.shape)
        yy, xx = np.indices(self.mask.shape, dtype=np.float32)
        query = gradients(self.mini)[self.mask > 0].astype(np.float64)
        for left, top in ((0, 0), (90, 70), (200, 200), (surface.shape[1] - 1, surface.shape[0] - 1)):
            sampled = cv2.remap(gradients(self.reference), xx + left + np.float32(phase[0]),
                                yy + top + np.float32(phase[1]), cv2.INTER_LINEAR)
            values = sampled[self.mask > 0].astype(np.float64)
            direct = np.sum(query * values) / np.sqrt(np.sum(query ** 2) * np.sum(values ** 2))
            self.assertAlmostEqual(direct, float(surface[top, left]), places=6)

    def test_wrong_sift_integer_location_cannot_be_repaired_by_its_phase(self):
        feature = self.matcher.feature_translation(self.mini, self.mask)
        good, original_surface = self.matcher.measure(self.mini, self.mask)
        wrong = {**feature, "feature_pixel_xy": tuple(np.asarray(feature["feature_pixel_xy"]) + [40, 0])}
        with patch.object(self.matcher, "feature_translation", return_value=wrong):
            evidence, surface = self.matcher.measure(self.mini, self.mask)
        np.testing.assert_array_equal(surface, original_surface)
        self.assertEqual(good.pixel_xy, evidence.pixel_xy)
        self.assertIn("signals_disagree", self.policy.evaluate(evidence).reason)

    def test_missing_or_nonfinite_phase_never_falls_back_to_integer(self):
        for feature in ({}, {"feature_pixel_xy": (float("nan"), 10)}, {"feature_pixel_xy": (10, float("inf"))}):
            with self.subTest(feature=feature), patch.object(self.matcher, "feature_translation", return_value=feature):
                evidence = self.matcher.match(self.mini, self.mask)
                self.assertFalse(evidence.accepted)
                self.assertIsNone(evidence.confidence)
                self.assertIsNone(evidence.second_best_score)
                self.assertEqual("gradient_sift_phase", evidence.source)

    def test_duplicate_with_strong_sift_is_rejected_by_margin(self):
        feature = self.matcher.feature_translation(self.mini, self.mask)
        repeated = np.concatenate((self.reference, self.reference), axis=1)
        matcher = HybridMapMatcher(repeated, replace(self.policy, reference_pixel_sha256=pixel_hash(repeated)))
        with patch.object(matcher, "feature_translation", return_value=feature):
            evidence = matcher.match(self.mini, self.mask)
        self.assertGreater(evidence.confidence, .95)
        self.assertGreaterEqual(evidence.feature_inliers, self.policy.min_inliers)
        self.assertAlmostEqual(evidence.confidence, evidence.second_best_score, places=6)
        self.assertIn("ambiguous_peak", evidence.reason)
        self.assertFalse(evidence.accepted)

    def test_old_calibrations_default_to_integer_and_unknown_modes_fail(self):
        data = asdict(self.policy)
        data.pop("sampling_mode")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(json.dumps({"schema_version": 1, "scope": "localization_only", "policy": data}))
            self.assertEqual("integer", MatcherCalibration.load(path).sampling_mode)
        for mode in (None, "best_fraction", ""):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                replace(self.policy, sampling_mode=mode)
        with self.assertRaises(ValueError):
            replace(self.policy, score_threshold=.699)

    def test_combined_real_dataset_and_all_controls_through_runtime_path(self):
        from scripts.validate_subpixel_gradient import ROOT, main
        if not (ROOT / "assets/overworld/calibration/surface-test-02/stationary_010.png").is_file():
            self.skipTest("Private captures are unavailable")
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            result = main(Path(directory))
        self.assertTrue(result["offline_clean"])
        self.assertEqual(20, result["summary"]["combined_positive"]["subpixel"]["accepted"])
        self.assertEqual(210, result["summary"]["combined_negative"]["count"])
        self.assertEqual(0, result["summary"]["combined_negative"]["subpixel"]["accepted"])
        self.assertEqual(.7, result["policy"]["score_threshold"])
        self.assertAlmostEqual(.3634031228721142, result["policy"]["min_margin"], places=6)
        for row in result["rows"]:
            if row["kind"] == "duplicate_strong_sift":
                self.assertGreaterEqual(row["subpixel"]["confidence"], .7)
                self.assertIn("ambiguous_peak", row["subpixel"]["reason"])
            if row["kind"] == "positive":
                self.assertEqual(row["partition"] != "fresh", row["integer"]["accepted"])


if __name__ == "__main__":
    unittest.main()
