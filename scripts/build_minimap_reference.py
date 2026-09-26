"""Offline local reference from terrain-registered minimap tiles, no game input.

The full-map reference supplies absolute coordinates. Each tile is independently
registered to that original reference, never to a previously added tile. Player
arrows and circular rims are excluded. Review flags are deliberately not copied.
"""

from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.analyze_surface_test_a import read_image, sha256
from src.overworld.navigation.image_matcher import MatcherCalibration, HybridMapMatcher, pixel_hash
from src.task.FarmMapTask import create_circle_mask_with_hole


def main(base, captures, output):
    if output.exists():
        raise ValueError("Choose a new output directory; existing calibration is immutable")
    reference = read_image(base / "reference.png")
    original = MatcherCalibration.load(base / "matcher_calibration.json")
    registrar = HybridMapMatcher(reference, original)
    mosaic = reference.copy()
    inputs, tiles, samples = {}, [], []
    mask = None
    for folder in captures:
        paths = sorted(folder.glob("stationary_*.png"))
        assert len(paths) == 10
        minis = [read_image(p)[38:285, 48:296] for p in paths]
        samples.extend(zip(paths, minis))
        inputs.update({str(p.relative_to(ROOT)): sha256(p) for p in paths})
        mask = create_circle_mask_with_hole(minis[0])
        geometry = registrar.feature_translation(minis[0], mask)
        if (geometry.get("feature_inliers", 0) < original.min_inliers
                or geometry.get("feature_coverage", 0) < original.min_coverage
                or geometry.get("geometry_error", float("inf")) > original.max_geometry_error):
            raise ValueError(f"Tile lacks independent geometry: {folder}")
        shift = np.asarray(geometry["feature_pixel_xy"]) - [124, 123.5]
        transform = np.float64([[1, 0, shift[0]], [0, 1, shift[1]]])
        size = reference.shape[1::-1]
        tile = cv2.warpAffine(minis[0], transform, size, flags=cv2.INTER_LINEAR)
        safe_mask = cv2.erode(mask, np.ones((5, 5), np.uint8))
        coverage = cv2.warpAffine(safe_mask, transform, size, flags=cv2.INTER_LINEAR) == 255
        mosaic[coverage] = tile[coverage]
        tiles.append({"source": str(paths[0].relative_to(ROOT)), "registration": geometry,
                      "reference_translation": shift.tolist(), "pixels_written": int(coverage.sum())})
    policy = replace(original, reference_pixel_sha256=pixel_hash(mosaic))
    matcher = HybridMapMatcher(mosaic, policy)
    duplicate = np.concatenate((mosaic, mosaic), axis=1)
    repeated = HybridMapMatcher(duplicate, replace(policy, reference_pixel_sha256=pixel_hash(duplicate)))
    absent = mosaic[:, 650:]
    wrong = HybridMapMatcher(absent, replace(policy, reference_pixel_sha256=pixel_hash(absent)))
    rows = []

    def measure(name, kind, mini, active=matcher):
        evidence, surface = active.measure(mini, mask)
        row = {"name": name, "kind": kind, **asdict(active.calibration.evaluate(evidence))}
        if kind == "positive" and surface is not None:
            y, x = np.unravel_index(np.argmax(surface), surface.shape)
            yy, xx = np.indices(surface.shape)
            distant = (yy - y) ** 2 + (xx - x) ** 2 > policy.distinct_radius ** 2
            row["distant_locations_above_threshold"] = int(np.count_nonzero(surface[distant] >= policy.score_threshold))
        rows.append(row)
        return row

    for path, mini in samples:
        name = str(path.relative_to(ROOT))
        positive = measure(name, "positive", mini)
        for angle in (2, -2, 10, 90, 180):
            rotated = cv2.warpAffine(mini, cv2.getRotationMatrix2D((124, 123.5), angle, 1), (248, 247))
            measure(name + f"_rotation_{angle}", "negative", rotated)
        measure(name + "_blank", "negative", np.zeros_like(mini))
        measure(name + "_absent", "negative", mini, wrong)
        measure(name + "_duplicate", "negative", mini, repeated)
        feature = {k: positive[k] for k in ("feature_pixel_xy", "feature_matches", "feature_inliers", "feature_coverage", "geometry_error")}
        with patch.object(repeated, "feature_translation", return_value=feature):
            measure(name + "_duplicate_strong_sift", "negative", mini, repeated)
        print(path.name, positive["confidence"], positive["accepted"], flush=True)
    positive = [r for r in rows if r["kind"] == "positive"]
    negative = [r for r in rows if r["kind"] == "negative"]
    clean = (all(r["accepted"] and r["distant_locations_above_threshold"] == 0 for r in positive)
             and not any(r["accepted"] for r in negative))
    report = {"offline_clean": clean, "inputs_sha256": inputs,
              "base_reference_sha256": sha256(base / "reference.png"), "tiles": tiles,
              "policy": asdict(policy), "rows": rows,
              "limitations": "Tile frame 1 participates in construction; subsequent stationary frames are correlated. Requires fresh live localization and navigation review."}
    output.mkdir(parents=True)
    cv2.imwrite(str(output / "reference.png"), mosaic)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if clean:
        (output / "matcher_calibration.json").write_text(json.dumps({
            "schema_version": 1, "scope": "localization_only", "policy": asdict(policy),
            "validation": {"evidence": "report.json", "thresholds": "Unchanged from base calibration"},
        }, indent=2), encoding="utf-8")
        profile = json.loads((base / "profile.json").read_text(encoding="utf-8"))
        profile.update(localization_verified=False, navigation_verified=False, test_walk_target=None)
        profile.pop("localization_evidence", None)
        profile.pop("navigation_evidence", None)
        (output / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"clean": clean, "positive_count": len(positive), "positive_accepted": sum(r["accepted"] for r in positive),
                      "negative_count": len(negative), "negative_accepted": sum(r["accepted"] for r in negative)}))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), [Path(p).resolve() for p in sys.argv[3:]], Path(sys.argv[2]).resolve())
