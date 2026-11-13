"""Private, opt-in retention of a read-only Farming Assistant PNG snapshot.

This stores local bytes for later human review; it does not authenticate game
origin, prove freshness of a frame source, or authorize an executor. The root
must be a dedicated, access-controlled local evidence directory, NOT the repo.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import re

from src.automation.farming_runtime_capture import ReadOnlyFrameSnapshot


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_BYTES = 32 * 1024 * 1024
_MAX_AGE = timedelta(minutes=15)
_FUTURE_SKEW = timedelta(minutes=2)


class SnapshotRetentionBlocked(ValueError):
    """The snapshot was not accepted as a durable private artifact."""


@dataclass(frozen=True)
class RetainedReadOnlySnapshot:
    """Private file reference, not an execution qualification."""

    relative_path: str
    captured_at_utc: str
    frame_sha256: str
    size_bytes: int

    def public_summary(self) -> dict:
        return {
            "status": "PRIVATE_CAPTURE_PENDING_INDEPENDENT_REVIEW",
            "frame_sha256": self.frame_sha256,
            "size_bytes": self.size_bytes,
            "origin_authenticated": False,
            "frame_freshness_verified": False,
            "route_qualified": False,
            "can_start": False,
        }


def _private_root(value) -> Path:
    if not isinstance(value, (str, Path)) or isinstance(value, bool):
        raise SnapshotRetentionBlocked("PRIVATE_ROOT_INVALID")
    path = Path(value)
    if not path.is_absolute():
        raise SnapshotRetentionBlocked("PRIVATE_ROOT_INVALID")
    # Reject junctions/reparse redirection as well as POSIX symlinks.
    for ancestor in (path, *path.parents):
        try:
            if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
                raise SnapshotRetentionBlocked("PRIVATE_ROOT_UNSAFE")
        except OSError as exc:
            raise SnapshotRetentionBlocked("PRIVATE_ROOT_UNSAFE") from exc
    if not path.is_dir():
        raise SnapshotRetentionBlocked("PRIVATE_ROOT_INVALID")
    return path


def _check_snapshot(snapshot, now):
    if type(snapshot) is not ReadOnlyFrameSnapshot:
        raise SnapshotRetentionBlocked("SNAPSHOT_INVALID")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise SnapshotRetentionBlocked("CLOCK_INVALID")
    try:
        captured = datetime.fromisoformat(snapshot.captured_at_utc)
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError("naive")
        captured = captured.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SnapshotRetentionBlocked("SNAPSHOT_TIMESTAMP_INVALID") from exc
    now = now.astimezone(timezone.utc)
    if not now - _MAX_AGE <= captured <= now + _FUTURE_SKEW:
        raise SnapshotRetentionBlocked("SNAPSHOT_STALE")
    data = snapshot.frame_png
    if (type(data) is not bytes or not len(_PNG_SIGNATURE) <= len(data) <= _MAX_BYTES
            or not data.startswith(_PNG_SIGNATURE)
            or type(snapshot.width) is not int or type(snapshot.height) is not int
            or snapshot.width <= 0 or snapshot.height <= 0
            or type(snapshot.frame_sha256) is not str
            or sha256(data).hexdigest() != snapshot.frame_sha256):
        raise SnapshotRetentionBlocked("SNAPSHOT_BYTES_INVALID")
    return data


def retain_readonly_snapshot(
    snapshot: ReadOnlyFrameSnapshot, *, private_root, capture_token: str,
    opted_in=False, now: datetime | None = None,
) -> RetainedReadOnlySnapshot:
    """Write exactly one new private PNG; never overwrite existing evidence.

    The caller supplies a pre-provisioned access-controlled directory outside
    the repository and a private, unique opaque capture token. This method
    never creates directories, updates a catalog, or enables gameplay input.
    The root is trusted against concurrent hostile filesystem mutation.
    """
    if opted_in is not True:
        raise SnapshotRetentionBlocked("RETENTION_REQUIRES_EXPLICIT_OPT_IN")
    if type(capture_token) is not str or not _TOKEN.fullmatch(capture_token):
        raise SnapshotRetentionBlocked("CAPTURE_TOKEN_INVALID")
    data = _check_snapshot(snapshot, datetime.now(timezone.utc) if now is None else now)
    root = _private_root(private_root)
    relative = f"farm-frame-{capture_token}.png"
    destination = root / relative
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise SnapshotRetentionBlocked("CAPTURE_ALREADY_EXISTS") from exc
    except OSError as exc:
        raise SnapshotRetentionBlocked("CAPTURE_WRITE_FAILED") from exc
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        # Read back from disk: the returned digest is not a mere write claim.
        with destination.open("rb") as check:
            stored = check.read(_MAX_BYTES + 1)
        if stored != data:
            raise SnapshotRetentionBlocked("CAPTURE_READBACK_MISMATCH")
    except Exception as exc:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, SnapshotRetentionBlocked):
            raise
        raise SnapshotRetentionBlocked("CAPTURE_WRITE_FAILED") from exc
    return RetainedReadOnlySnapshot(
        relative, snapshot.captured_at_utc, snapshot.frame_sha256, len(data),
    )
