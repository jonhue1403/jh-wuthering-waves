"""Path-free reconciliation of historical receipt and route *candidates*.

Exact numeric game mob IDs are the only cross-audit join key. This module has
no game, input, task, network, or filesystem access. Matching local metadata
does NOT authenticate screenshots, game identity, reviewer assertions, version,
or permit route execution. It is diagnostic only.
"""

from collections import defaultdict
import re

from src.automation.farming_selection import FarmingCatalog, TargetKind

_SLUG = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
_ROUTE_ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
_MAX_RECEIPTS = 24
_MAX_ROUTES = 8


def _game_id(value):
    # Preserve leading zeros. Never coerce ints, floats or display-name slugs.
    return (isinstance(value, str) and value.isascii()
            and value.isdecimal() and 1 <= len(value) <= 32)


def _blocked(status, note, *, receipt_count=0, route_count=0):
    return {
        "status": status,
        "candidate_match_count": 0,
        "matches": [],
        "receipt_candidate_count": receipt_count,
        "route_candidate_count": route_count,
        "unmatched_receipt_count": receipt_count,
        "unmatched_route_count": route_count,
        "can_start": False,
        "note": note,
    }


def reconcile_candidate_audits(
    material_id: str, receipt_summary: dict, route_summary: dict, *,
    catalog: FarmingCatalog,
) -> dict:
    """Compare *untrusted* local audit summaries, without promoting evidence.

    A successful result means only that bounded local metadata claims share an
    identical numeric game mob ID for this material. The current game version
    is NOT bound to a route by the static route audit. Nothing here is a
    live-source verifier or current-runtime qualification callback.
    """
    if (not isinstance(material_id, str) or not _SLUG.fullmatch(material_id)
            or not isinstance(catalog, FarmingCatalog)):
        raise ValueError("Unknown calibration target")
    if not catalog.search(kind=TargetKind.MATERIAL, limit=100) or not any(
        item.target_id == material_id
        for item in catalog.search(kind=TargetKind.MATERIAL, limit=100)
    ):
        raise ValueError("Unknown calibration target")

    if not isinstance(receipt_summary, dict) or not isinstance(route_summary, dict):
        return _blocked("INVALID_AUDIT_SCHEMA", "Invalid local audit summary.")
    if (receipt_summary.get("material_id") != material_id
            or route_summary.get("material_id") != material_id):
        return _blocked(
            "TARGET_SCOPE_MISMATCH",
            "Receipt and route audits do not belong to the same material.",
        )

    receipts = receipt_summary.get("sources")
    routes = route_summary.get("routes")
    receipt_count = receipt_summary.get("receipt_candidate_count")
    route_count = route_summary.get("route_candidate_count")
    receipt_rejected = receipt_summary.get("rejected_manifest_count")
    route_rejected = route_summary.get("rejected_manifest_count")
    if (not isinstance(receipts, list) or not isinstance(routes, list)
            or type(receipt_count) is not int or type(route_count) is not int
            or type(receipt_rejected) is not int or type(route_rejected) is not int
            or receipt_rejected < 0 or route_rejected < 0
            or len(receipts) > _MAX_RECEIPTS or len(routes) > _MAX_ROUTES
            or receipt_count != len(receipts) or route_count != len(routes)):
        return _blocked("INVALID_AUDIT_SCHEMA", "Inconsistent or excessive local audit data.")

    # An invalid or truncated scan can exclude conflicting identity records.
    # A partial scan cannot safely establish even a candidate association.
    if (receipt_summary.get("status") == "AUDIT_INCOMPLETE"
            or route_summary.get("status") == "ROUTE_AUDIT_INCOMPLETE"
            or receipt_rejected or route_rejected):
        return _blocked(
            "INCOMPLETE_AUDITS",
            "Review invalid or truncated local receipts/routes before comparing IDs.",
            receipt_count=receipt_count, route_count=route_count,
        )

    names = {
        target.target_id: target.name
        for target in catalog.search(kind=TargetKind.MOB, limit=100)
    }
    mapped_sources = {
        source.mob_id for source in catalog.documented_sources(material_id)
    }
    if ((receipts and receipt_summary.get("status") != "LOCAL_CANDIDATES_ONLY")
            or (routes and route_summary.get("status") != "LOCAL_ROUTE_CANDIDATES_ONLY")):
        return _blocked(
            "INVALID_AUDIT_SCHEMA",
            "Candidate records conflict with their local audit status.",
            receipt_count=receipt_count, route_count=route_count,
        )

    if not receipts or not routes:
        return _blocked(
            "NO_SHARED_CANDIDATES",
            "Both local receipt and route candidates are required for an ID comparison.",
            receipt_count=receipt_count, route_count=route_count,
        )

    by_game = defaultdict(set)
    by_catalog = defaultdict(set)
    versions = defaultdict(set)
    observed = defaultdict(int)
    for row in receipts:
        if not isinstance(row, dict):
            return _blocked("INVALID_AUDIT_SCHEMA", "Invalid receipt record.")
        mob = row.get("catalog_mob_id")
        game = row.get("game_mob_id")
        version = row.get("game_version")
        delta = row.get("inventory_delta")
        if (not isinstance(mob, str) or not _SLUG.fullmatch(mob)
                or not _game_id(game)
                or not isinstance(version, str) or not 0 < len(version) <= 32
                or not version.strip() or type(delta) is not int or delta <= 0
                or delta > 9_999_999
                or row.get("evidence_level") != "local_hash_match_only"):
            return _blocked("INVALID_AUDIT_SCHEMA", "Unusable local receipt identity.")
        if mob not in names:
            return _blocked(
                "UNRECOGNIZED_CATALOG_MOB",
                "A local receipt names a mob absent from the current catalog.",
                receipt_count=receipt_count, route_count=route_count,
            )
        if mob not in mapped_sources:
            return _blocked(
                "SOURCE_NOT_MAPPED_TO_MATERIAL",
                "The local enemy record has no documented mapping to this material.",
                receipt_count=receipt_count, route_count=route_count,
            )
        by_game[game].add(mob)
        by_catalog[mob].add(game)
        versions[game].add(version)
        observed[game] += 1

    route_by_game = defaultdict(set)
    seen_route_ids = set()
    for row in routes:
        if not isinstance(row, dict):
            return _blocked("INVALID_AUDIT_SCHEMA", "Invalid route record.")
        game = row.get("game_mob_id")
        route_id = row.get("route_id")
        camps = row.get("camp_count")
        if (not _game_id(game) or not isinstance(route_id, str)
                or not _ROUTE_ID.fullmatch(route_id) or type(camps) is not int
                or not 1 <= camps <= 3
                or row.get("evidence_level") != "local_static_hash_match_only"):
            return _blocked("INVALID_AUDIT_SCHEMA", "Unusable local route identity.")
        if route_id in seen_route_ids:
            return _blocked(
                "DUPLICATE_LOCAL_ROUTE_ID",
                "Duplicate route identities must be reconciled in the route audit.",
                receipt_count=receipt_count, route_count=route_count,
            )
        seen_route_ids.add(route_id)
        route_by_game[game].add(route_id)

    if (any(len(ids) != 1 for ids in by_game.values())
            or any(len(ids) != 1 for ids in by_catalog.values())
            or any(len(items) != 1 for items in versions.values())):
        return _blocked(
            "AMBIGUOUS_RECEIPT_IDENTITIES",
            "Conflicting catalog names, numeric game IDs or historical game versions.",
            receipt_count=receipt_count, route_count=route_count,
        )

    shared = sorted(set(by_game) & set(route_by_game))
    matches = [
        {
            "catalog_mob_id": next(iter(by_game[game])),
            "name": names[next(iter(by_game[game]))],
            "game_mob_id": game,
            "receipt_record_count": observed[game],
            "route_candidate_count": len(route_by_game[game]),
            "evidence_level": "local_numeric_id_overlap_only",
        }
        for game in shared
    ]
    # IDs with leading zeros are intentionally *not* normalized or joined.
    return {
        "status": "LOCAL_ID_OVERLAP_ONLY" if matches else "NO_EXACT_ID_MATCH",
        "candidate_match_count": len(matches),
        "matches": matches,
        "receipt_candidate_count": receipt_count,
        "route_candidate_count": route_count,
        "unmatched_receipt_count": sum(
            count for game, count in observed.items() if game not in route_by_game
        ),
        "unmatched_route_count": sum(
            len(ids) for game, ids in route_by_game.items() if game not in by_game
        ),
        "can_start": False,
        "note": (
            "Numeric ID overlap in historical local metadata only. Route game "
            "version, live inventory OCR, current-runtime evidence, and reviewer "
            "qualification are not established. Execution remains disabled."
        ) if matches else "No exact numeric enemy IDs overlap across local audits.",
    }
