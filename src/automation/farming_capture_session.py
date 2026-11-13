"""Read-only in-memory coherence check for a private farming capture session.

This checks the *same bytes* crossing snapshot, retention metadata, and the
immutable handoff. It does not establish game origin, real-time frame freshness,
correct inventory OCR, game version, independent review, or executor permission.
No input, filesystem, network, or game APIs are called here.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from src.automation.farming_capture_binding import (
    FrameBindingBlocked, bind_retained_frame_files,
)
from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.automation.farming_runtime_capture import ReadOnlyFrameSnapshot
from src.automation.farming_live_handoff import (
    FarmingObservationHandoff, validate_observation_handoff_integrity,
)

_PNG = b"\x89PNG\r\n\x1a\n"
_MAX_IMAGE_BYTES = 32 * 1024 * 1024
_MAX_DIMENSION = 4096
_MAX_PIXELS = 4096 * 2160


class CaptureSessionBlocked(ValueError):
    """Inconsistent private capture claim. Never fall back to cached data."""


@dataclass(frozen=True)
class ReadOnlyCaptureSessionAudit:
    packet_sha256: str
    frame_count: int

    def public_summary(self) -> dict:
        return {
            "status": "LOCAL_SESSION_COHERENT_ONLY",
            "packet_sha256": self.packet_sha256,
            "frame_count": self.frame_count,
            "actual_frame_freshness_verified": False,
            "game_origin_authenticated": False,
            "game_version_authenticated": False,
            "original_files_verified": False,
            "inventory_receipt_verified": False,
            "independent_review_complete": False,
            "route_qualified": False,
            "can_start": False,
        }


def _utc(value: str) -> datetime:
    if type(value) is not str or len(value) > 40:
        raise CaptureSessionBlocked("CAPTURE_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise CaptureSessionBlocked("CAPTURE_TIMESTAMP_INVALID") from exc


def inspect_readonly_capture_session(
    packet: FarmingObservationHandoff,
    snapshots: dict[str, ReadOnlyFrameSnapshot],
    retained: dict[str, RetainedReadOnlySnapshot],
    *,
    now: datetime | None = None,
) -> ReadOnlyCaptureSessionAudit:
    """Check private in-memory frame continuity before original-file auditing.

    Caller-held snapshots and retention records must match exact packet frame
    IDs, bytes, hashes, capture instants, and the *claimed* OK Script version.
    bind_retained_frame_files separately checks retention chronology and
    bounded observation lag. No result from this function authorizes farming.
    """
    if type(packet) is not FarmingObservationHandoff:
        raise CaptureSessionBlocked("HANDOFF_INVALID")
    if type(snapshots) is not dict or set(snapshots) != set(packet.frame_ids):
        raise CaptureSessionBlocked("SNAPSHOT_IDS_MISMATCH")
    if type(retained) is not dict or set(retained) != set(packet.frame_ids):
        raise CaptureSessionBlocked("RETAINED_IDS_MISMATCH")
    now = datetime.now(timezone.utc) if now is None else now
    try:
        validate_observation_handoff_integrity(packet, now=now)
    except ValueError as exc:
        raise CaptureSessionBlocked("HANDOFF_INTEGRITY_INVALID") from exc
    try:
        bind_retained_frame_files(packet, retained, now=now)
    except FrameBindingBlocked as exc:
        raise CaptureSessionBlocked("RETAINED_BINDING_INVALID") from exc
    expected = dict(packet.frame_sha256)
    dimensions = None
    for frame_id in packet.frame_ids:
        image = snapshots[frame_id]
        record = retained[frame_id]
        if type(image) is not ReadOnlyFrameSnapshot:
            raise CaptureSessionBlocked("SNAPSHOT_INVALID")
        data = image.frame_png
        if (type(data) is not bytes or not _PNG == data[:len(_PNG)]
                or not len(_PNG) <= len(data) <= _MAX_IMAGE_BYTES):
            raise CaptureSessionBlocked("SNAPSHOT_BYTES_INVALID")
        if (type(image.width) is not int or type(image.height) is not int
                or not 1 <= image.width <= _MAX_DIMENSION
                or not 1 <= image.height <= _MAX_DIMENSION
                or image.width * image.height > _MAX_PIXELS):
            raise CaptureSessionBlocked("SNAPSHOT_DIMENSIONS_INVALID")
        current_dimensions = (image.width, image.height)
        if dimensions is not None and dimensions != current_dimensions:
            raise CaptureSessionBlocked("RESOLUTION_CHANGED")
        dimensions = current_dimensions
        if type(image.runtime_version) is not str or image.runtime_version != packet.ok_script_version:
            raise CaptureSessionBlocked("RUNTIME_VERSION_MISMATCH")
        if _utc(image.captured_at_utc) != _utc(record.captured_at_utc):
            raise CaptureSessionBlocked("CAPTURE_TIMESTAMP_MISMATCH")
        digest = sha256(data).hexdigest()
        if (type(image.frame_sha256) is not str
                or digest != image.frame_sha256
                or digest != record.frame_sha256
                or digest != expected[frame_id]
                or len(data) != record.size_bytes):
            raise CaptureSessionBlocked("SNAPSHOT_DIGEST_MISMATCH")
    return ReadOnlyCaptureSessionAudit(packet.record_sha256, len(packet.frame_ids))
