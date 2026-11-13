"""Immutable review handoff for current-runtime Farming Assistant observations.

This is a *capture claim*, not authenticated evidence. It checks structural
consistency, binds declared digests, and makes a reproducible packet identity.
It performs no filesystem, camera, game, controller, reviewer, or network I/O.
Neither the SHA256 packet digest nor a 'current runtime' claim grants authority:
Codex and an independent reviewer must inspect originals and run existing
RuntimeQualification.assert_compatible before any executor integration.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re

from src.overworld.qualification import REQUIRED_SOURCES, STAGES


_TOKEN = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")
_TARGET = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
_NUMBER_ID = re.compile(r"[0-9]{1,32}\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ROOT_FIELDS = frozenset((
    "schema_version", "purpose", "target_kind", "target_id", "game_mob_id",
    "game_version", "ok_script_version", "session_id", "observed_at",
    "stage", "route_id", "state_id", "floor_id", "frame_ids",
    "frame_sha256", "bindings_sha256", "source_sha256",
    "inventory_before", "inventory_after",
))
_PURPOSES = frozenset(("SOURCE_DROP", "ROUTE_SURVEY", "RUNTIME_PREFLIGHT"))
_MAX_AGE = timedelta(minutes=15)
_FUTURE_SKEW = timedelta(minutes=2)
_BASE_BINDINGS = frozenset(("profile", "reference", "database"))


def _token(value):
    return type(value) is str and _TOKEN.fullmatch(value) is not None


def _digest_map(value, *, required, optional=frozenset()):
    if (type(value) is not dict or not set(required).issubset(value)
            or set(value) - set(required) - set(optional)):
        raise ValueError("Missing or unexpected observation digest labels")
    for name, digest in value.items():
        if type(name) is not str or type(digest) is not str or not _SHA.fullmatch(digest):
            raise ValueError("Invalid observation digest")
    return tuple(sorted(value.items()))


def _timestamp(value, now):
    if type(value) is not str or len(value) > 40:
        raise ValueError("Invalid observation timestamp")
    try:
        captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid observation timestamp") from exc
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("Observation must include a timezone")
    utc = captured.astimezone(timezone.utc)
    if not now - _MAX_AGE <= utc <= now + _FUTURE_SKEW:
        raise ValueError("Observation is stale or in the future")
    return utc.isoformat(timespec="microseconds")


@dataclass(frozen=True)
class FarmingObservationHandoff:
    """Frozen, structurally valid review packet; *never* live permission."""

    purpose: str
    target_kind: str
    target_id: str
    game_mob_id: str
    game_version: str
    ok_script_version: str
    session_id: str
    observed_at_utc: str
    stage: str
    route_id: str
    state_id: str
    floor_id: str
    frame_ids: tuple[str, ...]
    frame_sha256: tuple[tuple[str, str], ...]
    bindings_sha256: tuple[tuple[str, str], ...]
    source_sha256: tuple[tuple[str, str], ...]
    inventory_before: int | None
    inventory_after: int | None
    record_sha256: str

    def public_summary(self) -> dict:
        """Path-free display metadata. No frames, private IDs or file paths."""
        return {
            "status": "CAPTURE_CLAIM_PENDING_INDEPENDENT_REVIEW",
            "purpose": self.purpose,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "stage": self.stage,
            "frame_count": len(self.frame_ids),
            "packet_sha256": self.record_sha256,
            "current_version_authenticated": False,
            "source_verified": False,
            "route_qualified": False,
            "reviewer_authenticated": False,
            "can_start": False,
            "note": "A consistent capture claim is not an independently verified game observation.",
        }


def build_observation_handoff(payload: dict, *, now: datetime | None = None) -> FarmingObservationHandoff:
    """Validate a single short-lived observation claim for later local review.

    This API is intentionally NOT a task_tab_action or user-provided JSON
    upload. Only a future trusted capture adapter should construct a packet.
    Do not feed its fields to the FarmingCatalog execution callbacks.
    """
    if type(payload) is not dict or set(payload) != _ROOT_FIELDS:
        raise ValueError("Missing or unexpected observation fields")
    if payload["schema_version"] != 1 or type(payload["schema_version"]) is not int:
        raise ValueError("Unknown observation schema")
    purpose = payload["purpose"]
    kind = payload["target_kind"]
    stage = payload["stage"]
    if (type(purpose) is not str or purpose not in _PURPOSES
            or type(kind) is not str or kind not in ("material", "mob")
            or type(stage) is not str or stage not in STAGES):
        raise ValueError("Unknown observation purpose, target or stage")
    if purpose == "SOURCE_DROP" and (kind != "material" or stage not in ("SINGLE_CAMP", "MATERIAL_ROUTE")):
        raise ValueError("Material receipt must come from a bounded encounter")
    if purpose == "ROUTE_SURVEY" and stage not in ("WALK", "SINGLE_CAMP", "MATERIAL_ROUTE"):
        raise ValueError("Route observation must use a bounded route stage")

    target = payload["target_id"]
    game_id = payload["game_mob_id"]
    route = payload["route_id"]
    if (type(target) is not str or not _TARGET.fullmatch(target)
            or type(game_id) is not str or not _NUMBER_ID.fullmatch(game_id)
            or (route != "" and not _token(route))
            or type(route) is not str
            or (purpose == "ROUTE_SURVEY" and not route)
            or not _token(payload["session_id"])
            or not _token(payload["state_id"])
            or not _token(payload["floor_id"])):
        raise ValueError("Unusable observation identity or route")
    for field in ("game_version", "ok_script_version"):
        value = payload[field]
        if type(value) is not str or not _VERSION.fullmatch(value):
            raise ValueError("Missing observed version claim")
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Comparison clock must be timezone aware")
    now = now.astimezone(timezone.utc)
    when = _timestamp(payload["observed_at"], now)

    frames = payload["frame_ids"]
    if (type(frames) not in (tuple, list) or not 1 <= len(frames) <= 4
            or any(not _token(frame) for frame in frames)
            or len(set(frames)) != len(frames)):
        raise ValueError("Missing, duplicate or invalid frame IDs")
    if purpose == "SOURCE_DROP" and len(frames) != 2:
        raise ValueError("Material receipt requires distinct before/after frames")
    frame_hashes = _digest_map(payload["frame_sha256"], required=set(frames))
    if len(frame_hashes) != len(frames):
        raise ValueError("Frame digests do not match observed frames")
    bindings = _digest_map(
        payload["bindings_sha256"], required=_BASE_BINDINGS,
        optional=frozenset(("matcher_calibration",)),
    )
    required_sources = set(REQUIRED_SOURCES)
    if stage in ("MATERIAL_ROUTE", "BEACON"):
        required_sources.update((
            "src/overworld/material_route.py", "src/task/BoundedRouteTask.py",
        ))
    sources = _digest_map(payload["source_sha256"], required=required_sources)
    before, after = payload["inventory_before"], payload["inventory_after"]
    if purpose == "SOURCE_DROP":
        if (type(before) is not int or type(after) is not int
                or not 0 <= before < after <= 9_999_999):
            raise ValueError("Material receipt requires a positive inventory delta")
    elif before is not None or after is not None:
        raise ValueError("Non-receipt observation cannot claim inventory gain")

    canonical = {
        **{key: payload[key] for key in (
            "schema_version", "purpose", "target_kind", "target_id",
            "game_mob_id", "game_version", "ok_script_version", "session_id",
            "stage", "route_id", "state_id", "floor_id",
            "inventory_before", "inventory_after",
        )},
        "observed_at": when,
        "frame_ids": list(frames),
        "frame_sha256": dict(frame_hashes),
        "bindings_sha256": dict(bindings),
        "source_sha256": dict(sources),
    }
    digest = sha256(json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()
    return FarmingObservationHandoff(
        purpose, kind, target, game_id, payload["game_version"],
        payload["ok_script_version"], payload["session_id"], when,
        stage, route, payload["state_id"], payload["floor_id"],
        tuple(frames), frame_hashes, bindings, sources, before, after, digest,
    )
