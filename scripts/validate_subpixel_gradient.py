"""Phase 4.5B offline replay. Never starts capture, a task, or game inputs."""

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
from scripts.diagnose_surface_matcher import distribution
from src.overworld.navigation.image_matcher import HybridMapMatcher, MatcherCalibration, pixel_hash
from src.overworld.navigation.player_locator import LocalizationEvidence
from src.task.FarmMapTask import create_circle_mask_with_hole

OUTPUT = ROOT / "assets/overworld/calibration/subpixel-validation"


def main(output=OUTPUT):
    folder = ROOT / "assets/overworld/calibration/surface-test-01"
    prior = json.loads((folder / "analysis/test_a_results.json").read_text(encoding="utf-8"))
    fresh = ROOT / "assets/overworld/calibration/surface-test-02"
    replay = json.loads((fresh / "analysis/frozen_replay.json").read_text(encoding="utf-8"))
    inputs = {}
    for name, digest in prior["inputs_sha256"].items():
        assert sha256(folder / name) == digest, name
        inputs[str((folder / name).relative_to(ROOT))] = digest
    for row in replay["frames"]:
        assert sha256(fresh / row["filename"]) == row["sha256"]
        inputs[str((fresh / row["filename"]).relative_to(ROOT))] = row["sha256"]
    reference = read_image(folder / "analysis/reference_candidate.png")
    assert sha256(folder / "analysis/reference_candidate.png") == prior["reference_sha256"]
    policy = MatcherCalibration.load(folder / "matcher_diagnosis/matcher_calibration.json")
    matcher = HybridMapMatcher(reference, policy)
    x, y, width, height = prior["minimap_box_xywh"]
    rows, offsets = [], []
    phase_matchers = {}

    def measure(name, partition, kind, mini, active=matcher):
        mask = create_circle_mask_with_hole(mini)
        integer, old_scores = active.measure(mini, mask)
        key = active.calibration.reference_pixel_sha256
        if key not in phase_matchers:
            phase_matchers[key] = HybridMapMatcher(active.reference, replace(active.calibration, sampling_mode="sift_phase"))
        refined, scores = phase_matchers[key].measure(mini, mask)
        row = {"name": name, "partition": partition, "kind": kind,
               "integer": asdict(active.calibration.evaluate(integer)), "subpixel": asdict(refined)}
        rows.append(row)
        if kind == "positive":
            # All distant wrong locations; use the integer coarse candidate as
            # the exclusion center, not whichever refined candidate wins.
            top, left = np.unravel_index(np.argmax(old_scores), old_scores.shape)
            center = np.array([left, top])
            phase = np.rint(((np.asarray(integer.feature_pixel_xy) - [width / 2, height / 2]) % 1) * 32) / 32
            for label, surface, delta in (("integer", old_scores, np.zeros(2)),
                                           ("subpixel", scores, phase)):
                yy, xx = np.indices(surface.shape)
                wrong = (xx + delta[0] - center[0]) ** 2 + (yy + delta[1] - center[1]) ** 2 > policy.distinct_radius ** 2
                row[label + "_spatial_wrong_scores"] = distribution(surface[wrong])
                row[label + "_spatial_wrong_above_0700"] = int((surface[wrong] >= .7).sum())
            # Reproduce original nearby offset controls, now for every frame.
            # Adjacent offsets can land on the true subpixel peak; they are
            # uncertainty probes, not distinct wrong-location trials.
            left, top = np.rint(center).astype(int)
            yy, xx = np.indices(scores.shape)
            for d in (1, 2, 4, 8, 16, 32):
                for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                    a, b = left + dx, top + dy
                    position = np.array([a, b]) + phase + [width / 2, height / 2]
                    competitor = float(scores[(xx - a) ** 2 + (yy - b) ** 2 > policy.distinct_radius ** 2].max())
                    sift_distance = float(np.linalg.norm(position - integer.feature_pixel_xy))
                    forced = replace(refined, pixel_xy=tuple(position), confidence=float(scores[b, a]),
                                     second_best_score=competitor, margin=float(scores[b, a] - competitor),
                                     agreement_error=max(integer.agreement_error, sift_distance))
                    offsets.append({"name": name, "dx": dx, "dy": dy,
                                    "integer_score": float(old_scores[b, a]),
                                    "subpixel_score": float(scores[b, a]),
                                    "margin": forced.margin,
                                    "distinct_wrong_location": sift_distance > policy.distinct_radius,
                                    "agreement_error": forced.agreement_error,
                                    "accepted": policy.evaluate(forced).accepted})
        return row

    for dataset, directory in (("01", folder), ("02", fresh)):
        for index in range(1, 11):
            partition = ("train" if index <= 5 else "held_out") if dataset == "01" else "fresh"
            name = f"surface-test-{dataset}_{index:03d}"
            mini = read_image(directory / f"stationary_{index:03d}.png")[y:y + height, x:x + width]
            positive = measure(name, partition, "positive", mini)
            angles = ((10, 45, 90, 180) if index <= 5 else (-10, -45, -90, 135, 2, -2)) if dataset == "01" else (2, -2, 10, -10, 45, 90, 180)
            for angle in angles:
                rotated = cv2.warpAffine(mini, cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1), (width, height))
                measure(f"{name}_rotation_{angle}", partition, "rotated", rotated)
            galleries = (reference[:, :355],) if dataset == "01" and index <= 5 else (reference[:, 603:],)
            if dataset == "02":
                galleries = (reference[:, :355], reference[:, 651:])
            for gallery_index, gallery in enumerate(galleries):
                wrong = HybridMapMatcher(gallery, replace(policy, reference_pixel_sha256=pixel_hash(gallery)))
                measure(f"{name}_absent_{gallery_index}", partition, "absent_terrain", mini, wrong)
            # Additional exact duplicated terrain: independent descriptors may
            # tie or disagree, but a strong duplicate must never be accepted.
            duplicate = np.concatenate((reference, reference), axis=1)
            repeated = HybridMapMatcher(duplicate, replace(policy, reference_pixel_sha256=pixel_hash(duplicate)))
            measure(f"{name}_duplicate", partition, "duplicate_terrain", mini, repeated)
            # Adversarial strong feature evidence at the original true copy:
            # descriptor ambiguity must not be the only duplicate-terrain guard.
            # This is a fault-injection control, not an independent SIFT result.
            feature = {key: positive["integer"][key] for key in (
                "feature_pixel_xy", "feature_matches", "feature_inliers", "feature_coverage", "geometry_error")}
            repeated_phase = phase_matchers[repeated.calibration.reference_pixel_sha256]
            with patch.object(repeated, "feature_translation", return_value=feature), \
                    patch.object(repeated_phase, "feature_translation", return_value=feature):
                measure(f"{name}_duplicate_strong_sift", partition, "duplicate_strong_sift", mini, repeated)
            measure(f"{name}_blank", partition, "blank", np.zeros_like(mini))
            print(name, flush=True)

    # Freeze new margin from original fitting data only, before looking at
    # held-out/fresh distributions. Never weaken the existing margin or score.
    train_positive = [r["subpixel"] for r in rows if r["partition"] == "train" and r["kind"] == "positive"]
    train_negative = [r["subpixel"] for r in rows if r["partition"] == "train" and r["kind"] != "positive"]
    pmin = min(r["margin"] for r in train_positive)
    nmax = max(r["margin"] for r in train_negative if r["margin"] is not None)
    assert pmin > nmax, (pmin, nmax)
    final = replace(policy, sampling_mode="sift_phase", min_margin=max(policy.min_margin, (pmin + nmax) / 2))
    for row in rows:
        row["subpixel"] = asdict(final.evaluate(LocalizationEvidence(**row["subpixel"])))
    summary = {}
    for partition in ("train", "held_out", "fresh", "combined"):
        for kind in ("positive", "negative"):
            group = [r for r in rows if (partition == "combined" or r["partition"] == partition)
                     and (r["kind"] == "positive") == (kind == "positive")]
            entry = {"count": len(group)}
            for method in ("integer", "subpixel"):
                entry[method] = {"accepted": sum(r[method]["accepted"] for r in group)}
                for field in ("confidence", "second_best_score", "margin", "feature_inliers", "geometry_error", "agreement_error"):
                    values = [r[method][field] for r in group if r[method][field] is not None]
                    entry[method][field] = distribution(values) if values else None
            summary[partition + "_" + kind] = entry
    clean = (summary["combined_positive"]["subpixel"]["accepted"] == 20 and
             summary["combined_negative"]["subpixel"]["accepted"] == 0 and
             not any(r["accepted"] and r["distinct_wrong_location"] for r in offsets) and
             not any(r.get("subpixel_spatial_wrong_above_0700", 0) for r in rows))
    result = {"method": "SIFT fractional translation phase; one common bilinear gradient grid, no fractional search; retain independent coarse agreement",
              "opencv_version": cv2.__version__, "inputs_sha256": inputs,
              "source_sha256": {name: sha256(ROOT / name) for name in (
                  "scripts/validate_subpixel_gradient.py", "src/overworld/navigation/image_matcher.py")},
              "reference_file_sha256": prior["reference_sha256"], "original_policy": asdict(policy),
              "policy": asdict(final), "margin_fit": {"original_train_positive_min": pmin, "original_train_negative_max": nmax},
              "summary": summary, "offline_clean": clean, "rows": rows, "offset_controls": offsets,
              "limitations": "Correlated frames at two poses in one reference; fresh layer/absolute geometry unverified; original held-out frames were already used in prior evaluation. No live Test A certification, movement, or Test B."}
    output.mkdir(exist_ok=True)
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if clean:
        calibration = {"schema_version": 1, "scope": "localization_only", "policy": asdict(final),
                       "validation": {"evidence": "results.json", "margin_fit": result["margin_fit"],
                                      "score_threshold": "0.700 retained and revalidated on combined datasets; no score-only acceptance",
                                      "limitations": result["limitations"]}}
        (output / "matcher_calibration.json").write_text(json.dumps(calibration, indent=2) + "\n", encoding="utf-8")
        assert MatcherCalibration.load(output / "matcher_calibration.json") == final
    print(json.dumps({"offline_clean": clean, "policy": asdict(final),
                      "acceptance": {key: {"count": value["count"], "integer": value["integer"]["accepted"],
                                           "subpixel": value["subpixel"]["accepted"]} for key, value in summary.items()}}, indent=2))
    return result


if __name__ == "__main__":
    main()
