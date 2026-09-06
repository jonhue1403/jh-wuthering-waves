"""Calibrated, local image matching in the same coordinate system as Kuro data.

The profile is a manually verified surface area, not a world/layer detector.
North-up images must have the same scale as the live minimap (as in FarmMap).
"""

from dataclasses import asdict, dataclass
import json
from math import atan2, degrees, isfinite
from pathlib import Path

from ..models import HuntPosition, MapCoordinate
from .route_follower import WaypointObservation


@dataclass(frozen=True)
class SurfaceProfile:
    image_path: Path
    database_path: Path
    target_mob: str
    state_id: int
    floor_id: str
    origin: MapCoordinate
    units_per_pixel: float
    frame_size: tuple[int, int]
    spawn_ids: frozenset[str]
    match_threshold: float = 0.7
    localization_tolerance_pixels: float | None = None
    matcher_calibration_path: Path | None = None

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("surface_verified") is not True:
            raise ValueError("A manually verified surface profile is required")
        profile = cls(
            (path.parent / data["map_image"]).resolve(),
            (path.parent / data["kuro_database"]).resolve(),
            str(data["target_mob"]), int(data["state_id"]), str(data["floor_id"]),
            MapCoordinate(*data["origin"]), float(data["units_per_pixel"]),
            tuple(data["frame_size"]), frozenset(str(s) for s in data["spawn_ids"]),
            float(data.get("match_threshold", 0.7)),
            (float(data["localization_tolerance_pixels"])
             if data.get("localization_tolerance_pixels") is not None else None),
            ((path.parent / data["matcher_calibration"]).resolve()
             if data.get("matcher_calibration") else None),
        )
        if (not profile.target_mob or not profile.spawn_ids
                or not isfinite(profile.units_per_pixel) or profile.units_per_pixel <= 0
                or not all(isfinite(v) for v in (profile.origin.x, profile.origin.y))
                or len(profile.frame_size) != 2 or min(profile.frame_size) <= 0
                or not 0.6 <= profile.match_threshold <= 1):
            raise ValueError("Invalid surface profile calibration or target selection")
        if (profile.localization_tolerance_pixels is not None
                and (not isfinite(profile.localization_tolerance_pixels)
                     or profile.localization_tolerance_pixels <= 0)):
            raise ValueError("Localization tolerance must be positive and finite")
        if not profile.image_path.is_file() or not profile.database_path.is_file():
            raise ValueError("Surface profile image or Kuro database is missing")
        return profile

    @property
    def layer(self):
        return self.state_id, self.floor_id

    def world_position(self, x, y):
        return HuntPosition(self.state_id, self.floor_id, MapCoordinate(
            self.origin.x + x * self.units_per_pixel,
            self.origin.y + y * self.units_per_pixel,
        ))

    def image_coordinate(self, coordinate):
        return ((coordinate.x - self.origin.x) / self.units_per_pixel,
                (coordinate.y - self.origin.y) / self.units_per_pixel)


@dataclass(frozen=True)
class LocalizationEvidence:
    """Measured signals, not a synthetic probability. Rejection keeps evidence."""

    pixel_xy: tuple[float, float] | None
    confidence: float | None
    source: str
    accepted: bool = False
    reason: str = "unvalidated"
    second_best_score: float | None = None
    margin: float | None = None
    feature_pixel_xy: tuple[float, float] | None = None
    feature_matches: int = 0
    feature_inliers: int = 0
    geometry_error: float | None = None
    agreement_error: float | None = None
    feature_coverage: float = 0.0


class PlayerLocator:
    def __init__(self, profile, *, match_player, facing, image_size, diagnostic=None):
        self.profile = profile
        self.match_player = match_player
        self.facing = facing
        self.image_size = image_size
        self.diagnostic = diagnostic or (lambda *args, **kwargs: None)
        self.last_confidence = None
        self.last_evidence = None

    def contains(self, coordinate):
        x, y = self.profile.image_coordinate(coordinate)
        return 0 <= x < self.image_size[0] and 0 <= y < self.image_size[1]

    def locate(self):
        self.last_confidence = None
        self.last_evidence = None
        match = self.match_player()
        if match is None:
            self.diagnostic("localization", valid=False, source="local_image", reason="no_match")
            return None
        if isinstance(match, LocalizationEvidence):
            self.last_evidence = match
            self.last_confidence = match.confidence
            self.diagnostic("localization_evidence", **asdict(match))
            if not match.accepted or match.pixel_xy is None or match.confidence is None:
                self.diagnostic("localization", valid=False, source=match.source, reason=match.reason)
                return None
            match = (*match.pixel_xy, match.confidence)
        x, y, confidence = match
        self.last_confidence = confidence
        if (not all(isfinite(v) for v in match)
                or confidence < self.profile.match_threshold
                or not (0 <= x < self.image_size[0] and 0 <= y < self.image_size[1])):
            self.diagnostic("localization", valid=False, source="local_image",
                            confidence=confidence, pixel_xy=(x, y), reason="confidence_or_bounds")
            return None
        position = self.profile.world_position(x, y)
        self.diagnostic("localization", valid=True,
                        source=self.last_evidence.source if self.last_evidence else "local_image",
                        state_id=position.state_id, floor_id=position.floor_id,
                        layer_source="verified_profile", confidence=confidence,
                        xy=(position.coordinate.x, position.coordinate.y), pixel_xy=(x, y))
        return position

    def observe(self, target):
        if (target.state_id, target.floor_id) != self.profile.layer or not self.contains(target.coordinate):
            return None
        position = self.locate()
        if position is None:
            return None
        facing = self.facing()
        if facing is None or not isfinite(facing):
            return None
        dx = target.coordinate.x - position.coordinate.x
        dy = target.coordinate.y - position.coordinate.y
        bearing = (degrees(atan2(dy, dx)) - facing + 180) % 360 - 180
        return WaypointObservation(position.coordinate.distance_to(target.coordinate), bearing,
                                   (position.coordinate.x, position.coordinate.y))
