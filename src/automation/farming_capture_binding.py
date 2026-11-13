"""Internal bridge from retained frames to an immutable observation claim.

This binds *declared* private frame references to handoff frame IDs. A match
is only a prerequisite for local byte auditing, not proof of live game origin,
correct OCR, inventory gain, independent review or route authorization.
Neither this bridge nor the verifier can dispatch game input.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.automation.farming_capture_verify import verify_local_capture_claim
from src.automation.farming_live_handoff import (
    FarmingObservationHandoff, validate_observation_handoff_integrity,
)


_PRIVATE_NAME = re.compile(r"farm-frame-[A-Za-z0-9_-]{1,48}\.png\Z")
_MAX_AGE = timedelta(minutes=15)
_FUTURE_SKEW = timedelta(minutes=2)
_OBSERVATION_LAG = timedelta(minutes=2)
_MAX_PNG = 32 * 1024 * 1024


class FrameBindingBlocked(ValueError):
    """The frame references cannot be safely bound to this handoff."""


@dataclass(frozen=True)
class RetainedFrameBinding:
    packet_sha256: str
    private_frame_files: tuple[tuple[str, str], ...]

    def internal_frame_files(self) -> dict[str, str]:
        """Private verifier input only; never serialize into Qt/Web state."""
        return dict(self.private_frame_files)

    def public_summary(self) -> dict:
        return {
            "status": "PRIVATE_FRAME_REFERENCES_UNVERIFIED",
            "packet_sha256": self.packet_sha256,
            "frame_count": len(self.private_frame_files),
            "frame_bytes_verified": False,
            "game_origin_authenticated": False,
            "inventory_receipt_verified": False,
            "route_qualified": False,
            "can_start": False,
        }


def _utc(value: str, *, code: str) -> datetime:
    if type(value) is not str or len(value) > 40:
        raise FrameBindingBlocked(code)
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("naive timestamp")
        return timestamp.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise FrameBindingBlocked(code) from exc


def bind_retained_frame_files(
    packet: FarmingObservationHandoff,
    retained: dict[str, RetainedReadOnlySnapshot],
    *,
    now: datetime | None = None,
) -> RetainedFrameBinding:
    """Bind exact private frame IDs, digest, order and time to the handoff.

    Does not read disk: call verify_local_capture_claim afterwards to hash
    *original bytes*. In particular, an apparently valid retention record is
    not a screenshot provenance certificate or gameplay execution authority.
    """
    if type(packet) is not FarmingObservationHandoff:
        raise FrameBindingBlocked("HANDOFF_INVALID")
    if type(retained) is not dict or set(retained) != set(packet.frame_ids):
        raise FrameBindingBlocked("FRAME_IDS_MISMATCH")
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise FrameBindingBlocked("CLOCK_INVALID")
    now = now.astimezone(timezone.utc)
    observed = _utc(packet.observed_at_utc, code="OBSERVATION_TIME_INVALID")
    if not now - _MAX_AGE <= observed <= now + _FUTURE_SKEW:
        raise FrameBindingBlocked("OBSERVATION_STALE")
    # Preserve explicit clock/stale diagnostics before integrity revalidation.
    try:
        validate_observation_handoff_integrity(packet, now=now)
    except ValueError as exc:
        raise FrameBindingBlocked("HANDOFF_INTEGRITY_INVALID") from exc

    declared_hashes = dict(packet.frame_sha256)
    if set(declared_hashes) != set(packet.frame_ids):
        raise FrameBindingBlocked("FRAME_DIGESTS_INVALID")
    files = []
    previous_capture = None
    for frame_id in packet.frame_ids:
        record = retained[frame_id]
        if type(record) is not RetainedReadOnlySnapshot:
            raise FrameBindingBlocked("RETAINED_FRAME_INVALID")
        if (type(record.relative_path) is not str
                or not _PRIVATE_NAME.fullmatch(record.relative_path)
                or type(record.frame_sha256) is not str
                or record.frame_sha256 != declared_hashes[frame_id]
                or type(record.size_bytes) is not int
                or not 8 <= record.size_bytes <= _MAX_PNG):
            raise FrameBindingBlocked("RETAINED_FRAME_MISMATCH")
        captured = _utc(record.captured_at_utc, code="CAPTURE_TIME_INVALID")
        if not now - _MAX_AGE <= captured <= now + _FUTURE_SKEW:
            raise FrameBindingBlocked("CAPTURE_STALE")
        if not captured <= observed <= captured + _MAX_AGE:
            raise FrameBindingBlocked("CAPTURE_OBSERVATION_MISMATCH")
        if previous_capture is not None and captured <= previous_capture:
            raise FrameBindingBlocked("CAPTURE_ORDER_INVALID")
        previous_capture = captured
        files.append((frame_id, record.relative_path))
    if observed - previous_capture > _OBSERVATION_LAG:
        raise FrameBindingBlocked("CAPTURE_OBSERVATION_MISMATCH")
    if len({path for _, path in files}) != len(files):
        raise FrameBindingBlocked("AMBIGUOUS_PRIVATE_FRAMES")
    return RetainedFrameBinding(packet.record_sha256, tuple(files))


def verify_retained_capture_claim(
    packet: FarmingObservationHandoff,
    retained: dict[str, RetainedReadOnlySnapshot],
    *, source_root, evidence_root, binding_files: dict[str, str],
    now: datetime | None = None,
):
    """Verify actual local bytes after binding (still never authorization)."""
    now = datetime.now(timezone.utc) if now is None else now
    binding = bind_retained_frame_files(packet, retained, now=now)
    return verify_local_capture_claim(
        packet,
        source_root=source_root,
        evidence_root=evidence_root,
        frame_files=binding.internal_frame_files(),
        binding_files=binding_files,
        now=now,
    )
