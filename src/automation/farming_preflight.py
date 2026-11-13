"""Non-authorizing, version-aware calibration checklist for Farming Assistant.

This module consumes only read-only historical summaries. It never loads the
game, a runtime sidecar, filesystem routes, or the input controller. A supplied
game-version hint is NOT independently observed or authenticated here. Even a
historical version match cannot promote a static route to executable status.
"""

import re


_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")
_GAME_ID = re.compile(r"[0-9]{1,32}\Z")


def _valid_candidate(summary, *, status, count_key):
    return (
        isinstance(summary, dict)
        and summary.get("status") == status
        and type(summary.get(count_key)) is int
        and 0 < summary[count_key] <= (24 if count_key == "receipt_candidate_count" else 8)
        and summary.get("rejected_manifest_count") == 0
        and summary.get("can_start") is False
    )


def _historical_version_state(receipts, comparison, version_hint):
    if version_hint is None:
        return "VERSION_NOT_OBSERVED"
    if not isinstance(comparison, dict) or comparison.get("status") != "LOCAL_ID_OVERLAP_ONLY":
        return "VERSION_NOT_COMPARABLE"
    matches = comparison.get("matches")
    rows = receipts.get("sources") if isinstance(receipts, dict) else None
    if (not isinstance(matches, list) or not isinstance(rows, list)
            or not 1 <= len(matches) <= 8):
        return "VERSION_NOT_COMPARABLE"
    ids = set()
    for row in matches:
        if not isinstance(row, dict) or not isinstance(row.get("game_mob_id"), str):
            return "VERSION_NOT_COMPARABLE"
        game_id = row["game_mob_id"]
        if not _GAME_ID.fullmatch(game_id):
            return "VERSION_NOT_COMPARABLE"
        ids.add(game_id)
    versions = set()
    for row in rows:
        if not isinstance(row, dict):
            return "VERSION_NOT_COMPARABLE"
        if row.get("game_mob_id") in ids:
            version = row.get("game_version")
            if not isinstance(version, str) or not _VERSION.fullmatch(version):
                return "VERSION_NOT_COMPARABLE"
            versions.add(version)
    if not versions:
        return "VERSION_NOT_COMPARABLE"
    if len(versions) != 1:
        return "CONFLICTING_HISTORICAL_VERSIONS"
    return ("HISTORICAL_EQUAL_UNVERIFIED" if version_hint in versions
            else "HISTORICAL_VERSION_MISMATCH")


def build_calibration_preflight(
    kind: str,
    receipt_summary: dict | None,
    route_summary: dict | None,
    reconciliation: dict | None,
    *,
    game_version_hint: str | None = None,
) -> dict:
    """Return a path-free next-step diagnostic; ALWAYS deny execution.

    The optional version hint is for offline diagnostic/testing only. The GUI
    intentionally does not accept it from users. A future runtime adapter must
    independently authenticate game/version identity and the existing SHA-bound
    qualification sidecar rather than using this report as permission.
    """
    if kind not in ("material", "mob") or type(kind) is not str:
        raise ValueError("Unknown farming target kind")
    if game_version_hint is not None:
        if not isinstance(game_version_hint, str) or not _VERSION.fullmatch(game_version_hint):
            raise ValueError("Invalid game version hint")
    if kind == "mob":
        return {
            "status": "CALIBRATION_REQUIRED",
            "source_check": "NOT_APPLICABLE",
            "route_check": "NO_VERIFIED_MOB_ROUTE",
            "identity_check": "UNRESOLVED",
            "game_version_check": "VERSION_NOT_OBSERVED",
            "runtime_qualification": "NOT_CHECKED",
            "fresh_inventory_check": "NOT_OBSERVED",
            "input_safety_check": "NOT_CHECKED",
            "can_start": False,
            "next_action": "Identify the in-game numeric enemy ID and independently calibrate its current-version route.",
        }

    source_ok = _valid_candidate(
        receipt_summary, status="LOCAL_CANDIDATES_ONLY",
        count_key="receipt_candidate_count",
    )
    route_ok = _valid_candidate(
        route_summary, status="LOCAL_ROUTE_CANDIDATES_ONLY",
        count_key="route_candidate_count",
    )
    identity_overlap = (
        source_ok and route_ok and isinstance(reconciliation, dict)
        and reconciliation.get("status") == "LOCAL_ID_OVERLAP_ONLY"
        and type(reconciliation.get("candidate_match_count")) is int
        and 1 <= reconciliation["candidate_match_count"] <= 8
        and reconciliation.get("can_start") is False
    )
    version_state = _historical_version_state(
        receipt_summary, reconciliation, game_version_hint,
    ) if identity_overlap else (
        "VERSION_NOT_OBSERVED" if game_version_hint is None
        else "VERSION_NOT_COMPARABLE"
    )
    incomplete = any(
        isinstance(summary, dict) and (
            summary.get("status") in ("AUDIT_INCOMPLETE", "ROUTE_AUDIT_INCOMPLETE")
            or type(summary.get("rejected_manifest_count")) is int
            and summary["rejected_manifest_count"] > 0
        )
        for summary in (receipt_summary, route_summary)
    )
    if incomplete:
        next_action = "Review incomplete or rejected local evidence before calibration."
    elif not source_ok:
        next_action = "Collect and independently review an actual material inventory increase after the enemy encounter."
    elif not route_ok:
        next_action = "Calibrate a bounded route and its map/profile evidence for the observed enemy ID."
    elif not identity_overlap:
        next_action = "Reconcile exact numeric enemy IDs between historical inventory and route observations."
    elif version_state == "HISTORICAL_VERSION_MISMATCH":
        next_action = "Reobserve the material source and route in the current game version."
    elif version_state == "CONFLICTING_HISTORICAL_VERSIONS":
        next_action = "Resolve conflicting historical game versions before route review."
    else:
        next_action = (
            "Capture fresh game and runtime versions, then independently review "
            "the SHA-bound route qualification, inventory OCR, focus and input safety."
        )

    return {
        "status": "CALIBRATION_REQUIRED",
        "source_check": "HISTORICAL_ONLY" if source_ok else "MISSING_OR_INVALID",
        "route_check": "STATIC_ONLY" if route_ok else "MISSING_OR_INVALID",
        "identity_check": "HISTORICAL_ID_OVERLAP_ONLY" if identity_overlap else "UNRESOLVED",
        "game_version_check": version_state,
        "runtime_qualification": "NOT_CHECKED",
        "fresh_inventory_check": "NOT_OBSERVED",
        "input_safety_check": "NOT_CHECKED",
        "can_start": False,
        "next_action": next_action,
    }
