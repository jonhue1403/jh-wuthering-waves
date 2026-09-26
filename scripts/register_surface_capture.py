"""Offline registration of an overlapping map capture; never sends game input.

Retains the existing matcher acceptance limits. A successful replay is evidence
for live localization review, not permission to enable movement review flags.
"""

from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.analyze_surface_test_a import read_image, sha256, fit_scale_offset
from src.overworld.navigation.image_matcher import HybridMapMatcher, MatcherCalibration, pixel_hash
from src.task.FarmMapTask import create_circle_mask_with_hole


def register(source, target, source_mask=None, target_mask=None, limit=3):
    sift = cv2.SIFT_create()
    ka, da = sift.detectAndCompute(cv2.cvtColor(source, cv2.COLOR_BGR2GRAY), source_mask)
    kb, db = sift.detectAndCompute(cv2.cvtColor(target, cv2.COLOR_BGR2GRAY), target_mask)
    if da is None or db is None or len(db) < 2:
        raise ValueError("Insufficient terrain descriptors")
    candidates = [a for a, b in cv2.BFMatcher().knnMatch(da, db, k=2) if a.distance < .7 * b.distance]
    pairs, used_a, used_b = [], set(), set()
    for match in sorted(candidates, key=lambda m: m.distance):
        a, b = ka[match.queryIdx].pt, kb[match.trainIdx].pt
        if a not in used_a and b not in used_b:
            pairs.append((a, b))
            used_a.add(a)
            used_b.add(b)
    pairs.sort()
    if len(pairs) < 9:
        raise ValueError("Insufficient independent terrain matches")
    a, b = np.asarray(pairs).transpose(1, 0, 2)
    # Split before robust fitting; held-out matches never select the transform.
    held = np.arange(len(a)) % 3 == 0
    cv2.setRNGSeed(0)
    affine, inside = cv2.estimateAffinePartial2D(a[~held], b[~held], method=cv2.RANSAC,
                                              ransacReprojThreshold=limit, maxIters=10000)
    if affine is None or inside.sum() < 4:
        raise ValueError("Insufficient training consensus")
    inside = inside.ravel().astype(bool)
    scale, offset = fit_scale_offset(a[~held][inside], b[~held][inside])
    error = np.linalg.norm(a * scale + offset - b, axis=1)
    # Descriptor mismatches are reported too; require held-out geometric support.
    supported = held & (error <= limit)
    if scale <= 0 or supported.sum() < 3 or max(error[~held][inside]) > limit:
        raise ValueError("Uniform north-up registration failed")
    return scale, offset, {
        "scale": scale, "offset": offset.tolist(), "limit_pixels": limit,
        "unique_pairs": len(pairs), "training_inliers": int(inside.sum()),
        "held_out_total": int(held.sum()), "held_out_support": int(supported.sum()),
        "held_out_supported_max_error": float(max(error[supported])),
        "rotation_degrees": math.degrees(math.atan2(affine[1, 0], affine[0, 0])),
        "pairs": [{"source": x.tolist(), "target": y.tolist(), "held_out": bool(h),
                   "error": float(e)} for x, y, h, e in zip(a, b, held, error)],
    }


