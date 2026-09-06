"""Capture-independent, opt-in Test A matcher. No game/window/input APIs.

Color correlation remains unchanged elsewhere. Here signed gradients propose a
translation and independently matched SIFT keypoints must corroborate it.
Acceptance limits are loaded from reference-bound offline calibration evidence.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from .player_locator import LocalizationEvidence


def pixel_hash(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def gradients(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return np.dstack((cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)))


def correlation(reference, template, mask, method=cv2.TM_CCORR_NORMED):
    scores = cv2.matchTemplate(reference, template, method, mask=mask)
    return np.nan_to_num(scores, nan=0, posinf=0, neginf=0)


def distinct_peaks(scores, template_size, radius, count=5):
    """NMS in translation pixels; nearby pixels of one peak are not five places."""
    working = scores.copy()
    yy, xx = np.indices(working.shape)
    width, height = template_size
    peaks = []
    for _ in range(count):
        _, score, _, (x, y) = cv2.minMaxLoc(working)
        if not math.isfinite(score):
            break
        peaks.append({"top_left": [x, y], "pixel_xy": [round(x + width / 2), round(y + height / 2)],
                      "score": score})
        working[(xx - x) ** 2 + (yy - y) ** 2 <= radius ** 2] = -np.inf
    return peaks


@dataclass(frozen=True)
class MatcherCalibration:
    reference_pixel_sha256: str
    mask_pixel_sha256: str
    minimap_size: tuple[int, int]
    state_id: int
    floor_id: str
    score_threshold: float
    distinct_radius: float
    min_margin: float
    min_inliers: int
    min_coverage: float
    max_geometry_error: float

    def __post_init__(self):
        numeric = (self.score_threshold, self.distinct_radius, self.min_margin,
                   self.min_coverage, self.max_geometry_error)
        if (not all(math.isfinite(v) for v in numeric) or not 0.7 <= self.score_threshold <= 1
                or self.distinct_radius <= 0 or not 0 < self.min_margin <= 2
                or type(self.min_inliers) is not int or self.min_inliers < 3
                or type(self.state_id) is not int or self.state_id <= 0 or not isinstance(self.floor_id, str)
                or not 0 < self.min_coverage <= 1 or self.max_geometry_error <= 0
                or len(self.minimap_size) != 2 or any(type(v) is not int or v <= 0 for v in self.minimap_size)
                or not all(len(value) == 64 and all(c in "0123456789abcdef" for c in value)
                           for value in (self.reference_pixel_sha256, self.mask_pixel_sha256))):
            raise ValueError("Invalid offline matcher calibration")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or data.get("scope") != "localization_only":
            raise ValueError("Only localization-only matcher calibration is supported")
        values = dict(data["policy"])
        values["minimap_size"] = tuple(values["minimap_size"])
        return cls(**values)

    def evaluate(self, evidence):
        reasons = []
        if evidence.pixel_xy is None or evidence.confidence is None or not math.isfinite(evidence.confidence):
            reasons.append("no_candidate")
        elif evidence.confidence < self.score_threshold:
            reasons.append("gradient_score")
        if evidence.margin is None or not math.isfinite(evidence.margin) or evidence.margin < self.min_margin:
            reasons.append("ambiguous_peak")
        if evidence.feature_inliers < self.min_inliers:
            reasons.append("feature_support")
        if (evidence.feature_pixel_xy is None
                or not all(math.isfinite(value) for value in evidence.feature_pixel_xy)):
            reasons.append("no_feature_position")
        if not math.isfinite(evidence.feature_coverage) or evidence.feature_coverage < self.min_coverage:
            reasons.append("feature_coverage")
        if (evidence.geometry_error is None or not math.isfinite(evidence.geometry_error)
                or evidence.geometry_error > self.max_geometry_error):
            reasons.append("feature_geometry")
        if (evidence.agreement_error is None or not math.isfinite(evidence.agreement_error)
                or evidence.agreement_error > self.max_geometry_error):
            reasons.append("signals_disagree")
        return replace(evidence, accepted=not reasons, reason=",".join(reasons) if reasons else "corroborated")


class HybridMapMatcher:
    def __init__(self, reference, calibration):
        if (reference.ndim != 3 or reference.shape[2] != 3 or reference.dtype != np.uint8
                or pixel_hash(reference) != calibration.reference_pixel_sha256):
            raise ValueError("Matcher calibration does not belong to this reference")
        self.reference = reference
        self.calibration = calibration
        self.reference_gradients = gradients(reference)
        self.sift = cv2.SIFT_create()
        self.reference_keypoints, self.reference_descriptors = self.sift.detectAndCompute(
            cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), None)

    def feature_translation(self, mini, mask):
        """SIFT descriptor matching followed by translation-only consensus.

        No expected player position, gradient result, rotation or zoom adjustment
        enters this estimate. Duplicate orientations and shared target keypoints
        cannot inflate the unique support count.
        """
        keypoints, descriptors = self.sift.detectAndCompute(cv2.cvtColor(mini, cv2.COLOR_BGR2GRAY), mask)
        if descriptors is None or self.reference_descriptors is None or len(self.reference_descriptors) < 2:
            return {}
        matches = [a for a, b in cv2.BFMatcher().knnMatch(descriptors, self.reference_descriptors, k=2)
                   if a.distance < 0.7 * b.distance]
        pairs, seen_source, seen_target = [], set(), set()
        for match in sorted(matches, key=lambda value: value.distance):
            source = tuple(keypoints[match.queryIdx].pt)
            target = tuple(self.reference_keypoints[match.trainIdx].pt)
            if source not in seen_source and target not in seen_target:
                pairs.append((source, target))
                seen_source.add(source)
                seen_target.add(target)
        if len(pairs) < 3:
            return {"feature_matches": len(pairs)}
        source, target = np.asarray(pairs).transpose(1, 0, 2)
        shifts = target - source
        # Deterministic maximal translation consensus, then a median refinement.
        distances = np.linalg.norm(shifts[:, None] - shifts[None, :], axis=2)
        support = distances <= self.calibration.max_geometry_error
        inside = support[np.argmax(support.sum(axis=1))]
        shift = np.median(shifts[inside], axis=0)
        inside = np.linalg.norm(shifts - shift, axis=1) <= self.calibration.max_geometry_error
        shift = np.median(shifts[inside], axis=0)
        residual = np.linalg.norm(shifts[inside] - shift, axis=1)
        hull = cv2.convexHull(source[inside].astype(np.float32))
        height, width = mini.shape[:2]
        return {"feature_matches": len(pairs), "feature_inliers": int(inside.sum()),
                "feature_pixel_xy": tuple(shift + [width / 2, height / 2]),
                "feature_coverage": float(cv2.contourArea(hull) / (width * height)),
                "geometry_error": float(max(residual))}

    def measure(self, mini, mask):
        """Return raw evidence and the score surface; never accept by expectation."""
        if (mini.ndim != 3 or mini.shape[2] != 3 or mini.dtype != np.uint8
                or mini.shape[1::-1] != self.calibration.minimap_size
                or mask.shape != mini.shape[:2] or mask.dtype != np.uint8
                or pixel_hash(mask) != self.calibration.mask_pixel_sha256
                or mini.shape[0] > self.reference.shape[0] or mini.shape[1] > self.reference.shape[1]):
            return LocalizationEvidence(None, None, "gradient_sift", reason="shape_or_mask"), None
        scores = correlation(self.reference_gradients, gradients(mini), mask)
        peaks = distinct_peaks(scores, self.calibration.minimap_size, self.calibration.distinct_radius, 2)
        if len(peaks) < 2:
            return LocalizationEvidence(None, None, "gradient_sift", reason="no_distinct_comparison"), scores
        best, second = peaks
        feature = self.feature_translation(mini, mask)
        agreement = (float(np.linalg.norm(np.asarray(feature["feature_pixel_xy"]) - best["pixel_xy"]))
                     if feature.get("feature_pixel_xy") else None)
        evidence = LocalizationEvidence(tuple(best["pixel_xy"]), best["score"], "gradient_sift",
                                        second_best_score=second["score"], margin=best["score"] - second["score"],
                                        agreement_error=agreement, **feature)
        return evidence, scores

    def match(self, mini, mask):
        evidence, _ = self.measure(mini, mask)
        return self.calibration.evaluate(evidence)
