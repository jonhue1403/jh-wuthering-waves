"""Build a reviewable surface-profile draft from measured landmarks, without game input."""

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from .map_data import KuroMapDataProvider
from .planner import cluster_spawns


def fit_landmarks(rows, max_error_pixels):
    """Fit positive uniform scale/translation; never fit the held-out landmarks."""
    if not np.isfinite(max_error_pixels) or max_error_pixels <= 0:
        raise ValueError("Choose a finite positive landmark error limit before fitting")
    if any(row.get("role") not in ("fit", "held_out") for row in rows):
        raise ValueError("Each landmark needs role=fit or role=held_out")
    image = np.array([[float(row.get("image_x", row.get("reference_x"))),
                       float(row.get("image_y", row.get("reference_y")))] for row in rows])
    world = np.array([[float(row["kuro_x"]), float(row["kuro_y"])] for row in rows])
    fitting = np.array([row["role"] == "fit" for row in rows])
    if len(rows) < 3 or fitting.sum() < 2 or (~fitting).sum() < 1:
        raise ValueError("Supply two fitting landmarks and at least one independent held-out landmark")
    if not np.isfinite(image).all() or not np.isfinite(world).all():
        raise ValueError("Landmark coordinates must be finite")
    if len(np.unique(image, axis=0)) != len(rows) or len(np.unique(world, axis=0)) != len(rows):
        raise ValueError("Landmarks must represent distinct locations")
    centered_image = image[fitting] - image[fitting].mean(axis=0)
    centered_world = world[fitting] - world[fitting].mean(axis=0)
    scale = float(np.sum(centered_image * centered_world) / np.sum(centered_image ** 2))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Reference requires rotation/reflection or has invalid scale")
    origin = world[fitting].mean(axis=0) - image[fitting].mean(axis=0) * scale
    errors = np.linalg.norm((origin + image * scale - world) / scale, axis=1)
    if np.max(errors) > max_error_pixels:
        raise ValueError(f"Landmark error {np.max(errors):.3f}px exceeds {max_error_pixels:.3f}px")
    return {
        "origin": origin.tolist(), "units_per_pixel": scale,
        "landmark_error_pixels": errors.tolist(),
        "held_out_max_error_pixels": float(np.max(errors[~fitting])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--target", required=True, help="Exact source mob id or name")
    parser.add_argument("--state", type=int, required=True)
    parser.add_argument("--floor", default="")
    parser.add_argument("--spawn-id", action="append", required=True)
    parser.add_argument("--frame-size", type=int, nargs=2, required=True, metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--max-error-pixels", type=float, required=True)
    parser.add_argument("--stationary-tolerance-pixels", type=float, required=True)
    parser.add_argument("--matcher-calibration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output already exists; choose a new draft filename")
    if (min(args.frame_size) <= 0 or not np.isfinite(args.stationary_tolerance_pixels)
            or args.stationary_tolerance_pixels <= 0):
        parser.error("Frame size and stationary tolerance must be positive and finite")
    for source in (args.reference, args.landmarks, args.database, args.matcher_calibration):
        if source is not None and not source.is_file():
            parser.error(f"Missing source: {source}")
    with args.landmarks.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    fit = fit_landmarks(rows, args.max_error_pixels)
    image = cv2.imdecode(np.fromfile(args.reference, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Reference image could not be decoded")
    spawns = KuroMapDataProvider(args.database).query_target_mob_locations(
        args.target, state_id=args.state, floor_id=args.floor)
    selected = tuple(s for s in spawns if s.spawn_id in args.spawn_id)
    if {s.spawn_id for s in selected} != set(args.spawn_id):
        raise ValueError("Spawn ids do not match the exact target and layer")
    scale = fit["units_per_pixel"]
    if len(cluster_spawns(selected, radius=20 * scale)) != 1:
        raise ValueError("Select exactly one camp for controlled live validation")
    for spawn in selected:
        x, y = (np.array([spawn.coordinate.x, spawn.coordinate.y]) - fit["origin"]) / scale
        if not (0 <= x < image.shape[1] and 0 <= y < image.shape[0]):
            raise ValueError(f"Spawn {spawn.spawn_id} is outside the reference image")
    profile = {
        "surface_verified": False, "localization_verified": False, "navigation_verified": False,
        "map_image": str(args.reference.resolve()), "kuro_database": str(args.database.resolve()),
        "target_mob": args.target, "state_id": args.state, "floor_id": args.floor,
        "origin": fit["origin"], "units_per_pixel": scale, "frame_size": args.frame_size,
        "spawn_ids": args.spawn_id, "match_threshold": 0.7,
        "localization_tolerance_pixels": args.stationary_tolerance_pixels,
        "calibration_review": {**fit, "landmarks": str(args.landmarks.resolve()),
                               "max_error_pixels": args.max_error_pixels},
    }
    if args.matcher_calibration:
        from .navigation.image_matcher import MatcherCalibration, pixel_hash
        policy = MatcherCalibration.load(args.matcher_calibration)
        if (policy.state_id, policy.floor_id) != (args.state, args.floor):
            raise ValueError("Matcher calibration belongs to a different layer")
        if pixel_hash(image) != policy.reference_pixel_sha256:
            raise ValueError("Matcher calibration belongs to a different reference")
        profile["matcher_calibration"] = str(args.matcher_calibration.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(profile, file, indent=2, allow_nan=False)
        file.write("\n")
    print(f"Draft saved: {args.output.resolve()}. Review the surface and landmarks before enabling Test A.")
    return profile


if __name__ == "__main__":
    main()
