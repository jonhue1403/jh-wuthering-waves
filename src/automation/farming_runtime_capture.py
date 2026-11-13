"""Opt-in, read-only OK Script frame snapshot for later independent qualification.

Uses the existing task.next_frame()/task.frame and the attached game HWND.
It never calls a game input, task dispatch, inventory OCR, or a route executor.
A successful snapshot is NOT an authenticated game observation, does not
establish frame freshness or the installed game version, and cannot authorize
farming. Snapshot bytes remain private to the local reviewer workflow.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import re
import sys


_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\Z")
_MAX_DIMENSION = 4096
_MAX_PIXELS = 4096 * 2160
_MAX_ENCODED_BYTES = 32 * 1024 * 1024


class CaptureBlocked(ValueError):
    """No screenshot was accepted; the caller must not fall back to cached data."""


@dataclass(frozen=True)
class ReadOnlyFrameSnapshot:
    captured_at_utc: str
    runtime_version: str
    width: int
    height: int
    frame_sha256: str
    frame_png: bytes = field(repr=False)

    def public_summary(self) -> dict:
        """No image, HWND, paths, session keys, or approval state in UI output."""
        return {
            "status": "READ_ONLY_FRAME_PENDING_INDEPENDENT_REVIEW",
            "captured_at_utc": self.captured_at_utc,
            "runtime_version": self.runtime_version,
            "width": self.width,
            "height": self.height,
            "frame_sha256": self.frame_sha256,
            "frame_freshness_verified": False,
            "game_version_observed": False,
            "inventory_receipt_verified": False,
            "route_qualified": False,
            "can_start": False,
        }


def _system_foreground_hwnd():
    if sys.platform != "win32":
        raise CaptureBlocked("FOREGROUND_CHECK_UNAVAILABLE")
    try:
        import win32gui
        return win32gui.GetForegroundWindow()
    except (ImportError, OSError) as exc:
        raise CaptureBlocked("FOREGROUND_CHECK_UNAVAILABLE") from exc


def capture_readonly_frame(task, *, opted_in=False) -> ReadOnlyFrameSnapshot:
    """Snapshot a foreground OK Script task's frame without issuing game inputs.

    Internal, explicit opt-in only; not a task-tab action. The default focus
    provider checks the real Win32 foreground window. Unit tests replace the
    system-check function using unittest.mock; callers cannot supply a bypass.
    This reads
    actual OK Script task.next_frame() and task.frame when run inside the
    authorized task runtime, but cannot prove that a backend returned a fresh
    uncached frame. Never convert this result into RuntimeQualification.
    """
    if opted_in is not True:
        raise CaptureBlocked("CAPTURE_REQUIRES_EXPLICIT_OPT_IN")
    try:
        window = task.executor.device_manager.hwnd_window
        hwnd = window.hwnd
        next_frame = task.next_frame
        cancelled = task.cancelled
    except AttributeError as exc:
        raise CaptureBlocked("OK_SCRIPT_RUNTIME_UNAVAILABLE") from exc
    if type(hwnd) is not int or hwnd <= 0 or not callable(next_frame) or not callable(cancelled):
        raise CaptureBlocked("OK_SCRIPT_RUNTIME_UNAVAILABLE")
    checker = _system_foreground_hwnd

    def guard():
        if cancelled():
            raise CaptureBlocked("CAPTURE_CANCELLED")
        try:
            focus = checker()
        except Exception as exc:
            raise CaptureBlocked("FOREGROUND_CHECK_UNAVAILABLE") from exc
        if type(focus) is not int or focus != hwnd or window.hwnd != hwnd:
            raise CaptureBlocked("GAME_NOT_FOREGROUND")

    guard()
    # next_frame() is the project's existing read-only capture primitive.
    # Avoid task.wait()/sleep()/ocr() and ALL input-facing task methods here.
    next_frame()
    guard()

    import cv2
    import numpy as np

    frame = task.frame
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
            or frame.ndim != 3 or frame.shape[2] not in (3, 4)
            or not 1 <= frame.shape[0] <= _MAX_DIMENSION
            or not 1 <= frame.shape[1] <= _MAX_DIMENSION
            or frame.shape[0] * frame.shape[1] > _MAX_PIXELS):
        raise CaptureBlocked("INVALID_FRAME_BUFFER")
    # Copy immediately: the OK Script capture buffer may be reused next frame.
    private_copy = np.ascontiguousarray(frame).copy()
    encoded_ok, encoded = cv2.imencode(".png", private_copy)
    if not encoded_ok or encoded.size > _MAX_ENCODED_BYTES:
        raise CaptureBlocked("FRAME_ENCODING_REJECTED")
    guard()
    try:
        installed = version("ok-script")
    except Exception as exc:
        raise CaptureBlocked("RUNTIME_VERSION_UNAVAILABLE") from exc
    if type(installed) is not str or not _VERSION.fullmatch(installed):
        raise CaptureBlocked("RUNTIME_VERSION_UNAVAILABLE")
    data = encoded.tobytes()
    return ReadOnlyFrameSnapshot(
        captured_at_utc=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        runtime_version=installed,
        width=private_copy.shape[1],
        height=private_copy.shape[0],
        frame_sha256=sha256(data).hexdigest(),
        frame_png=data,
    )
