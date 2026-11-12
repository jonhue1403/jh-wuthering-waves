"""Bounded, read-only audit of local route/profile candidate files.

Unlike MaterialRoute.load and RuntimeQualification.assert_compatible, this module
NEVER authorizes gameplay or imports the executor. A local file claiming REVIEWED
is still untrusted historical metadata; hashes do not prove gameplay or versions.
Only direct child files in the private calibration folder are inspected.
"""

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
import time

from src.automation.farming_static_json import read_static_json


DEFAULT_ROUTES_DIR = (
    Path(__file__).resolve().parents[2] / "configs" / "farming-assistant" / "routes"
)
MAX_ROUTES = 8
MAX_MANIFEST_BYTES = 48 * 1024
MAX_PROFILE_BYTES = 32 * 1024
MAX_EVIDENCE_FILES = 8
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_HASH_BYTES = 64 * 1024 * 1024
SLUG = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
NAME = re.compile(r"[A-Za-z0-9_.-]{1,120}\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")


class AuditBudgetExhausted(ValueError):
    """Stop scanning when a bounded hash budget is exceeded."""


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    material_id: str
    game_mob_id: str
    camp_count: int


def _name(value):
    return isinstance(value, str) and NAME.fullmatch(value) is not None and value not in (".", "..")


def _safe_file(base, name, limit):
    if not _name(name):
        raise ValueError("Invalid local calibration file name")
    path = base / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked calibration file")
    size = path.stat().st_size
    if not 0 < size <= limit:
        raise ValueError("Invalid calibration file size")
    return path, size


def _load_json(base, name, limit):
    path, _ = _safe_file(base, name, limit)
    return read_static_json(path, max_bytes=limit)


def _sha_match(base, name, digest, byte_budget, *, limit):
    if not isinstance(digest, str) or not HASH.fullmatch(digest):
        raise ValueError("Invalid calibration digest")
    path, size = _safe_file(base, name, limit)
    if byte_budget[0] + size > MAX_TOTAL_HASH_BYTES:
        raise AuditBudgetExhausted("Hash budget exhausted")
    byte_budget[0] += size
    checksum = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    if checksum.hexdigest() != digest:
        raise ValueError("Stale or altered calibration file")


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def _rectangle(values):
    return (isinstance(values, list) and len(values) == 4
            and all(_number(v) and 0 <= v <= 1 for v in values)
            and values[0] < values[2] and values[1] < values[3])


def _candidate(base, manifest_name, byte_budget):
    data = _load_json(base, manifest_name, MAX_MANIFEST_BYTES)
    if (type(data.get("schema_version")) is not int or data["schema_version"] != 1
            or data.get("status") != "REVIEWED"
            or data.get("surface_only") is not True):
        raise ValueError("Route is not reviewed surface metadata")
    route_id = data.get("route_id")
    if not isinstance(route_id, str) or not ID.fullmatch(route_id):
        raise ValueError("Invalid route ID")

    mapping = data.get("material_source")
    if not isinstance(mapping, dict) or mapping.get("kind") != "observed_mob_drop":
        raise ValueError("Missing claimed observed source mapping")
    material_id, game_mob = mapping.get("material_id"), mapping.get("target_mob")
    if (not isinstance(material_id, str) or not SLUG.fullmatch(material_id)
            or not isinstance(game_mob, str) or not game_mob.isascii()
            or not game_mob.isdecimal() or len(game_mob) > 32
            or not isinstance(mapping.get("item_text"), str)
            or not mapping["item_text"].strip()):
        raise ValueError("Unqualified source identity")

    profile_name = data.get("profile")
    profile_hash = data.get("profile_sha256")
    if not _name(profile_name) or not profile_name.lower().endswith(".json"):
        raise ValueError("Profile must be a local JSON file")
    _sha_match(base, profile_name, profile_hash, byte_budget, limit=MAX_PROFILE_BYTES)
    profile = _load_json(base, profile_name, MAX_PROFILE_BYTES)
    if (profile.get("surface_verified") is not True
            or str(profile.get("target_mob")) != game_mob
            or profile.get("state_id") != data.get("state_id")
            or str(profile.get("floor_id")) != str(data.get("floor_id"))):
        raise ValueError("Profile, game mob or map layer mismatch")
    spawn_ids = profile.get("spawn_ids")
    if (not isinstance(spawn_ids, list) or not spawn_ids
            or any(not isinstance(s, (str, int)) or isinstance(s, bool)
                   for s in spawn_ids)):
        raise ValueError("Missing profile spawns")
    expected = {str(s) for s in spawn_ids}
    if len(expected) != len(spawn_ids) or any(not value for value in expected):
        raise ValueError("Ambiguous profile spawns")

    segments = data.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 3:
        raise ValueError("Route needs one to three reviewed camps")
    radius, seconds = data.get("rejoin_radius"), data.get("max_seconds")
    if (not _number(radius) or radius <= 0 or not _number(seconds)
            or not 1 <= seconds <= 1800):
        raise ValueError("Invalid route bounds")
    observed_spawns = set()
    camp_ids = set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("Invalid segment")
        camp = segment.get("camp_id")
        spawns = segment.get("spawn_ids")
        points = segment.get("waypoints")
        if (not isinstance(camp, str) or not ID.fullmatch(camp)
                or camp in camp_ids or not isinstance(spawns, list) or not spawns
                or not isinstance(points, list) or not 2 <= len(points) <= 32):
            raise ValueError("Invalid or duplicate camp")
        camp_ids.add(camp)
        for spawn in spawns:
            if not isinstance(spawn, (str, int)) or isinstance(spawn, bool):
                raise ValueError("Invalid spawn ID")
            value = str(spawn)
            if not value or value in observed_spawns:
                raise ValueError("Overlapping route spawns")
            observed_spawns.add(value)
        if any(not isinstance(point, (list, tuple)) or len(point) != 2
               or not all(_number(v) for v in point) for point in points):
            raise ValueError("Non-finite route waypoint")
    if observed_spawns != expected:
        raise ValueError("Route does not cover exact profile spawns")

    evidence = data.get("evidence_sha256")
    if (not isinstance(evidence, dict)
            or not 1 <= len(evidence) <= MAX_EVIDENCE_FILES
            or any(not _name(name) for name in evidence)):
        raise ValueError("Missing, excessive or unsafe route evidence")
    if (mapping.get("evidence") not in evidence
            or any(segment.get("evidence") not in evidence for segment in segments)):
        raise ValueError("Material source or camp has no hashed evidence")
    reader = data.get("inventory_reader")
    if (not isinstance(reader, dict)
            or reader.get("evidence") not in evidence
            or reader.get("item_text") != mapping["item_text"]
            or not reader.get("screen_feature")
            or not _rectangle(reader.get("label_box"))
            or not _rectangle(reader.get("quantity_box"))):
        raise ValueError("Inventory observation lacks compatible evidence")
    for name in ("open_steps", "close_steps"):
        steps = reader.get(name)
        if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
            raise ValueError("Unbounded inventory UI steps")
        for step in steps:
            if (not isinstance(step, dict) or not step.get("screen_feature")
                    or not ((set(step) == {"screen_feature", "click_feature"}
                             and step["click_feature"])
                            or (set(step) == {"screen_feature", "key"}
                                and step["key"] in ("b", "m", "esc")))):
                raise ValueError("Unsupported inventory step")
    pickup = reader.get("pickup")
    if (not isinstance(pickup, dict) or pickup.get("evidence") not in evidence
            or not pickup.get("prompt_text")):
        raise ValueError("Pickup lacks screenshot evidence")
    for name, digest in sorted(evidence.items()):
        _sha_match(base, name, digest, byte_budget, limit=MAX_EVIDENCE_BYTES)

    # No sidecar/current game/frame observation or input ownership is checked
    # here. A structurally plausible candidate is NOT qualified to execute.
    return RouteCandidate(route_id, material_id, game_mob, len(segments))


