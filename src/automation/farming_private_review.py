"""Internal-only bridge from opt-in private captures to offline review manifest.

A trusted local reviewer supplies the already-built, immutable observation
claim and private roots. This module never captures a screen, builds a
SOURCE_DROP claim, accepts operator paths, invokes an executor or grants Start.
A file hash match is not proof of game origin, drop receipt or route readiness.
"""

from datetime import datetime

from src.automation.farming_live_handoff import FarmingObservationHandoff
from src.automation.farming_private_capture import PrivateReadOnlyCapture
from src.automation.farming_review_manifest import (
    ReadOnlyReviewManifest, ReviewManifestBlocked, prepare_readonly_review_manifest,
)


class PrivateReviewBlocked(ValueError):
    """No qualified review manifest; never reuse an earlier capture."""


def review_private_captures(
    packet: FarmingObservationHandoff,
    captures: dict[str, PrivateReadOnlyCapture],
    *,
    source_root,
    evidence_root,
    binding_files: dict[str, str],
    now: datetime | None = None,
) -> ReadOnlyReviewManifest:
    """Audit original bytes for a trusted, opt-in private capture session.

    A complete mapping keyed by exact packet frame IDs is required. Extracting
    snapshot and retention metadata together prevents callers from accidentally
    pairing separately sourced in-memory and on-disk capture references. The
    downstream session/byte verifier independently rechecks every claim.

    The caller MUST obtain source_root, evidence_root and binding_files from
    trusted private local configuration, never from the public selector or an
    imported hunt/route plan. No result here can authorize game input.
    """
    if type(packet) is not FarmingObservationHandoff:
        raise PrivateReviewBlocked("HANDOFF_INVALID")
    if type(captures) is not dict or set(captures) != set(packet.frame_ids):
        raise PrivateReviewBlocked("CAPTURE_FRAME_IDS_MISMATCH")

    snapshots = {}
    retained = {}
    seen_captures = set()
    for frame_id in packet.frame_ids:
        record = captures[frame_id]
        if type(record) is not PrivateReadOnlyCapture:
            raise PrivateReviewBlocked("PRIVATE_CAPTURE_INVALID")
        if id(record) in seen_captures:
            raise PrivateReviewBlocked("DUPLICATE_PRIVATE_CAPTURE")
        seen_captures.add(id(record))
        snapshots[frame_id] = record.snapshot
        retained[frame_id] = record.retained

    try:
        return prepare_readonly_review_manifest(
            packet, snapshots, retained,
            source_root=source_root,
            evidence_root=evidence_root,
            binding_files=binding_files,
            now=now,
        )
    except (ReviewManifestBlocked, ValueError, TypeError, AttributeError) as exc:
        # Preserve a safe diagnostic without leaking paths, frame bytes or
        # source/profile contents through a user-visible exception message.
        raise PrivateReviewBlocked("PRIVATE_REVIEW_NOT_QUALIFIED") from exc
