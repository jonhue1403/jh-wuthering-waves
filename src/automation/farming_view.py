"""Read-only, serializable view model for the material-first Farming Assistant.

No executor, session, map, OCR or input subsystem may be imported here.
Qualified routes must be checked later in the actual game runtime. The UI
always remains PREVIEW_ONLY until an independently reviewed execution adapter
and explicit user authorization are wired through this boundary.
"""

from src.automation.farming_selection import (
    FarmingCatalog, SCREENSHOT_MATERIALS, TargetKind, starting_catalog,
)
from src.automation.farming_evidence import FarmingEvidenceAudit
from src.automation.farming_route_audit import FarmingRouteAudit
from src.automation.farming_reconciliation import reconcile_candidate_audits
from src.automation.farming_preflight import build_calibration_preflight
from src.automation.farming_calibration_guide import build_calibration_guide
from src.automation.farming_acquisition_reference import documented_acquisition
from src.automation.farming_strategy import (
    plan_material_acquisition, plan_mob_hunt,
)
from src.automation.farming_stop_policy import evaluate_stop_criterion

MAX_GOAL = 9_999_999
MAX_QUERY_LENGTH = 120
_KNOWN_SCREENSHOT_MATERIAL_IDS = frozenset(
    slug for slug, _ in SCREENSHOT_MATERIALS
)


def _material_reference(target_id: str) -> dict:
    # Tests and extensions can inject additional catalog entries. Unknown
    # materials must remain discoverable even without a research reference;
    # never turn the absence of a wiki claim into an executable provider.
    if target_id in _KNOWN_SCREENSHOT_MATERIAL_IDS:
        return documented_acquisition(target_id)
    return {
        "status": "NO_RESEARCH_REFERENCE",
        "methods": [], "possible_mob_source": False,
        "executable_source_ids": [], "can_start": False,
        "requires_game_verification": True,
        "note": "No documented acquisition method for this catalog target.",
    }


def _material_plan(target_id: str) -> dict:
    if target_id in _KNOWN_SCREENSHOT_MATERIAL_IDS:
        return plan_material_acquisition(target_id)
    return {
        "status": "NO_DOCUMENTED_PROVIDER",
        "target_kind": TargetKind.MATERIAL.value,
        "material_id": target_id, "possible_methods": [],
        "possible_automation_adapter_count": 0, "selected_provider": None,
        "qualified_provider_ids": [], "can_dispatch": False,
        "can_start": False,
        "source_auto_selection": "NOT_PERMITTED_WITH_REFERENCE_ONLY_DATA",
        "next_action": "Observe and independently qualify the actual acquisition source.",
    }


