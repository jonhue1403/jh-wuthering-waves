"""Strict static selector checks for inherited domain tasks.

These guards prevent malformed or stale local F2 selector values from silently
choosing another challenge. A valid index/name is only code-shape validation:
it NEVER proves the current game's challenge identity, availability, material
drop, resource permission or executable qualification.
"""
from src.automation.resource_policy import ResourcePolicyError


# Bounds reflect the checked-in F2 structures, not observed live-game slots.
# If the inherited task structure changes, update and review this table too.
DOMAIN_SELECTORS = {
    'ForgeryTask': ('Which Forgery Challenge to Farm', 20),
    'SimulationTask': ('Material Selection', None),
    'TacetTask': ('Which Tacet Suppression to Farm', 21),
}
SIMULATION_OPTIONS = frozenset(('Resonator EXP', 'Weapon EXP', 'Shell Credit'))


def validate_domain_selector(executor: str, value: object, *, count: int | None = None) -> int | str:
    """Reject unintended fallback selection before F2 navigation or spending."""
    if executor not in DOMAIN_SELECTORS:
        raise ResourcePolicyError('Unsupported domain selector task')
    key, expected_count = DOMAIN_SELECTORS[executor]
    if expected_count is None:
        if type(value) is not str or value not in SIMULATION_OPTIONS:
            raise ResourcePolicyError(f'{key}: choose one recognized native task option; no fallback')
    else:
        if count is not None and (type(count) is not int or count != expected_count):
            raise ResourcePolicyError(f'{executor}: local F2 layout drift; review selector bounds')
        if type(value) is not int or not 1 <= value <= expected_count:
            raise ResourcePolicyError(f'{key}: expected 1..{expected_count}, not a boolean or fallback')
    return value


def inspect_domain_selector(executor: str, overrides: object) -> str:
    """Plan-only diagnostics. No defaults imply a verified native challenge."""
    if executor not in DOMAIN_SELECTORS:
        return 'STATIC_SELECTOR_UNSUPPORTED'
    key, _ = DOMAIN_SELECTORS[executor]
    if type(overrides) is not dict:
        return 'STATIC_SELECTOR_INVALID: task overrides must be a mapping'
    if key not in overrides:
        return 'STATIC_SELECTOR_MISSING: explicit native task option not supplied'
    try:
        validate_domain_selector(executor, overrides[key])
    except ResourcePolicyError as error:
        return f'STATIC_SELECTOR_INVALID: {error}'
    return ('STATIC_SELECTOR_SHAPE_ONLY: local option is well formed; '
            'CURRENT_GAME_CHALLENGE_UNOBSERVED; no source or spending permission')
