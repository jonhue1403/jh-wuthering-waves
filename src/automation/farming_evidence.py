"""Bounded read-only audit of locally collected material-drop receipts.

This scans only the application's internal evidence directory. File hashes and
metadata establish an auditable *candidate*, NOT an authenticated game drop or
current-runtime execution authorization. No game/input/task modules are imported.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import re
import time

from src.automation.farming_static_json import read_static_json


DEFAULT_EVIDENCE_DIR = (
    Path(__file__).resolve().parents[2] / "configs" / "farming-assistant" / "evidence"
)
MAX_MANIFESTS = 24
MAX_MANIFEST_BYTES = 16 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_AGE = timedelta(days=30)
FUTURE_TOLERANCE = timedelta(minutes=5)
SLUG = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class ReceiptCandidate:
    """Historic local evidence candidate; deliberately not a verified drop."""

    material_id: str
    catalog_mob_id: str
    game_mob_id: str
    game_version: str
    observed_at: datetime
    inventory_delta: int


def _text(value, *, limit=128):
    return isinstance(value, str) and 0 < len(value) <= limit and bool(value.strip())


def _quantity(value):
    return type(value) is int and 0 <= value <= 9_999_999


def _image_name(value):
    if not _text(value) or value in (".", ".."):
        return False
    # No absolute paths, directory traversal, control characters or subfolders.
    return (Path(value).name == value
            and not any(char in value for char in ("/", "\\", ":", "\0"))
            and value.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))


def _hash_file(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("Missing, linked or oversized evidence file")
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_candidate(path, base, now):
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > MAX_MANIFEST_BYTES):
        raise ValueError("Unusable evidence manifest")
    data = read_static_json(path, max_bytes=MAX_MANIFEST_BYTES)
    if (
        type(data.get("schema_version")) is not int or data["schema_version"] != 1
        or data.get("status") != "REVIEWED"
        or data.get("independent_review") is not True
    ):
        raise ValueError("Unreviewed evidence metadata")
    material = data.get("material_id")
    catalog_mob = data.get("catalog_mob_id")
    game_mob = data.get("game_mob_id")
    game_version = data.get("game_version")
    if (not isinstance(material, str) or not SLUG.fullmatch(material)
            or not isinstance(catalog_mob, str) or not SLUG.fullmatch(catalog_mob)
            or not isinstance(game_mob, str) or not game_mob.isascii()
            or not game_mob.isdecimal() or len(game_mob) > 32
            or not _text(game_version, limit=32)
            or not _text(data.get("session_id"))):
        raise ValueError("Incomplete or ambiguous material/source identity")

    before, after = data.get("inventory_before"), data.get("inventory_after")
    if not _quantity(before) or not _quantity(after) or after <= before:
        raise ValueError("No positive inventory receipt")
    before_frame, after_frame = data.get("frame_before"), data.get("frame_after")
    if (not _text(before_frame) or not _text(after_frame)
            or before_frame == after_frame):
        raise ValueError("No distinct before/after observations")

    stamp = data.get("observed_at")
    if not _text(stamp, limit=40):
        raise ValueError("Missing observation timestamp")
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if observed.tzinfo is None:
        raise ValueError("Observation timestamp needs a timezone")
    age = now - observed.astimezone(timezone.utc)
    if not -FUTURE_TOLERANCE <= age <= MAX_AGE:
        raise ValueError("Stale or future-dated evidence")

    before_name = data.get("inventory_before_image")
    after_name = data.get("inventory_after_image")
    if (not _image_name(before_name) or not _image_name(after_name)
            or before_name == after_name):
        raise ValueError("Missing distinct inventory screenshots")
    hashes = data.get("evidence_sha256")
    if not isinstance(hashes, dict) or set(hashes) != {before_name, after_name}:
        raise ValueError("Evidence hash set must match exact observations")
    for name in (before_name, after_name):
        expected = hashes[name]
        if not isinstance(expected, str) or not HASH.fullmatch(expected):
            raise ValueError("Invalid SHA256 evidence digest")
        evidence_path = base / name
        if _hash_file(evidence_path) != expected:
            raise ValueError("Stale or changed local screenshot evidence")

    return ReceiptCandidate(
        material, catalog_mob, game_mob, game_version,
        observed.astimezone(timezone.utc), after - before,
    )


class FarmingEvidenceAudit:
    """Small time-bounded local cache. Never issues runtime or game input."""

    def __init__(self, directory=None, *, ttl_seconds=10.0, clock=time.monotonic):
        self.directory = Path(directory) if directory is not None else DEFAULT_EVIDENCE_DIR
        if type(ttl_seconds) not in (float, int) or not 0 <= ttl_seconds <= 60:
            raise ValueError("Invalid audit cache duration")
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._last_checked = None
        self._cached = None

    def _scan(self):
        base = self.directory
        try:
            if base.is_symlink() or (base.exists() and not base.is_dir()):
                return (), 1, True
            if not base.exists():
                return (), 0, False
            manifests = sorted(base.glob("*.json"))
        except OSError:
            return (), 1, True
        incomplete = len(manifests) > MAX_MANIFESTS
        rejected = 0
        candidates = []
        now = datetime.now(timezone.utc)
        for path in manifests[:MAX_MANIFESTS]:
            try:
                candidates.append(_load_candidate(path, base, now))
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                # Never leak local paths or untrusted fields through the UI.
                rejected += 1
        return tuple(candidates), rejected, incomplete

    def summary(self, material_id):
        if not isinstance(material_id, str) or not SLUG.fullmatch(material_id):
            raise ValueError("Unknown material")
        moment = self.clock()
        if (self._cached is None or self._last_checked is None
                or moment < self._last_checked
                or moment - self._last_checked >= self.ttl_seconds):
            self._cached = self._scan()
            self._last_checked = moment
        all_candidates, rejected, incomplete = self._cached
        matching = tuple(x for x in all_candidates if x.material_id == material_id)
        return {
            "material_id": material_id,
            "status": ("AUDIT_INCOMPLETE" if incomplete else
                       "LOCAL_CANDIDATES_ONLY" if matching else
                       "NO_LOCAL_RECEIPTS"),
            "receipt_candidate_count": len(matching),
            "rejected_manifest_count": rejected,
            "sources": [
                {
                    "catalog_mob_id": row.catalog_mob_id,
                    "game_mob_id": row.game_mob_id,
                    "game_version": row.game_version,
                    "inventory_delta": row.inventory_delta,
                    "evidence_level": "local_hash_match_only",
                }
                for row in matching
            ],
            "can_start": False,
            "note": (
                "Local hashes and reviewer flags are not independent proof of "
                "in-game drop identity, current-version readiness or a qualified route."
            ),
        }