class FarmingRouteAudit:
    """Cache only informational, path-free summaries of private local candidates."""

    def __init__(self, directory=None, *, ttl_seconds=10.0, clock=time.monotonic):
        self.directory = Path(directory) if directory is not None else DEFAULT_ROUTES_DIR
        if type(ttl_seconds) not in (float, int) or not 0 <= ttl_seconds <= 60:
            raise ValueError("Invalid audit cache duration")
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._cached = None
        self._checked_at = None

    def _scan(self):
        base = self.directory
        try:
            if base.is_symlink() or (base.exists() and not base.is_dir()):
                return (), 1, True
            if not base.exists():
                return (), 0, False
            manifests = sorted(base.glob("*.route.json"))
        except OSError:
            return (), 1, True
        candidates = []
        route_ids = set()
        rejected = 0
        incomplete = len(manifests) > MAX_ROUTES
        budget = [0]
        for path in manifests[:MAX_ROUTES]:
            try:
                candidate = _candidate(base, path.name, budget)
                # Distinct manifest filenames are not distinct routes.  Never
                # count duplicate route IDs as multiple calibrated candidates.
                if candidate.route_id in route_ids:
                    raise ValueError("Duplicate candidate route ID")
                route_ids.add(candidate.route_id)
                candidates.append(candidate)
            except AuditBudgetExhausted:
                incomplete = True
                rejected += 1
                break
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                rejected += 1
        return tuple(candidates), rejected, incomplete

    def summary(self, material_id):
        if not isinstance(material_id, str) or not SLUG.fullmatch(material_id):
            raise ValueError("Unknown material")
        now = self.clock()
        if (self._cached is None or self._checked_at is None
                or now < self._checked_at
                or now - self._checked_at >= self.ttl_seconds):
            self._cached = self._scan()
            self._checked_at = now
        candidates, rejected, incomplete = self._cached
        matches = tuple(candidate for candidate in candidates
                        if candidate.material_id == material_id)
        return {
            "material_id": material_id,
            "status": ("ROUTE_AUDIT_INCOMPLETE" if incomplete else
                       "LOCAL_ROUTE_CANDIDATES_ONLY" if matches else
                       "NO_LOCAL_ROUTES"),
            "route_candidate_count": len(matches),
            "rejected_manifest_count": rejected,
            "routes": [
                {"route_id": entry.route_id, "game_mob_id": entry.game_mob_id,
                 "camp_count": entry.camp_count,
                 "evidence_level": "local_static_hash_match_only"}
                for entry in matches
            ],
            "can_start": False,
            "note": (
                "Local route metadata/hashes do not prove current game version, "
                "independent review, fresh frames, runtime authorization or safe input."
            ),
        }
