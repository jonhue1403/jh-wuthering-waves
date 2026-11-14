"""Non-authorizing, version-aware calibration checklist for Farming Assistant.

This module consumes only read-only historical summaries. It never loads the
game, a runtime sidecar, filesystem routes, or the input controller. A supplied
game-version hint is NOT independently observed or authenticated here. Even a
historical version match cannot promote a static route to executable status.
"""

import re

from src.automation.farming_acquisition_reference import SourceKind


_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")
_GAME_ID = re.compile(r"[0-9]{1,32}\Z")


def _valid_candidate(summary, *, status, count_key):
    return (
        isinstance(summary, dict)
        and summary.get("status") == status
        and type(summary.get(count_key)) is int
        and 0 < summary[count_key] <= (24 if count_key == "receipt_candidate_count" else 8)
        and type(summary.get("rejected_manifest_count")) is int
        and summary["rejected_manifest_count"] == 0
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


_DOMAIN_METHODS = frozenset((
    SourceKind.FORGERY.value,
    SourceKind.SIMULATION.value,
    SourceKind.TACET_FIELD.value,
))
_KNOWN_METHODS = frozenset(method.value for method in SourceKind)


def _non_mob_source_preflight(methods):
    """Never turn a quest, domain, synthesis or historical method into a mob."""

    names = set(methods)
    domain = names & _DOMAIN_METHODS
    if domain:
        family = "DOMAIN_CHALLENGE_CANDIDATE"
        if len(domain) == 1:
            method = next(iter(domain))
            label = {
                SourceKind.FORGERY.value: "Forgery Challenge",
                SourceKind.SIMULATION.value: "Simulation Training",
                SourceKind.TACET_FIELD.value: "Tacet Field",
            }[method]
            next_action = (
                f"Observe the exact current-game {label} and its actual material "
                "reward. Qualify the selected challenge, per-claim current "
                "Waveplate debit and fresh inventory receipt before enabling "
                "any resource-consuming adapter."
            )
        else:
            next_action = (
                "Choose and independently verify one current-game domain provider "
                "and material reward; conflicting references do not select a challenge."
            )
        source_state = "DOMAIN_SOURCE_UNVERIFIED"
    elif SourceKind.SYNTHESIS.value in names:
        family = "SYNTHESIS_REFERENCE_ONLY"
        source_state = "NON_EXECUTABLE_REFERENCE"
        next_action = (
            "Review the current in-game synthesis recipe, input materials and "
            "consumption costs. There is no qualified automatic synthesis adapter."
        )
    elif SourceKind.SUBSCRIPTION.value in names:
        family = "HISTORICAL_REFERENCE_ONLY"
        source_state = "NON_EXECUTABLE_REFERENCE"
        next_action = (
            "Check whether the historical reward is still obtainable in the "
            "current game. A past subscription does not authorize farming."
        )
    elif names:
        family = "MANUAL_REWARD_REFERENCE_ONLY"
        source_state = "NON_EXECUTABLE_REFERENCE"
        next_action = (
            "Verify the item's current quest, exploration, event or exchange "
            "availability and observe its inventory receipt. No repeatable "
            "enemy route or automatic reward claim is qualified."
        )
    else:
        family = "SOURCE_UNKNOWN"
        source_state = "SOURCE_UNRESOLVED"
        next_action = (
            "Identify a real acquisition source in the current game before "
            "choosing an executor. Do not assume the material drops from mobs."
        )
    return {
        "status": "CALIBRATION_REQUIRED",
        "source_family": family,
        "source_check": source_state,
        "route_check": "NOT_APPLICABLE",
        "identity_check": "NOT_APPLICABLE",
        "game_version_check": "VERSION_NOT_OBSERVED",
        "runtime_qualification": "NOT_CHECKED",
        "fresh_inventory_check": "NOT_OBSERVED",
        "input_safety_check": "NOT_CHECKED",
        "can_start": False,
        "next_action": next_action,
    }


def build_calibration_preflight(
    kind: str,
    receipt_summary: dict | None,
    route_summary: dict | None,
    reconciliation: dict | None,
    *,
    game_version_hint: str | None = None,
    acquisition_methods: tuple[str, ...] | list[str] | None = None,
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
    if acquisition_methods is not None:
        if (type(acquisition_methods) not in (list, tuple)
                or len(acquisition_methods) > len(_KNOWN_METHODS)
                or any(type(method) is not str or method not in _KNOWN_METHODS
                       for method in acquisition_methods)
                or len(set(acquisition_methods)) != len(acquisition_methods)):
            raise ValueError("Unrecognized or duplicate acquisition methods")
        if kind == "material" and SourceKind.MOB_DROP.value not in acquisition_methods:
            return _non_mob_source_preflight(acquisition_methods)
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
        "source_family": "MOB_DROP_CANDIDATE",
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
