"""Opt-in read-only capture -> private retention for future offline review.

This is an INTERNAL adapter, not an OK Script task registration or UI action.
The private_root must come from trusted local reviewer configuration, never
from an operator form or imported route/profile JSON. It neither builds an
observation packet nor authorizes farming, navigation or inventory claims.
"""

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import secrets

from src.automation.farming_runtime_capture import (
    CaptureBlocked, ReadOnlyFrameSnapshot, capture_readonly_frame,
)
from src.automation.farming_capture_retention import (
    RetainedReadOnlySnapshot, SnapshotRetentionBlocked, retain_readonly_snapshot,
)


class PrivateCaptureBlocked(ValueError):
    """No reviewable capture result. Never fall back to old screenshots."""


@dataclass(frozen=True)
class PrivateReadOnlyCapture:
    """Internal immutable frame/retention pair, NOT a verified observation."""

    snapshot: ReadOnlyFrameSnapshot = field(repr=False)
    retained: RetainedReadOnlySnapshot = field(repr=False)

    def public_summary(self) -> dict:
        """Avoid leaking PNG bytes, private path/token or runtime handles."""
        return {
            "status": "PRIVATE_FRAME_PENDING_INDEPENDENT_REVIEW",
            "frame_sha256": self.snapshot.frame_sha256,
            "size_bytes": self.retained.size_bytes,
            "frame_origin_authenticated": False,
            "frame_freshness_verified": False,
            "game_version_authenticated": False,
            "inventory_receipt_verified": False,
            "route_qualified": False,
            "can_start": False,
        }


def capture_private_readonly_evidence(
    task, *, private_root, opted_in=False, now: datetime | None = None,
) -> PrivateReadOnlyCapture:
    """Capture one foreground frame and retain exact PNG bytes privately.

    No paths/tokens are accepted from the public Farming Assistant selector.
    An unpredictable token is generated inside this adapter. The underlying
    capture code checks cancellation and focus; the retention code validates
    age, content digest, exclusive creation and private root safety.
    The caller must independently qualify actual game identity and freshness.
    """
    if opted_in is not True:
        raise PrivateCaptureBlocked("EXPLICIT_CAPTURE_OPT_IN_REQUIRED")
    if now is not None and (
        not isinstance(now, datetime) or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise PrivateCaptureBlocked("CLOCK_INVALID")
    try:
        snapshot = capture_readonly_frame(task, opted_in=True)
    except CaptureBlocked as exc:
        raise PrivateCaptureBlocked("FOREGROUND_CAPTURE_FAILED") from exc
    if type(snapshot) is not ReadOnlyFrameSnapshot:
        raise PrivateCaptureBlocked("CAPTURE_CONTRACT_INVALID")
    try:
        retained = retain_readonly_snapshot(
            snapshot,
            private_root=private_root,
            capture_token=secrets.token_hex(16),
            opted_in=True,
            now=now,
        )
    except SnapshotRetentionBlocked as exc:
        raise PrivateCaptureBlocked("PRIVATE_RETENTION_FAILED") from exc
    if (type(retained) is not RetainedReadOnlySnapshot
            or retained.frame_sha256 != snapshot.frame_sha256
            or retained.captured_at_utc != snapshot.captured_at_utc
            or type(snapshot.frame_png) is not bytes
            or retained.size_bytes != len(snapshot.frame_png)
            or sha256(snapshot.frame_png).hexdigest() != snapshot.frame_sha256):
        # A mismatched storage receipt must NEVER be used as review evidence.
        # Do not delete unknown files automatically; require local quarantine.
        raise PrivateCaptureBlocked("CAPTURE_RETENTION_CONTRACT_MISMATCH")
    return PrivateReadOnlyCapture(snapshot=snapshot, retained=retained)
