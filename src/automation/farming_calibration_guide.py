"""Read-only guided calibration steps for material-first farming.

This guide is presentation metadata, never a qualification workflow engine.
Steps cannot be marked complete here. No game input, filesystem path, execution
adapter, or reviewer sidecar is accepted or opened by this module.
"""

from src.automation.farming_preflight import build_calibration_preflight


def _step(step_id: str, title: str, instruction: str, *, historical: bool = False) -> dict:
    return {
        "id": step_id,
        "title": title,
        "instruction": instruction,
        "status": "HISTORICAL_REFERENCE_ONLY" if historical else "NEEDS_LIVE_VERIFICATION",
    }


_NON_MOB_FAMILIES = {
    "DOMAIN_CHALLENGE_CANDIDATE": "DOMAIN_SOURCE_UNVERIFIED",
    "SYNTHESIS_REFERENCE_ONLY": "NON_EXECUTABLE_REFERENCE",
    "HISTORICAL_REFERENCE_ONLY": "NON_EXECUTABLE_REFERENCE",
    "MANUAL_REWARD_REFERENCE_ONLY": "NON_EXECUTABLE_REFERENCE",
    "SOURCE_UNKNOWN": "SOURCE_UNRESOLVED",
}


def _non_mob_guide(preflight):
    family = preflight.get("source_family")
    if (preflight.get("source_check") != _NON_MOB_FAMILIES[family]
            or preflight.get("route_check") != "NOT_APPLICABLE"
            or preflight.get("identity_check") != "NOT_APPLICABLE"
            or preflight.get("runtime_qualification") != "NOT_CHECKED"
            or preflight.get("fresh_inventory_check") != "NOT_OBSERVED"
            or preflight.get("input_safety_check") != "NOT_CHECKED"
            or preflight.get("game_version_check") != "VERSION_NOT_OBSERVED"):
        raise ValueError("Unsupported non-mob calibration evidence state")
    if family == "DOMAIN_CHALLENGE_CANDIDATE":
        steps = [
            _step(
                "observe-domain-source", "Verify exact challenge and material",
                "In the installed client, capture the current challenge identity, "
                "selected F2 entry and exact reward material on fresh frames. "
                "A static task index or wiki reference is not source proof.",
            ),
            _step(
                "observe-installed-version", "Verify current client and runtime",
                "Independently observe the installed game and OK Script versions "
                "before binding any selector or adapter.",
            ),
            _step(
                "qualify-domain-claim", "Qualify bounded claims and debit receipts",
                "Independently review the selected challenge, actual claim cost, "
                "fresh Waveplates balance, journal PENDING before input, exact "
                "debit, no reserve or refill, and fail-closed interruption.",
            ),
            _step(
                "verify-live-inventory", "Verify material receipt and stopping goal",
                "Capture the exact item's inventory before and after the reward. "
                "A combat victory or claim confirmation does not prove receipt.",
            ),
            _step(
                "verify-input-safety", "Verify focus, stop and cancellation",
                "Independently test single-controller ownership, distinct fresh "
                "frames, pause/stop, held-input cleanup and no-skip Story Watch.",
            ),
        ]
    elif family == "SYNTHESIS_REFERENCE_ONLY":
        steps = [
            _step(
                "verify-current-recipe", "Verify synthesis availability",
                "Observe the current recipe, output item, required ingredients, "
                "conversion quantity and whether the option is available.",
            ),
            _step(
                "review-consumption", "Review ingredient consumption",
                "Synthesis can consume valuable materials. No automatic "
                "conversion or inventory destruction is authorized.",
            ),
            _step(
                "verify-live-inventory", "Verify manual result",
                "Only an actual item-detail inventory change can establish "
                "receipt. This preview never triggers synthesis.",
            ),
        ]
    elif family == "HISTORICAL_REFERENCE_ONLY":
        steps = [
            _step(
                "verify-current-availability", "Check current reward availability",
                "Independently check whether the historical subscription or "
                "reward exists in the installed game. An old guide is not proof.",
            ),
            _step(
                "verify-live-inventory", "Verify a separately obtained item",
                "Review the actual current item and inventory. The assistant "
                "does not automate purchases, claims or subscriptions.",
            ),
        ]
    elif family == "MANUAL_REWARD_REFERENCE_ONLY":
        steps = [
            _step(
                "verify-current-availability", "Check quest or reward eligibility",
                "Check whether this item is obtainable from the current quest, "
                "exploration, event or exchange; do not substitute a mob route.",
            ),
            _step(
                "verify-live-inventory", "Confirm manual reward receipt",
                "Validate the item's identity and actual inventory after "
                "a separately authorized user-driven acquisition.",
            ),
        ]
    else:
        steps = [
            _step(
                "identify-material-source", "Discover an actual material source",
                "Inspect the current game for a valid reward or acquisition "
                "method. Do not infer enemy drops from the material name.",
            ),
            _step(
                "verify-live-inventory", "Observe item identity and quantity",
                "Use fresh current-game item-detail observations before "
                "considering any new adapter.",
            ),
        ]

    return {
        "mode": "GUIDED_READ_ONLY",
        "next_step_id": steps[0]["id"],
        "steps": steps,
        "verified_step_count": 0,
        "can_start": False,
        "notice": (
            "This source does not have a qualified mob route. The guide is "
            "informational only; no auto farming or spending is enabled."
        ),
    }