class FarmingAssistantView:
    def __init__(
        self,
        catalog: FarmingCatalog | None = None,
        evidence_audit: FarmingEvidenceAudit | None = None,
        route_audit: FarmingRouteAudit | None = None,
    ):
        self.catalog = catalog if catalog is not None else starting_catalog()
        self.evidence_audit = (
            evidence_audit if evidence_audit is not None else FarmingEvidenceAudit()
        )
        self.route_audit = (
            route_audit if route_audit is not None else FarmingRouteAudit()
        )

    @staticmethod
    def _kind(kind: str) -> TargetKind:
        if not isinstance(kind, str):
            raise ValueError("Choose Material or Mob")
        try:
            return TargetKind(kind)
        except ValueError:
            raise ValueError("Choose Material or Mob") from None

    @staticmethod
    def _goal(total) -> int | None:
        if total is None or total == "":
            return None
        # JSON never sends Python ints for a text input; accept strictly
        # formatted decimal text or actual positive ints, not booleans/floats.
        if isinstance(total, str):
            if not total.isascii() or not total.isdecimal() or len(total) > 7:
                raise ValueError("Goal must be a positive whole number")
            total = int(total)
        if type(total) is not int or not 1 <= total <= MAX_GOAL:
            raise ValueError("Goal must be a positive whole number")
        return total

    def targets(self, kind: str = "material", query: str = "") -> list[dict]:
        target_kind = self._kind(kind)
        if not isinstance(query, str) or len(query) > MAX_QUERY_LENGTH:
            raise ValueError("Search must be a short text query")
        matches = list(self.catalog.search(query, kind=target_kind, limit=30))
        # Preserve the previously selected FF Mech Core as the default preview
        # when browsing the now-expanded material list. Filtered results still
        # follow their normal alphabetical search order.
        if target_kind == TargetKind.MATERIAL and not query.strip():
            matches.sort(key=lambda target: target.target_id != "ff-mech-core")
        return [
            {
                "id": target.target_id,
                "kind": target.kind.value,
                "name": target.name,
                "description": target.description,
                "readiness": self.catalog.resolve(
                    target.kind, target.target_id
                ).readiness.value,
            }
            for target in matches
        ]

    def preview(self, kind: str, target_id: str, desired_total=None) -> dict:
        target_kind = self._kind(kind)
        if not isinstance(target_id, str) or len(target_id) > 120:
            raise ValueError("Select a valid material or mob")
        goal = self._goal(desired_total)
        # A requested stop condition is display-only until an independently
        # qualified runtime adapter measures progress and enforces a hard cap.
        # Material quantities and mob encounter counts are different units.
        stop_criterion = evaluate_stop_criterion(target_kind, goal)
        # Deliberately no callbacks: a present source/route reference alone
        # cannot authenticate game observations, current runtime or input.
        resolution = self.catalog.resolve(target_kind, target_id)
        names = {
            entry.target_id: entry.name
            for entry in self.catalog.search(kind=TargetKind.MOB, limit=100)
        }
        documented = (
            self.catalog.documented_sources(target_id)
            if target_kind == TargetKind.MATERIAL else ()
        )
        # Local, hash-matched observations remain untrusted historical
        # candidates. They never populate verified_mob_ids or route IDs.
        calibration = (
            self.evidence_audit.summary(target_id)
            if target_kind == TargetKind.MATERIAL else {
                "status": "NO_MOB_ROUTE_QUALIFICATION",
                "receipt_candidate_count": 0,
                "rejected_manifest_count": 0,
                "sources": [],
                "can_start": False,
                "note": "A documented mob name does not qualify a live route.",
            }
        )
        # A static local manifest/hash audit is not an executable permission.
        # In particular, a display-name mob slug is not a numeric game mob ID.
        route_calibration = (
            self.route_audit.summary(target_id)
            if target_kind == TargetKind.MATERIAL else {
                "status": "NO_MOB_ROUTE_QUALIFICATION",
                "route_candidate_count": 0,
                "rejected_manifest_count": 0,
                "routes": [],
                "can_start": False,
                "note": "A mob display name does not qualify a current-game route.",
            }
        )
        reconciliation = (
            reconcile_candidate_audits(
                target_id, calibration, route_calibration, catalog=self.catalog,
            ) if target_kind == TargetKind.MATERIAL else {
                "status": "NOT_APPLICABLE_MOB",
                "candidate_match_count": 0,
                "matches": [],
                "can_start": False,
                "note": "A mob display slug cannot establish a numeric game ID.",
            }
        )
        # Use the researched acquisition *method*, never a guessed mob
        # source, to select the relevant read-only calibration steps. For
        # example quest/event-only or domain items must not request enemy IDs
        # or surface routes.
        acquisition_reference = (
            _material_reference(target_id)
            if target_kind == TargetKind.MATERIAL else {
                "status": "NOT_APPLICABLE_TO_MOB",
                "methods": [], "possible_mob_source": False,
                "executable_source_ids": [], "can_start": False,
                "requires_game_verification": True,
                "note": "A mob target still needs a current-runtime route.",
            }
        )
        acquisition_plan = (
            _material_plan(target_id)
            if target_kind == TargetKind.MATERIAL else
            plan_mob_hunt(target_id, catalog=self.catalog)
        )
        preflight = build_calibration_preflight(
            target_kind.value, calibration, route_calibration, reconciliation,
            acquisition_methods=(
                tuple(method["kind"] for method in acquisition_reference["methods"])
                if target_kind == TargetKind.MATERIAL else None
            ),
        )
        calibration_guide = build_calibration_guide(target_kind.value, preflight)
        return {
            "target": {
                "id": resolution.target.target_id,
                "kind": resolution.target.kind.value,
                "name": resolution.target.name,
                "description": resolution.target.description,
            },
            "desired_total": goal,  # Backwards-compatible raw UI input.
            "stop_criterion": stop_criterion,
            "owned_quantity": None,  # Actual inventory was NOT measured.
            "readiness": resolution.readiness.value,
            # Documented acquisition methods are not automatically executable
            # sources. They cover domain/quest/synthesis as well as mob cases.
            "acquisition_reference": acquisition_reference,
            "acquisition_plan": acquisition_plan,
            "source_candidates": [
                {
                    "mob_id": source.mob_id,
                    "name": names.get(source.mob_id, source.mob_id),
                    "source_url": source.source_url,
                    "evidence_level": "documented_only",
                }
                for source in documented
            ],
            "verified_mob_ids": [],
            "qualified_route_ids": [],
            "calibration": calibration,
            "route_calibration": route_calibration,
            "reconciliation": reconciliation,
            "preflight": preflight,
            "calibration_guide": calibration_guide,
            "can_start": False,
            "can_pause": False,
            "can_stop": False,
            "run_state": "PREVIEW_ONLY",
            "reason": (
                "Known acquisition reference, but this material has no "
                "qualified current-game provider or automatic route."
                if target_kind == TargetKind.MATERIAL
                and not any(method["kind"] == "MOB_DROP"
                            for method in acquisition_reference["methods"])
                else resolution.explanation
            ),
            "next_step": preflight["next_action"],
        }
