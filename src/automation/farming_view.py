"""Read-only, serializable view model for the material-first Farming Assistant.

No executor, session, map, OCR or input subsystem may be imported here.
Qualified routes must be checked later in the actual game runtime. The UI
always remains PREVIEW_ONLY until an independently reviewed execution adapter
and explicit user authorization are wired through this boundary.
"""

from src.automation.farming_selection import (
    FarmingCatalog, TargetKind, starting_catalog,
)
from src.automation.farming_evidence import FarmingEvidenceAudit

MAX_GOAL = 9_999_999
MAX_QUERY_LENGTH = 120


class FarmingAssistantView:
    def __init__(
        self,
        catalog: FarmingCatalog | None = None,
        evidence_audit: FarmingEvidenceAudit | None = None,
    ):
        self.catalog = catalog if catalog is not None else starting_catalog()
        self.evidence_audit = (
            evidence_audit if evidence_audit is not None else FarmingEvidenceAudit()
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
        matches = self.catalog.search(query, kind=target_kind, limit=30)
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
        return {
            "target": {
                "id": resolution.target.target_id,
                "kind": resolution.target.kind.value,
                "name": resolution.target.name,
                "description": resolution.target.description,
            },
            "desired_total": goal,
            "owned_quantity": None,  # Actual inventory was NOT measured.
            "readiness": resolution.readiness.value,
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
            "can_start": False,
            "can_pause": False,
            "can_stop": False,
            "run_state": "PREVIEW_ONLY",
            "reason": resolution.explanation,
            "next_step": (
                "Read-only calibration: confirm actual enemy drops, inventory "
                "receipt and current-game route qualification before execution."
            ),
        }
