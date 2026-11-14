"""Source-aware planning for the material-first Farming Assistant.

This is the boundary between a user's requested item and the *kind* of
existing automation that might eventually acquire it. It deliberately does
not resolve local paths, run framework tasks, accept claims of qualification,
spend resources, or authorize gameplay. A genuine current-runtime qualified
execution adapter is required separately.
"""
from dataclasses import dataclass
from enum import Enum

from src.automation.farming_acquisition_reference import (
    SourceKind, documented_acquisition,
)
from src.automation.farming_selection import TargetKind


class Workflow(str, Enum):
    BOUNDED_OVERWORLD = "BOUNDED_OVERWORLD"
    FORGERY = "FORGERY_CHALLENGE"
    SIMULATION = "SIMULATION_TRAINING"
    TACET_FIELD = "TACET_FIELD"
    SYNTHESIS = "SYNTHESIS"
    MANUAL_REWARD = "MANUAL_REWARD"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"


# The task identity is a code-level *candidate* only. It cannot be dispatched
# by this module or through the read-only Farming Assistant HTTP endpoint.
_TASK_CANDIDATES = {
    SourceKind.MOB_DROP: ("BoundedRouteTask", Workflow.BOUNDED_OVERWORLD),
    SourceKind.FORGERY: ("ForgeryTask", Workflow.FORGERY),
    SourceKind.SIMULATION: ("SimulationTask", Workflow.SIMULATION),
    SourceKind.TACET_FIELD: ("TacetTask", Workflow.TACET_FIELD),
    SourceKind.SYNTHESIS: (None, Workflow.SYNTHESIS),
    SourceKind.EXPLORATION: (None, Workflow.MANUAL_REWARD),
    SourceKind.REWARD: (None, Workflow.MANUAL_REWARD),
    SourceKind.SUBSCRIPTION: (None, Workflow.HISTORICAL_ONLY),
}
_POSSIBLE_SPEND = frozenset((
    SourceKind.FORGERY, SourceKind.SIMULATION, SourceKind.TACET_FIELD,
))
_POSSIBLE_CONSUME = frozenset((SourceKind.SYNTHESIS,))


@dataclass(frozen=True)
class AcquisitionOption:
    """A possible way to acquire an item, not an approved executable source."""

    kind: SourceKind
    workflow: Workflow
    label: str
    code_task_candidate: str | None
    may_spend_waveplates: bool
    may_consume_inventory: bool
    source_url: str

    def __post_init__(self):
        if not isinstance(self.kind, SourceKind) or not isinstance(self.workflow, Workflow):
            raise ValueError("Unknown acquisition method or workflow")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Acquisition option needs a label")
        if (self.code_task_candidate is not None
                and (not isinstance(self.code_task_candidate, str)
                     or not self.code_task_candidate.strip())):
            raise ValueError("Invalid possible task identity")
        if type(self.may_spend_waveplates) is not bool or type(self.may_consume_inventory) is not bool:
            raise ValueError("Acquisition resource flags must be booleans")
        if not isinstance(self.source_url, str) or not self.source_url.startswith("https://"):
            raise ValueError("Invalid acquisition source reference")

    def public(self) -> dict:
        """Safe serializable UI data: no task name, manifest or file path."""
        return {
            "method": self.kind.value,
            "workflow": self.workflow.value,
            "label": self.label,
            "reference_url": self.source_url,
            "automation_candidate_exists": self.code_task_candidate is not None,
            "resource_policy": (
                "POTENTIAL_WAVEPLATE_COST" if self.may_spend_waveplates else
                "MATERIAL_CONSUMPTION_UNVERIFIED" if self.may_consume_inventory else
                "NO_SPEND_CONFIRMED_FALSE"
            ),
            "qualification": "CURRENT_GAME_EVIDENCE_REQUIRED",
            "can_execute": False,
        }


def plan_material_acquisition(material_id: str) -> dict:
    """Generate a deterministic, path-free *preview*, never an executable plan.

    Even a matching historical receipt, a community source or a task import
    does not permit dispatch. There is intentionally no 'qualified=True'
    argument, no caller-supplied file path and no route picker here.
    """
    record = documented_acquisition(material_id)
    if record["status"] != "REFERENCE_ONLY" or record["can_start"] is not False:
        raise ValueError("Expected unqualified reference-only acquisition data")
    options = []
    for method in record["methods"]:
        kind = SourceKind(method["kind"])
        task_name, workflow = _TASK_CANDIDATES[kind]
        candidate = AcquisitionOption(
            kind=kind,
            workflow=workflow,
            label=method["label"],
            code_task_candidate=task_name,
            may_spend_waveplates=kind in _POSSIBLE_SPEND,
            may_consume_inventory=kind in _POSSIBLE_CONSUME,
            source_url=method["reference_url"],
        )
        options.append(candidate.public())

    if not options:
        raise ValueError("Material lacks a documented possible source")
    # A shortlist must not silently prioritize a costly or nonrepeatable
    # action. A selected provider only becomes meaningful after independent
    # current-version identity, eligibility, budget and receipt checks.
    automatic_candidates = sum(option["automation_candidate_exists"]
                               for option in options)
    return {
        "status": "AWAITING_CURRENT_GAME_SOURCE_VALIDATION",
        "target_kind": TargetKind.MATERIAL.value,
        "material_id": material_id,
        "possible_methods": options,
        "possible_automation_adapter_count": automatic_candidates,
        "selected_provider": None,
        "qualified_provider_ids": [],
        "can_dispatch": False,
        "can_start": False,
        "source_auto_selection": "NOT_PERMITTED_WITH_REFERENCE_ONLY_DATA",
        "next_action": (
            "Identify the actual item and available reward source in the "
            "current game, then independently qualify a bounded, inventory-"
            "verified provider before any farming or spending."
        ),
    }


def plan_mob_hunt(mob_id: str, *, catalog=None) -> dict:
    """A named mob is not a numeric game ID, calibrated camp or walk permit."""
    from src.automation.farming_selection import starting_catalog
    targets = catalog if catalog is not None else starting_catalog()
    targets.resolve(TargetKind.MOB, mob_id)
    return {
        "status": "AWAITING_CURRENT_GAME_MOB_ROUTE",
        "target_kind": TargetKind.MOB.value,
        "mob_id": mob_id,
        "possible_methods": [{
            "method": SourceKind.MOB_DROP.value,
            "workflow": Workflow.BOUNDED_OVERWORLD.value,
            "label": "Bounded surface mob hunt (not calibrated)",
            "reference_url": None,
            "automation_candidate_exists": True,
            "resource_policy": "NO_SPEND_CONFIRMED_FALSE",
            "qualification": "CURRENT_GAME_EVIDENCE_REQUIRED",
            "can_execute": False,
        }],
        "possible_automation_adapter_count": 1,
        "selected_provider": None,
        "qualified_provider_ids": [],
        "can_dispatch": False,
        "can_start": False,
        "source_auto_selection": "NOT_PERMITTED_WITH_REFERENCE_ONLY_DATA",
        "next_action": (
            "Verify the exact numeric game mob ID and a SHA-bound current-"
            "version surface route; then independently qualify bounded input."
        ),
    }
