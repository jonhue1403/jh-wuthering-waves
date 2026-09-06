"""Offline, capture-specific Test A evidence. Never constructs OK or a game task.

Run from the repository root with the local venv. Original captures and the
Kuro database are read-only. Outputs go to surface-test-01/analysis only.
"""

import csv
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ok.feature.FeatureSet import FeatureSet
from src.overworld.models import MapCoordinate
from src.overworld.navigation.player_locator import PlayerLocator, SurfaceProfile
from src.task.FarmMapTask import create_circle_mask_with_hole


def read_image(path):
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable image: {path}")
    return image


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fit_scale_offset(pixels, coordinates):
    """Least squares for world = positive uniform scale * pixel + offset."""
    p, q = np.asarray(pixels, float), np.asarray(coordinates, float)
    dp, dq = p - p.mean(axis=0), q - q.mean(axis=0)
    scale = float(np.sum(dp * dq) / np.sum(dp * dp))
    return scale, q.mean(axis=0) - scale * p.mean(axis=0)


def icon_center(image, roi, low, high):
    """ROI only selects a visibly identified icon; its pixels determine center."""
    x, y, width, height = roi
    hsv = cv2.cvtColor(image[y:y + height, x:x + width], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(low), np.array(high))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    component = max(stats[1:], key=lambda row: row[4])
    left, top, w, h, _ = (int(v) for v in component)
    return [x + left + (w - 1) / 2, y + top + (h - 1) / 2]


def strongest_match(reference, mini, mask):
    scores = cv2.matchTemplate(reference, mini, cv2.TM_CCOEFF_NORMED, mask=mask)
    np.nan_to_num(scores, copy=False, nan=0, posinf=0, neginf=0)
    _, score, _, (x, y) = cv2.minMaxLoc(scores)
    # Match the runtime Box.center() rounding, including its half-pixel behavior.
    return [round(x + mini.shape[1] / 2), round(y + mini.shape[0] / 2)], score


