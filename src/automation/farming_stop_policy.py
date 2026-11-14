"""Deterministic bounded stop-policy evaluation, without game authority.

The policy consumes numerical observations for planning/QA only. It does NOT
read game memory, authenticate OCR or inventory, issue input, schedule another
camp, or authorize execution. Real adapters must separately authenticate each
observation and enforce the same or stricter bounds in the owned controller.
"""
from src.automation.farming_selection import TargetKind


MAX_GOAL = 9_999_999
MAX_ATTEMPTS = 3


def evaluate_stop_criterion(
    kind: TargetKind,
    requested: int | None,
    *,
    observed: int | None = None,
    attempts: int = 0,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict:
    """Stop-first evaluation for materials and mob encounters.

    No value in this result can authorize a follow-up game input. In
    particular 'GOAL_BELOW_TARGET' means only that a number is below the
    requested goal, NOT that navigation, combat or spending is permitted.
    """
    if not isinstance(kind, TargetKind):
        raise ValueError("Unknown goal target kind")
    if requested is not None and (
        type(requested) is not int or not 1 <= requested <= MAX_GOAL
    ):
        raise ValueError("Stop target must be a positive integer")
    if observed is not None and (
        type(observed) is not int or not 0 <= observed <= MAX_GOAL
    ):
        raise ValueError("Observation must be a nonnegative integer")
    if (type(attempts) is not int or attempts < 0
            or type(max_attempts) is not int
            or not 1 <= max_attempts <= MAX_ATTEMPTS):
        raise ValueError("Invalid bounded attempt count")
    mode = (
        "INVENTORY_TOTAL" if kind == TargetKind.MATERIAL else "ENCOUNTER_LIMIT"
    )
    if attempts >= max_attempts:
        decision, reason = (
            "STOP_ATTEMPT_LIMIT", "Bounded attempt limit reached."
        )
    elif requested is None:
        decision, reason = (
            "NO_EXPLICIT_GOAL", "A stop target has not been configured."
        )
    elif observed is None:
        decision, reason = (
            "FRESH_OBSERVATION_REQUIRED",
            "Actual current inventory or encounters have not been verified.",
        )
    elif observed >= requested:
        decision, reason = (
            "STOP_TARGET_REACHED",
            "Reported target is reached; stop conservatively. "
            "Caller observations still require independent authentication.",
        )
    else:
        decision, reason = (
            "BELOW_GOAL_NO_AUTOMATIC_CONTINUE",
            "Below requested target; the current-runtime controller must "
            "independently authorize every bounded action.",
        )

    return {
        "mode": mode,
        "requested": requested,
        "observed": observed,
        "enforced": False,
        "state": "PLANNED_ONLY",
        "attempts": attempts,
        "max_attempts": max_attempts,
        "decision": decision,
        "reason": reason,
        "requires_independent_observation": True,
        "can_continue": False,
        "can_dispatch": False,
    }