def main(capture, validation_captures=()):
    old = ROOT / "assets/overworld/calibration/surface-test-01"
    prior = json.loads((old / "analysis/test_a_results.json").read_text(encoding="utf-8"))
    old_path, new_path = old / "full_map_position.png", capture / "full_map_position.png"
    assert sha256(old_path) == prior["inputs_sha256"][old_path.name]
    previous, full = read_image(old_path), read_image(new_path)
    map_mask = np.zeros(full.shape[:2], np.uint8)
    map_mask[220:1220, 100:2300] = 255
    scale, offset, registration = register(previous, full, map_mask, map_mask, 2)
    paths = sorted(capture.glob("stationary_*.png"))
    assert len(paths) == 10
    for directory in validation_captures:
        extra = sorted(directory.glob("stationary_*.png"))
        assert len(extra) == 10
        paths.extend(extra)
    minis = [read_image(p)[38:285, 48:296] for p in paths]
    mask = create_circle_mask_with_hole(minis[0])
    image_scale, _, mini_registration = register(minis[0], full, mask, map_mask)
    size = tuple(math.ceil(n / image_scale) for n in full.shape[1::-1])
    reference = cv2.warpAffine(full, np.float64([[1 / image_scale, 0, 0], [0, 1 / image_scale, 0]]),
                               size, flags=cv2.INTER_LINEAR)
    output = capture / "dense-bounded-gradient"
    output.mkdir(exist_ok=True)
    cv2.imwrite(str(output / "reference.png"), reference)
    previous_geometry = prior["reference_derivation"]
    world_scale = previous_geometry["world_units_per_full_map_pixel"] / scale
    origin = np.array(previous_geometry["world_origin"]) - world_scale * offset
    frozen = MatcherCalibration.load(ROOT / "assets/overworld/calibration/subpixel-validation/matcher_calibration.json")
    policy = replace(frozen, reference_pixel_sha256=pixel_hash(reference), mask_pixel_sha256=pixel_hash(mask),
                     gradient_mode="bounded64", feature_mode="dense", min_coverage=.1)
    matcher = HybridMapMatcher(reference, policy)
    rows = []

    def measure(name, kind, mini, active=matcher):
        evidence, _ = active.measure(mini, mask)
        row = {"name": name, "kind": kind, **asdict(active.calibration.evaluate(evidence))}
        rows.append(row)
        return row

    for index, mini in enumerate(minis):
        positive = measure(str(paths[index].relative_to(ROOT)), "positive", mini)
        for angle in (2, -2, 10, 90, 180):
            rotated = cv2.warpAffine(mini, cv2.getRotationMatrix2D((124, 123.5), angle, 1), (248, 247))
            measure(f"{index}_rotate_{angle}", "negative", rotated)
        measure(f"{index}_blank", "negative", np.zeros_like(mini))
        # Rightmost terrain does not include the centered player footprint.
        wrong = reference[:, 650:]
        absent = HybridMapMatcher(wrong, replace(policy, reference_pixel_sha256=pixel_hash(wrong)))
        measure(f"{index}_absent", "negative", mini, absent)
        duplicate = np.concatenate((reference, reference), axis=1)
        repeated = HybridMapMatcher(duplicate, replace(policy, reference_pixel_sha256=pixel_hash(duplicate)))
        measure(f"{index}_duplicate", "negative", mini, repeated)
        feature = {key: positive[key] for key in ("feature_pixel_xy", "feature_matches", "feature_inliers",
                                                  "feature_coverage", "geometry_error")}
        with patch.object(repeated, "feature_translation", return_value=feature):
            measure(f"{index}_duplicate_strong_sift", "negative", mini, repeated)
    positives = [r for r in rows if r["kind"] == "positive"]
    negatives = [r for r in rows if r["kind"] == "negative"]
    clean = all(r["accepted"] for r in positives) and not any(r["accepted"] for r in negatives)
    report = {"offline_clean": clean, "registration": registration, "minimap_geometry": mini_registration,
              "world_origin": origin.tolist(), "units_per_pixel": world_scale * image_scale,
              "inputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [old_path, new_path, *paths]},
              "policy": asdict(policy), "rows": rows,
              "development": "Magnitude caps 32, 64, 128 explored on first pose frame 1; cap 64 frozen. Dense SIFT (5 octave layers, contrast .02) evaluated at poses 1 and 2; coverage gate strengthened to .1. Fresh live validation still required.",
              "limitations": "Correlated frames per pose; no completed live walk, layer detector, or combat verification."}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if clean:
        (output / "matcher_calibration.json").write_text(json.dumps({
            "schema_version": 1, "scope": "localization_only", "policy": asdict(policy),
            "validation": {"evidence": "report.json", "thresholds": "Unchanged prior conservative limits"},
        }, indent=2), encoding="utf-8")
    print(json.dumps({"clean": clean, "origin": origin.tolist(), "units_per_pixel": report["units_per_pixel"],
                      "positive": positives, "negative_accepted": sum(r["accepted"] for r in negatives)}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), [Path(p).resolve() for p in sys.argv[2:]])