def main():
    capture = ROOT / "assets/overworld/calibration/surface-test-01"
    output = capture / "analysis"
    output.mkdir(exist_ok=True)
    database = ROOT.parent / "wuwa-map/map_items.db"
    paths = sorted(capture.glob("stationary_*.png"))
    metadata = json.loads((capture / "metadata.json").read_text())
    assert len(paths) == metadata["frame_count"] == 10 and metadata["complete"]
    full = read_image(capture / "full_map_position.png")
    frames = [read_image(path) for path in paths]
    assert all(frame.shape == (1440, 2560, 3) for frame in frames + [full])
    features = FeatureSet(False, str(ROOT / "assets/coco_annotations.json"), 0, 0)
    box = features.get_box_by_name(frames[0], "box_minimap")
    minis = [box.crop_frame(frame) for frame in frames]
    mask = create_circle_mask_with_hole(minis[0])

    # Pixel ROIs were identified visually in the original full-map screenshot.
    definitions = [
        ("Northeast Resonance Beacon", "1451326173333368832",
         (2120, 220, 90, 110), (85, 90, 160), (110, 255, 255)),
        ("South Resonance Beacon", "1451327183948935168",
         (1400, 1100, 90, 110), (85, 90, 160), (110, 255, 255)),
        ("West fixed Tacet Discord settlement marker", "1451217545689624576",
         (610, 515, 110, 110), (0, 100, 70), (10, 255, 255)),
    ]
    landmarks = []
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for label, location_id, roi, low, high in definitions:
            record = dict(connection.execute(
                "SELECT l.id, l.item_id, i.name, l.x, l.y, l.state_id, l.floor_id, "
                "l.country_id, l.description FROM location l JOIN item i ON i.id=l.item_id "
                "WHERE l.id=?", (location_id,),
            ).fetchone())
            record.update(label=label, full_map_pixel_xy=icon_center(full, roi, low, high),
                          pixel_source="HSV connected-component bounding-box center",
                          selection_roi=list(roi), hsv_low=list(low), hsv_high=list(high))
            landmarks.append(record)
        # Check other same-layer beacon pair assignments against the held-out marker.
        beacons = [dict(row) for row in connection.execute(
            "SELECT id,x,y FROM location WHERE state_id=906 AND floor_id='' AND item_id='CS_02'")]
    pixels = np.array([record["full_map_pixel_xy"] for record in landmarks])
    world = np.array([[record["x"], record["y"]] for record in landmarks])
    world_scale, origin = fit_scale_offset(pixels[:2], world[:2])
    landmark_errors = np.linalg.norm((world - origin) / world_scale - pixels, axis=1)
    assignments = []
    for first in beacons:
        for second in beacons:
            if first["id"] == second["id"]:
                continue
            coordinates = np.array([[first["x"], first["y"]], [second["x"], second["y"]]])
            scale, offset = fit_scale_offset(pixels[:2], coordinates)
            if scale > 0:
                errors = np.linalg.norm((np.vstack((coordinates, world[2])) - offset) / scale - pixels, axis=1)
                assignments.append({"ids": [first["id"], second["id"]],
                                    "max_residual_full_map_pixels": float(max(errors))})
    assignments.sort(key=lambda value: value["max_residual_full_map_pixels"])
    assert assignments[0]["ids"] == [record["id"] for record in landmarks[:2]]

    # Measure relative image scale from native-resolution terrain correspondences.
    # SIFT is analysis-only, not a replacement locator. No score/scale search.
    sift = cv2.SIFT_create()
    k1, d1 = sift.detectAndCompute(cv2.cvtColor(minis[0], cv2.COLOR_BGR2GRAY), mask)
    k2, d2 = sift.detectAndCompute(cv2.cvtColor(full, cv2.COLOR_BGR2GRAY), None)
    matches = [a for a, b in cv2.BFMatcher().knnMatch(d1, d2, k=2) if a.distance < 0.7 * b.distance]
    pairs = sorted(set((tuple(k1[m.queryIdx].pt), tuple(k2[m.trainIdx].pt)) for m in matches))
    source = np.float32([a for a, b in pairs])
    destination = np.float32([b for a, b in pairs])
    cv2.setRNGSeed(0)
    affine, inliers = cv2.estimateAffinePartial2D(
        source, destination, method=cv2.RANSAC, ransacReprojThreshold=3, maxIters=10000)
    inliers = inliers.ravel().astype(bool)
    assert inliers.sum() >= 3
    # The reference model supports north-up uniform scaling, not rotation.
    image_scale, image_offset = fit_scale_offset(source[inliers], destination[inliers])
    terrain_errors = np.linalg.norm(
        image_scale * source[inliers] + image_offset - destination[inliers], axis=1)
    # Spatially distributed withheld correspondences diagnose scale-fit residual.
    inside_source, inside_destination = source[inliers], destination[inliers]
    held_out = np.arange(len(inside_source)) % 3 == 0
    train_scale, train_offset = fit_scale_offset(inside_source[~held_out], inside_destination[~held_out])
    held_out_errors = np.linalg.norm(
        train_scale * inside_source[held_out] + train_offset - inside_destination[held_out], axis=1)
    reference_size = tuple(math.ceil(n / image_scale) for n in full.shape[1::-1])
    reference = cv2.warpAffine(full, np.float64([[1 / image_scale, 0, 0], [0, 1 / image_scale, 0]]),
                               reference_size, flags=cv2.INTER_LINEAR)
    reference_path = output / "reference_candidate.png"
    success, encoded = cv2.imencode(".png", reference)
    assert success
    reference_path.write_bytes(encoded.tobytes())

    # Geometry-only profile: not saved as, nor usable as, a live hunt profile.
    # Mob/camp selection and surface verification are intentionally not invented.
    profile = SurfaceProfile(reference_path, database, "", 906, "", MapCoordinate(*origin),
                             world_scale * image_scale, (2560, 1440), frozenset())
    samples = []
    for path, mini in zip(paths, minis):
        pixel, score = strongest_match(reference, mini, mask)
        boxes = features.find_one_feature(reference, None, template=mini, mask_function=create_circle_mask_with_hole,
                                           threshold=profile.match_threshold, limit=1)
        match = (*boxes[0].center(), boxes[0].confidence) if boxes else None
        locator = PlayerLocator(profile, match_player=lambda: match, facing=lambda: None, image_size=reference_size)
        accepted = locator.locate()
        candidate = profile.world_position(*pixel).coordinate
        samples.append({"filename": path.name, "source": "OK-Script masked TM_CCOEFF_NORMED",
                        "confidence": score, "accepted_xy": ([accepted.coordinate.x, accepted.coordinate.y]
                                                              if accepted else None),
                        "candidate_only_xy": [candidate.x, candidate.y], "reference_pixel_xy": pixel,
                        "state_id": 906, "floor_id": "", "layer_source": "Kuro landmark correspondence; not image-detected"})
    candidates = np.array([sample["candidate_only_xy"] for sample in samples])
    pixel_candidates = np.array([sample["reference_pixel_xy"] for sample in samples])
    pairwise = np.linalg.norm(pixel_candidates[:, None] - pixel_candidates[None, :], axis=2)
    # Independent visible player arrow comparison, NOT an exact world ground truth.
    hsv = cv2.cvtColor(full[680:775, 1230:1340], cv2.COLOR_BGR2HSV)
    arrow_mask = cv2.inRange(hsv, np.array([15, 100, 190]), np.array([40, 255, 255]))
    _, _, stats, centers = cv2.connectedComponentsWithStats(arrow_mask)
    arrow_index = 1 + int(np.argmax(stats[1:, 4]))
    arrow_centroid = centers[arrow_index] + [1230, 680]
    arrow_world = origin + world_scale * arrow_centroid
    _, raw_score = strongest_match(full, minis[0], mask)
    _, grayscale_score = strongest_match(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY),
                                        cv2.cvtColor(minis[0], cv2.COLOR_BGR2GRAY), mask)
    report = {
        "status": "FAIL" if any(s["accepted_xy"] is None for s in samples) else "REVIEW_REQUIRED",
        "test_b_authorized": False,
        "inputs_sha256": {p.name: sha256(p) for p in paths + [capture / "full_map_position.png", capture / "metadata.json"]},
        "database_sha256": sha256(database), "opencv_version": cv2.__version__,
        "reference_sha256": sha256(reference_path),
        "reference_derivation": {
            "source": "User full_map_position.png, unchanged 2560x1440; no local Kuro tiles exist",
            "operation": "warpAffine uniform scale 1/image_scale; INTER_LINEAR; no crop, rotation, score optimization or source overwrite",
            "image_scale_full_map_pixels_per_minimap_pixel": image_scale,
            "reference_size": list(reference_size), "world_units_per_full_map_pixel": world_scale,
            "world_origin": origin.tolist(), "world_units_per_reference_pixel": profile.units_per_pixel,
            "sift_raw_ratio_matches": len(matches), "sift_unique_pairs": len(pairs),
            "sift_unique_inliers": int(inliers.sum()),
            "similarity_rotation_degrees_diagnostic_only": math.degrees(math.atan2(affine[1, 0], affine[0, 0])),
            "terrain_residual_max_full_map_pixels": float(max(terrain_errors)),
            "terrain_held_out_count": int(held_out.sum()),
            "terrain_held_out_residual_max_full_map_pixels": float(max(held_out_errors)),
            "terrain_correspondences": [{"minimap_xy": a.tolist(), "full_map_xy": b.tolist(), "inlier": bool(i)}
                                        for a, b, i in zip(source, destination, inliers)],
        },
        "landmarks": landmarks, "landmark_residuals_full_map_pixels": landmark_errors.tolist(),
        "landmark_fit": "Two beacons fit uniform positive scale+offset; west settlement is held out",
        "best_two_same_layer_beacon_assignments": assignments[:2],
        "layer_assessment": "state 906 via three Kuro POIs; all floor_id empty. Empty floor_id is not proof of surface. User reports surface; screenshot shows outdoors.",
        "minimap_box_xywh": [box.x, box.y, box.width, box.height],
        "runtime_threshold_unchanged": profile.match_threshold,
        "samples": samples,
        "statistics": {
            "accepted_count": sum(s["accepted_xy"] is not None for s in samples),
            "candidate_mean_xy": candidates.mean(axis=0).tolist(),
            "candidate_sample_variance_xy": candidates.var(axis=0, ddof=1).tolist(),
            "candidate_max_pairwise_spread_reference_pixels": float(pairwise.max()),
            "candidate_max_pairwise_spread_world_units": float(pairwise.max() * profile.units_per_pixel),
            "observed_candidate_noise_envelope_reference_pixels": float(np.linalg.norm(pixel_candidates - pixel_candidates.mean(axis=0), axis=1).max()),
            "accepted_localization_tolerance": None,
            "tolerance_explanation": "No accepted positions: cannot derive an accepted localization tolerance. Candidate envelope is an observed statistic, not a pass threshold; integer quantization and shared scale calibration can hide error.",
        },
        "independent_position_comparison": {
            "source": "Full-map yellow player-arrow HSV component centroid, excluded from terrain fit",
            "full_map_pixel_xy": arrow_centroid.tolist(), "approximate_kuro_xy": arrow_world.tolist(),
            "candidate_distance_reference_pixels": float(np.linalg.norm(candidates.mean(axis=0) - arrow_world) / profile.units_per_pixel),
            "absolute_ground_truth_error": None,
            "limitation": "Arrow centroid is not a verified position anchor; icon geometry and Kuro landmark precision remain uncalibrated. HUD coordinate text has no verified conversion and is not used.",
        },
        "diagnostics": {"native_full_map_score_frame_001": raw_score, "grayscale_score_frame_001_analysis_only": grayscale_score,
                        "note": "Scale correction alone does not meet the existing color matcher threshold. No threshold, mask, runtime matcher, or game task changed."},
    }
    (output / "test_a_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (output / "landmarks.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["label", "source_location_id", "item_id", "state_id", "floor_id", "kuro_x", "kuro_y", "full_map_x", "full_map_y", "reference_x", "reference_y", "role"])
        for index, landmark in enumerate(landmarks):
            point = np.array(landmark["full_map_pixel_xy"])
            writer.writerow([landmark["label"], landmark["id"], landmark["item_id"], landmark["state_id"], landmark["floor_id"],
                             landmark["x"], landmark["y"], *point, *(point / image_scale), "fit" if index < 2 else "held_out"])
    print(json.dumps({key: report[key] for key in ("status", "statistics", "independent_position_comparison", "diagnostics")}, indent=2))


if __name__ == "__main__":
    main()
