"""Read-only handoff assembler for a Farming Assistant local review session.

Runs the existing in-memory session check AND original-byte audit in sequence.
The result is a private, path-free correlation record for later human review,
not an authenticated game observation or permission for gameplay input.
No game APIs, screenshot capture, controller, or UI actions are called here.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

from src.automation.farming_capture_binding import (
    FrameBindingBlocked, verify_retained_capture_claim,
)
from src.automation.farming_capture_session import (
    CaptureSessionBlocked, inspect_readonly_capture_session,
)
from src.automation.farming_live_handoff import (
    FarmingObservationHandoff, validate_observation_handoff_integrity,
)


class ReviewManifestBlocked(ValueError):
    """Review handoff was rejected. Never fall back to earlier evidence."""


@dataclass(frozen=True)
class ReadOnlyReviewManifest:
    """Immutable digest correlation. It is not a reviewer signature."""

    packet_sha256: str
    manifest_sha256: str
    observation_purpose: str
    frame_count: int
    checked_artifact_count: int

    def public_summary(self) -> dict:
        """Exclude private filenames, source paths, session IDs and quantities."""
        return {
            "status": "LOCAL_REVIEW_MANIFEST_ONLY",
            "packet_sha256": self.packet_sha256,
            "manifest_sha256": self.manifest_sha256,
            "frame_count": self.frame_count,
            "checked_artifact_count": self.checked_artifact_count,
            "local_bytes_match_claim": True,
            "game_origin_authenticated": False,
            "game_version_authenticated": False,
            "inventory_receipt_verified": False,
            "independent_review_complete": False,
            "route_qualified": False,
            "can_start": False,
            "note": (
                "Local capture representations and file bytes agree; "
                "the observation has not been independently authenticated."
            ),
        }


def prepare_readonly_review_manifest(
    packet: FarmingObservationHandoff,
    snapshots: dict,
    retained: dict,
    *,
    source_root,
    evidence_root,
    binding_files: dict[str, str],
    now: datetime | None = None,
) -> ReadOnlyReviewManifest:
    """Correlate a private observation, memory snapshots and original files.

    All paths must originate from the local trusted capture/reviewer adapter,
    never a material selector, Web/Qt form or imported user JSON. This method
    only reads existing evidence and never authorizes or dispatches farming.
    A successful local digest is still only a claim without attested origin,
    independent inventory OCR, current-game ID proof and route qualification.
    """
    if type(packet) is not FarmingObservationHandoff:
        raise ReviewManifestBlocked("HANDOFF_INVALID")
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ReviewManifestBlocked("CLOCK_INVALID")
    now = now.astimezone(timezone.utc)

    # Check the complete canonical observation before consuming its maps.
    try:
        validate_observation_handoff_integrity(packet, now=now)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReviewManifestBlocked("HANDOFF_INTEGRITY_INVALID") from exc

    try:
        session = inspect_readonly_capture_session(
            packet, snapshots, retained, now=now,
        )
    except (CaptureSessionBlocked, ValueError, TypeError) as exc:
        raise ReviewManifestBlocked("SESSION_INCOHERENT") from exc

    try:
        local = verify_retained_capture_claim(
            packet, retained, source_root=source_root,
            evidence_root=evidence_root, binding_files=binding_files, now=now,
        )
    except (FrameBindingBlocked, ValueError, TypeError) as exc:
        raise ReviewManifestBlocked("PRIVATE_BINDING_INVALID") from exc

    expected_count = (
        len(packet.source_sha256) + len(packet.bindings_sha256)
        + len(packet.frame_sha256)
    )
    if (session.packet_sha256 != packet.record_sha256
            or session.frame_count != len(packet.frame_ids)):
        raise ReviewManifestBlocked("SESSION_IDENTITY_MISMATCH")
    if local.status != "LOCAL_HASH_MATCH_ONLY":
        # Symbolic verifier code only; do not leak paths, bytes or private IDs.
        raise ReviewManifestBlocked("ORIGINAL_FILES_NOT_VERIFIED")
    if (local.packet_sha256 != packet.record_sha256
            or local.checked_artifact_count != expected_count):
        raise ReviewManifestBlocked("LOCAL_AUDIT_IDENTITY_MISMATCH")

    # This is an index of *local* consistency, not a cryptographic signature.
    # Deliberately omit raw frames, paths, private session IDs and quantities.
    record = {
        "schema_version": 1,
        "packet_sha256": packet.record_sha256,
        "purpose": packet.purpose,
        "frame_count": session.frame_count,
        "checked_artifact_count": local.checked_artifact_count,
        "local_audit_reason": local.reason_code,
    }
    manifest_sha = sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()
    return ReadOnlyReviewManifest(
        packet_sha256=packet.record_sha256,
        manifest_sha256=manifest_sha,
        observation_purpose=packet.purpose,
        frame_count=session.frame_count,
        checked_artifact_count=local.checked_artifact_count,
    )
