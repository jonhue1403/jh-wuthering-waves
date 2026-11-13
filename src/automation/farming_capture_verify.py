"""Read-only local artifact verification for Farming Assistant capture claims.

This adapter inspects *bytes on disk*, not just declared SHA256 strings. A
matching result is local integrity only: it does not authenticate a game frame,
inventory OCR, enemy ID, installed version, independent review or a live route.
It never dispatches tasks, captures the screen, or requests game input.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import re

from src.automation.farming_live_handoff import (
    FarmingObservationHandoff, validate_observation_handoff_integrity,
)


_RELATIVE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
_MAX_FRAME = 32 * 1024 * 1024
_MAX_BINDING = 256 * 1024 * 1024
_MAX_SOURCE = 8 * 1024 * 1024
_MAX_AGE = timedelta(minutes=15)
_FUTURE_SKEW = timedelta(minutes=2)


class _AuditFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LocalCaptureAudit:
    status: str
    reason_code: str
    checked_artifact_count: int
    packet_sha256: str

    def public_summary(self) -> dict:
        """No paths, raw frames, local session IDs or misleading approval."""
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "checked_artifact_count": self.checked_artifact_count,
            "packet_sha256": self.packet_sha256,
            "evidence_authenticated": False,
            "independent_review_complete": False,
            "route_qualified": False,
            "can_start": False,
            "note": (
                "Local bytes match the capture claim; game origin and runtime "
                "qualification still require independent review."
                if self.status == "LOCAL_HASH_MATCH_ONLY" else
                "Local capture artifacts could not be integrity-verified."
            ),
        }


def _root(path):
    if not isinstance(path, (str, Path)) or isinstance(path, bool):
        raise _AuditFailure("LOCAL_ROOT_INVALID")
    base = Path(path)
    if base.is_symlink() or not base.is_dir():
        raise _AuditFailure("LOCAL_ROOT_INVALID")
    try:
        return base.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _AuditFailure("LOCAL_ROOT_INVALID") from None


def _safe_file(base: Path, relative: str) -> Path:
    if type(relative) is not str or not _RELATIVE.fullmatch(relative):
        raise _AuditFailure("UNSAFE_LOCAL_PATH")
    parts = relative.split("/")
    if any(part in (".", "..") for part in parts):
        raise _AuditFailure("UNSAFE_LOCAL_PATH")
    current = base
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise _AuditFailure("UNSAFE_LOCAL_PATH")
    try:
        resolved = current.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _AuditFailure("LOCAL_ARTIFACT_MISSING") from None
    if not resolved.is_relative_to(base):
        raise _AuditFailure("UNSAFE_LOCAL_PATH")
    if not resolved.is_file():
        raise _AuditFailure("LOCAL_ARTIFACT_MISSING")
    return resolved


def _file_digest(base: Path, relative: str, size_limit: int) -> str:
    path = _safe_file(base, relative)
    try:
        if path.stat().st_size > size_limit:
            raise _AuditFailure("LOCAL_ARTIFACT_TOO_LARGE")
        digest = sha256()
        total = 0
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                total += len(block)
                if total > size_limit:
                    raise _AuditFailure("LOCAL_ARTIFACT_TOO_LARGE")
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        raise _AuditFailure("LOCAL_ARTIFACT_UNREADABLE") from None


def _paths(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise _AuditFailure("ARTIFACT_MAP_INVALID")
    if any(type(k) is not str or type(v) is not str for k, v in value.items()):
        raise _AuditFailure("ARTIFACT_MAP_INVALID")
    if len(set(value.values())) != len(value):
        raise _AuditFailure("ARTIFACT_MAP_AMBIGUOUS")
    return value


def verify_local_capture_claim(
    packet: FarmingObservationHandoff,
    *,
    source_root,
    evidence_root,
    frame_files: dict[str, str],
    binding_files: dict[str, str],
    now: datetime | None = None,
) -> LocalCaptureAudit:
    """Compare declared hashes with actual files under two trusted local roots.

    The two file maps must be produced by internal capture code, never a
    user-facing path entry. Source names are fixed by the validated packet.
    All source, binding and frame hashes must match. Even success does NOT
    mark the packet reviewed or grant any executor authority.
    """
    if type(packet) is not FarmingObservationHandoff:
        raise TypeError("Expected an immutable FarmingObservationHandoff")
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Verification clock must be timezone aware")
    checked = 0
    try:
        validate_observation_handoff_integrity(packet, now=now)
    except ValueError:
        # Do not inspect attacker-supplied filenames from an invalid packet.
        # Its advertised packet hash is not a verified identity.
        return LocalCaptureAudit("REJECTED", "HANDOFF_INTEGRITY_INVALID", 0, "")
    try:
        observed = datetime.fromisoformat(packet.observed_at_utc)
        utc = now.astimezone(timezone.utc)
        if not utc - _MAX_AGE <= observed <= utc + _FUTURE_SKEW:
            raise _AuditFailure("CAPTURE_CLAIM_STALE")
        sources = _root(source_root)
        evidence = _root(evidence_root)
        frames = _paths(frame_files, packet.frame_ids)
        bindings = _paths(binding_files, (key for key, _ in packet.bindings_sha256))
        for name, expected in packet.source_sha256:
            if _file_digest(sources, name, _MAX_SOURCE) != expected:
                raise _AuditFailure("LOCAL_HASH_MISMATCH")
            checked += 1
        for name, expected in packet.bindings_sha256:
            if _file_digest(evidence, bindings[name], _MAX_BINDING) != expected:
                raise _AuditFailure("LOCAL_HASH_MISMATCH")
            checked += 1
        for name, expected in packet.frame_sha256:
            if _file_digest(evidence, frames[name], _MAX_FRAME) != expected:
                raise _AuditFailure("LOCAL_HASH_MISMATCH")
            checked += 1
    except _AuditFailure as exc:
        return LocalCaptureAudit("REJECTED", exc.code, 0, packet.record_sha256)
    return LocalCaptureAudit(
        "LOCAL_HASH_MATCH_ONLY", "LOCAL_BYTES_MATCH_DECLARED_SHA256",
        checked, packet.record_sha256,
    )