def build_calibration_guide(kind: str, preflight: dict) -> dict:
    """Describe next calibration actions without promoting historical records.

    This function only consumes a previously generated preflight report. Even
    an old local file labeled REVIEWED, an ID match, or a version text match
    cannot complete a step or permit gameplay.
    """
    if type(kind) is not str or kind not in ("material", "mob"):
        raise ValueError("Unknown farming target kind")
    if (not isinstance(preflight, dict)
            or preflight.get("status") != "CALIBRATION_REQUIRED"
            or preflight.get("can_start") is not False):
        raise ValueError("A blocked calibration preflight is required")

    family = preflight.get("source_family")
    if kind == "material" and family in _NON_MOB_FAMILIES:
        return _non_mob_guide(preflight)

    source_state = preflight.get("source_check")
    route_state = preflight.get("route_check")
    identity_state = preflight.get("identity_check")
    version_state = preflight.get("game_version_check")
    if (source_state not in ("HISTORICAL_ONLY", "MISSING_OR_INVALID", "NOT_APPLICABLE")
            or route_state not in ("STATIC_ONLY", "MISSING_OR_INVALID", "NO_VERIFIED_MOB_ROUTE")
            or identity_state not in ("HISTORICAL_ID_OVERLAP_ONLY", "UNRESOLVED")
            or version_state not in (
                "VERSION_NOT_OBSERVED", "VERSION_NOT_COMPARABLE",
                "HISTORICAL_EQUAL_UNVERIFIED", "HISTORICAL_VERSION_MISMATCH",
                "CONFLICTING_HISTORICAL_VERSIONS",
            )):
        raise ValueError("Unrecognized calibration preflight fields")

    material = kind == "material"
    if material and source_state == "NOT_APPLICABLE":
        raise ValueError("Material source cannot be not applicable")
    if not material and source_state != "NOT_APPLICABLE":
        raise ValueError("Mob discovery must not claim material-source evidence")

    steps = []
    if material:
        steps.append(_step(
            "observe-material-drop", "Confirm an actual material drop",
            "In an authorized local session, capture distinct item-detail inventory "
            "observations before and after the specific enemy encounter. Have an "
            "independent reviewer confirm the item, positive quantity delta, "
            "enemy identity, frame sequence and no ambiguous pickup.",
            historical=source_state == "HISTORICAL_ONLY",
        ))
    steps.append(_step(
        "identify-game-enemy", "Confirm exact game enemy identity",
        "Independently identify the numeric in-game enemy ID and map-source "
        "identity in the current client. Never translate a wiki/display name "
        "to a numeric ID by guessing.",
        historical=material and identity_state == "HISTORICAL_ID_OVERLAP_ONLY",
    ))
    steps.append(_step(
        "observe-installed-version", "Observe the installed game and runtime versions",
        "Read the installed versions from the current trusted game and automation "
        "runtime. Historical labels and user-supplied version text do not count.",
    ))
    steps.append(_step(
        "calibrate-reviewed-route", "Calibrate a bounded surface route",
        "Record verified map layer, observed spawn and 1–3 safe camp segments. "
        "Independently check every waypoint, profile/evidence digest and "
        "localization tolerance. This is not permission to travel or fight.",
        historical=material and route_state == "STATIC_ONLY",
    ))
    steps.append(_step(
        "review-runtime-qualification", "Obtain independent runtime qualification",
        "Codex and an independent reviewer must verify the current-version, "
        "SHA-bound stage-specific qualification against the actual runtime, "
        "not merely against historical metadata.",
    ))
    steps.append(_step(
        "verify-live-inventory", "Verify fresh inventory and stop goal",
        "Read the current item total and confirm receipt-based positive deltas, "
        "bounded attempts and the requested stopping goal. A combat victory "
        "or pickup animation is not an inventory receipt.",
    ))
    steps.append(_step(
        "verify-input-safety", "Verify exclusive input and cancellation guards",
        "Independently test fresh frames, focus/privilege checks, exclusive "
        "session ownership, pause, cancel, held-input cleanup, no-skip Story "
        "Watch, zero spending and fail-closed recovery.",
    ))

    if material and source_state != "HISTORICAL_ONLY":
        next_step_id = "observe-material-drop"
    elif material and route_state != "STATIC_ONLY":
        next_step_id = "calibrate-reviewed-route"
    elif identity_state != "HISTORICAL_ID_OVERLAP_ONLY":
        next_step_id = "identify-game-enemy"
    elif version_state in (
        "HISTORICAL_VERSION_MISMATCH", "CONFLICTING_HISTORICAL_VERSIONS",
        "VERSION_NOT_OBSERVED", "VERSION_NOT_COMPARABLE",
        "HISTORICAL_EQUAL_UNVERIFIED",
    ):
        next_step_id = "observe-installed-version"
    elif route_state != "STATIC_ONLY":
        next_step_id = "calibrate-reviewed-route"
    else:
        next_step_id = "review-runtime-qualification"

    # A historical version equality never closes the live version step.
    # Missing route metadata blocks any meaningful numeric-ID cross-check.

    return {
        "mode": "GUIDED_READ_ONLY",
        "next_step_id": next_step_id,
        "steps": steps,
        "verified_step_count": 0,
        "can_start": False,
        "notice": (
            "Historical references help plan calibration; none of these steps "
            "have been live-qualified by this screen."
        ),
    }
