"""Closed-dataset Phase 4.5A experiment; no live capture or game task startup."""

from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_surface_test_a import read_image, sha256
from src.overworld.models import MapCoordinate
from src.overworld.navigation.image_matcher import (
    HybridMapMatcher, MatcherCalibration, correlation, distinct_peaks, pixel_hash,
)
from src.overworld.navigation.player_locator import PlayerLocator, SurfaceProfile
from src.task.FarmMapTask import create_circle_mask_with_hole


def save_png(path, image):
    success, png = cv2.imencode(".png", image)
    assert success
    path.write_bytes(png.tobytes())


def distribution(values):
    values = np.asarray(values)
    return {"count": int(values.size), "min": float(values.min()), "median": float(np.median(values)),
            "p95": float(np.quantile(values, .95)), "p99": float(np.quantile(values, .99)), "max": float(values.max())}


def main():
    folder = ROOT / "assets/overworld/calibration/surface-test-01"
    output = folder / "matcher_diagnosis"
    output.mkdir(exist_ok=True)
    prior = json.loads((folder / "analysis/test_a_results.json").read_text(encoding="utf-8"))
    for name, digest in prior["inputs_sha256"].items():
        assert sha256(folder / name) == digest, name
    reference_path = folder / "analysis/reference_candidate.png"
    assert sha256(reference_path) == prior["reference_sha256"]
    reference = read_image(reference_path)
    x, y, width, height = prior["minimap_box_xywh"]
    minis = [read_image(folder / f"stationary_{index:03d}.png")[y:y + height, x:x + width] for index in range(1, 11)]
    mask = create_circle_mask_with_hole(minis[0])
    derivation = prior["reference_derivation"]
    # Prior, withheld terrain fit error plus integer-grid half-diagonal. Not
    # adjusted to the new matcher outputs, and not a world accuracy guarantee.
    geometric_limit = (derivation["terrain_held_out_residual_max_full_map_pixels"] /
                       derivation["image_scale_full_map_pixels_per_minimap_pixel"] + math.sqrt(2) / 2)
    # These minimal structural values only permit raw measurements; they are
    # never used to accept a positive. Final gates are learned below and frozen.
    measuring = MatcherCalibration(pixel_hash(reference), pixel_hash(mask), (width, height), 906, "",
                                   .7, 8, np.finfo(float).eps, 3, np.finfo(float).eps, geometric_limit)
    matcher = HybridMapMatcher(reference, measuring)
    rows, negative_controls = [], []
    for index, mini in enumerate(minis):
        evidence, gradient_scores = matcher.measure(mini, mask)
        color_scores = correlation(reference, mini, mask, cv2.TM_CCOEFF_NORMED)
        color_peaks = distinct_peaks(color_scores, (width, height), measuring.distinct_radius)
        gradient_peaks = distinct_peaks(gradient_scores, (width, height), measuring.distinct_radius)
        left, top = gradient_peaks[0]["top_left"]
        yy, xx = np.indices(gradient_scores.shape)
        wrong = (xx - left) ** 2 + (yy - top) ** 2 > measuring.distinct_radius ** 2
        immediate = gradient_scores.copy()
        immediate[top, left] = -np.inf
        row = {"frame": index + 1, "partition": "train" if index < 5 else "held_out",
               "color_top5": color_peaks, "gradient_top5": gradient_peaks,
               "color_margin": color_peaks[0]["score"] - color_peaks[1]["score"],
               "gradient_immediate_runner_up": float(immediate.max()),
               "color_spatial_negative_scores": distribution(color_scores[wrong]),
               "gradient_spatial_negative_scores": distribution(gradient_scores[wrong]),
               "spatial_negative_count_above_0700": int((gradient_scores[wrong] >= .7).sum()),
               "raw_evidence": asdict(evidence)}
        rows.append(row)
        if index == 0:
            save_png(output / "raw_minimap.png", mini)
            save_png(output / "mask.png", mask)
            save_png(output / "masked_minimap.png", cv2.bitwise_and(mini, mini, mask=mask))
            candidate_crop = reference[top:top + height, left:left + width]
            save_png(output / "candidate_reference_crop.png", candidate_crop)
            save_png(output / "masked_difference.png", cv2.bitwise_and(cv2.absdiff(mini, candidate_crop),
                                                                       cv2.absdiff(mini, candidate_crop), mask=mask))
            for name, surface, peaks in (("color", color_scores, color_peaks), ("gradient", gradient_scores, gradient_peaks)):
                np.save(output / f"{name}_scores.npy", surface)
                # Heatmap is explicitly a normalized visualization, not raw evidence.
                rendered = cv2.applyColorMap(cv2.normalize(surface, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8), cv2.COLORMAP_TURBO)
                save_png(output / f"{name}_heatmap.png", rendered)
                annotated = reference.copy()
                for rank, peak in enumerate(peaks, 1):
                    a, b = peak["top_left"]
                    cv2.rectangle(annotated, (a, b), (a + width, b + height), (0, 255, 255), 1)
                    cv2.putText(annotated, f"{rank}: {peak['score']:.4f}", (a, max(12, b)), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                save_png(output / f"{name}_top5.png", annotated)
            # Fixed-pose diagnostic ablations only. These masks are NOT adopted.
            yy2, xx2 = np.indices(mask.shape)
            radius = np.hypot(xx2 - width // 2, yy2 - height // 2)
            regions = {"whole_runtime_mask": mask, "inner_three_quarters_radius": np.where(radius < min(width, height) * .375, mask, 0).astype(np.uint8),
                       "outer_quarter_radius": np.where(radius >= min(width, height) * .375, mask, 0).astype(np.uint8)}
            for name, region in regions.items():
                row.setdefault("appearance_ablation", {})[name] = float(correlation(candidate_crop, mini, region, cv2.TM_CCOEFF_NORMED)[0, 0])
            low_mini = cv2.GaussianBlur(mini.astype(np.float32), (0, 0), 8)
            low_ref = cv2.GaussianBlur(reference.astype(np.float32), (0, 0), 8)
            high_score = correlation(reference.astype(np.float32) - low_ref, mini.astype(np.float32) - low_mini, mask, cv2.TM_CCOEFF_NORMED)
            row["appearance_ablation"]["highpass_sigma8_fixed_pose"] = float(high_score[top, left])
            yellow = cv2.inRange(cv2.cvtColor(mini, cv2.COLOR_BGR2HSV), np.array([15, 100, 190]), np.array([40, 255, 255]))
            row["appearance_ablation"]["yellow_arrow_pixels_remaining_in_mask"] = int(np.count_nonzero((yellow > 0) & (mask > 0)))
            row["offset_controls"] = [{"dx": dx, "dy": dy, "color_score": float(color_scores[top + dy, left + dx]),
                                       "gradient_score": float(gradient_scores[top + dy, left + dx])}
                                      for d in (1, 2, 4, 8, 16, 32) for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d))]

        # Unsupported rotations, held-out angles separate from fitting angles.
        angles = (10, 45, 90, 180) if index < 5 else (-10, -45, -90, 135, 2, -2)
        for angle in angles:
            rotation = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1)
            rotated = cv2.warpAffine(mini, rotation, (width, height), flags=cv2.INTER_LINEAR)
            negative, _ = matcher.measure(rotated, mask)
            negative_color = distinct_peaks(correlation(reference, rotated, mask, cv2.TM_CCOEFF_NORMED),
                                            (width, height), measuring.distinct_radius, 2)
            negative_controls.append({"name": f"frame_{index + 1}_rotation_{angle}", "partition": row["partition"],
                                      "color_best_score": negative_color[0]["score"],
                                      "evidence": asdict(negative)})
        # Reference galleries with the correct terrain entirely absent. Left is
        # a training negative; the disjoint right gallery is validation-only.
        wrong_reference = reference[:, :355] if index < 5 else reference[:, 603:]
        wrong_matcher = HybridMapMatcher(wrong_reference, replace(measuring, reference_pixel_sha256=pixel_hash(wrong_reference)))
        negative, _ = wrong_matcher.measure(mini, mask)
        negative_color = distinct_peaks(correlation(wrong_reference, mini, mask, cv2.TM_CCOEFF_NORMED),
                                        (width, height), measuring.distinct_radius, 2)
        negative_controls.append({"name": f"frame_{index + 1}_wrong_gallery", "partition": row["partition"],
                                  "color_best_score": negative_color[0]["score"],
                                  "evidence": asdict(negative)})

    positives = [row["raw_evidence"] for row in rows[:5]]
    negatives = [control["evidence"] for control in negative_controls if control["partition"] == "train"]
    # Freeze disjoint-control mid-gap thresholds before evaluating frames 6–10.
    def separation(field):
        positive_min = min(p[field] or 0 for p in positives)
        negative_max = max(n[field] or 0 for n in negatives)
        if positive_min <= negative_max:
            raise RuntimeError(f"No training separation for {field}; do not enable this method")
        return positive_min, negative_max, (positive_min + negative_max) / 2

    margin_fit = separation("margin")
    support_fit = separation("feature_inliers")
    # Hull coverage is a structural non-collinearity check, not a learned region
    # classifier: require a hull larger than one pixel (three distinct points).
    # Support + agreement + score supply the empirical discrimination gates.
    policy = replace(measuring, min_margin=margin_fit[2], min_inliers=math.ceil(support_fit[2]),
                     min_coverage=1 / (width * height))
    calibration_data = {"schema_version": 1, "scope": "localization_only", "policy": asdict(policy),
                        "training": {"positive_frames": [1, 2, 3, 4, 5], "validation_frames": [6, 7, 8, 9, 10],
                                     "margin_positive_min_negative_max_midpoint": margin_fit,
                                     "support_positive_min_negative_max_midpoint": support_fit,
                                     "geometry_error_limit_derivation": "Prior held-out terrain residual / measured map-to-minimap scale + sqrt(2)/2 reference-pixel quantization",
                                     "score_threshold": "Retain 0.700; check both positive and negative distributions, do not lower it",
                                     "distinct_radius": "Existing 8-reference-pixel arrival scale, grouping adjacent samples of one peak; immediate runner-up also recorded",
                                     "limitations": "One stationary pose, correlated frames; geometry used frame 001. Not independent region generalization or live certification."}}
    (output / "matcher_calibration.json").write_text(json.dumps(calibration_data, indent=2) + "\n", encoding="utf-8")
    # Exercise the real loader and PlayerLocator, not a separate report-only gate.
    policy = MatcherCalibration.load(output / "matcher_calibration.json")
    matcher = HybridMapMatcher(reference, policy)
    profile = SurfaceProfile(reference_path, ROOT.parent / "wuwa-map/map_items.db", "", 906, "",
                             MapCoordinate(*derivation["world_origin"]), derivation["world_units_per_reference_pixel"],
                             (2560, 1440), frozenset())
    accepted_positions = []
    for row, mini in zip(rows, minis):
        locator = PlayerLocator(profile, match_player=lambda: matcher.match(mini, mask), facing=lambda: None,
                                image_size=reference.shape[1::-1])
        position = locator.locate()
        row["final_evidence"] = asdict(locator.last_evidence)
        row["accepted_xy"] = [position.coordinate.x, position.coordinate.y] if position else None
        row["state_id"], row["floor_id"] = 906, ""
        if position:
            accepted_positions.append(row["accepted_xy"])
    from src.overworld.navigation.player_locator import LocalizationEvidence
    for control in negative_controls:
        decision = policy.evaluate(LocalizationEvidence(**control["evidence"]))
        control["accepted"] = decision.accepted
        control["rejection_reason"] = decision.reason
    def sift_gate(e):
        return (e["feature_pixel_xy"] is not None and e["feature_inliers"] >= policy.min_inliers
                and e["geometry_error"] is not None and e["geometry_error"] <= policy.max_geometry_error
                and e["feature_coverage"] >= policy.min_coverage)

    comparison = {
        "A_masked_color": {"positive_accepts": sum(r["color_top5"][0]["score"] >= .7 for r in rows),
                           "negative_accepts": sum(n["color_best_score"] >= .7 for n in negative_controls)},
        "B_signed_gradients": {"positive_accepts": sum(r["raw_evidence"]["confidence"] >= .7 for r in rows),
                               "negative_accepts": sum((n["evidence"]["confidence"] or 0) >= .7 for n in negative_controls)},
        "C_SIFT_translation_support": {"positive_accepts": sum(sift_gate(r["raw_evidence"]) for r in rows),
                                       "negative_accepts": sum(sift_gate(n["evidence"]) for n in negative_controls)},
        "D_hybrid": {"positive_accepts": sum(r["final_evidence"]["accepted"] for r in rows),
                     "negative_accepts": sum(n["accepted"] for n in negative_controls)},
    }
    positions = np.array(accepted_positions)
    centered = positions - positions[0] if len(positions) else positions
    feature_pixels = np.array([row["final_evidence"]["feature_pixel_xy"] for row in rows])
    feature_spread = float(np.linalg.norm(feature_pixels[:, None] - feature_pixels[None, :], axis=2).max())
    # Recheck original coordinate correspondences rather than change the geometry.
    world_scale = derivation["world_units_per_full_map_pixel"]
    image_scale = derivation["image_scale_full_map_pixels_per_minimap_pixel"]
    origin = np.array(derivation["world_origin"])
    landmark_pixels = np.array([p["full_map_pixel_xy"] for p in prior["landmarks"]])
    landmark_world = np.array([[p["x"], p["y"]] for p in prior["landmarks"]])
    map_ref = landmark_pixels / image_scale
    reconstructed = origin + map_ref * derivation["world_units_per_reference_pixel"]
    assert np.allclose(reconstructed, origin + landmark_pixels * world_scale)
    geometry = {"axis_mapping": "Kuro x increases with image x; Kuro y increases with image y; no swapping/reflection",
                "rotation_degrees_measured_previously": derivation["similarity_rotation_degrees_diagnostic_only"],
                "residuals_kuro_units": np.linalg.norm(reconstructed - landmark_world, axis=1).tolist(),
                "residuals_reference_pixels": (np.linalg.norm(reconstructed - landmark_world, axis=1) /
                                                derivation["world_units_per_reference_pixel"]).tolist(),
                "no_geometry_modified": True}
    report = {"dataset": "Closed offline surface-test-01; current live position unknown and unused",
              "input_hashes": prior["inputs_sha256"], "reference_sha256": prior["reference_sha256"],
              "opencv_version": cv2.__version__, "geometry_preserved": derivation,
              "geometry_recheck": geometry, "method_comparison": comparison,
              "landmark_errors_full_map_pixels": prior["landmark_residuals_full_map_pixels"],
              "rows": rows, "negative_controls": negative_controls,
              "calibration": calibration_data,
              "summary": {"accepted_frames": len(positions), "negative_controls": len(negative_controls),
                          "false_acceptances": sum(n["accepted"] for n in negative_controls),
                          "gradient_candidate_mean_xy": positions.mean(axis=0).tolist() if len(positions) else None,
                          "gradient_candidate_variance_xy": centered.var(axis=0, ddof=1).tolist() if len(positions) > 1 else None,
                          "feature_subpixel_pairwise_spread_reference_pixels": feature_spread,
                          "position_arrow_comparison_reference_pixels": prior["independent_position_comparison"]["candidate_distance_reference_pixels"],
                          "test_b_authorized": False, "live_validated": False}}
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"calibration": calibration_data, "summary": report["summary"],
                      "ablation": rows[0]["appearance_ablation"],
                      "rows": [{"frame": row["frame"], "xy": row["accepted_xy"], **row["final_evidence"]} for row in rows]}, indent=2))


if __name__ == "__main__":
    main()
