"""Material goals and source selection; unknown mappings stay unresolved.

MaterialGoal/quantity parsing are adapted from EEEEEEEdison's upstream PR #1837
(61464cb8). Upstream license and attribution apply to the adapted implementation.
"""
from dataclasses import dataclass
import re
import unicodedata

from src.automation.resource_policy import ResourcePolicyError, verify_inventory


# Only these existing executors can consume their matching resource source.
# A reviewed source mapping must not turn a Forgery/Tacet/Simulation reward
# into an overworld hunt, or route a boss claim through another producer.
_SOURCE_EXECUTORS = {
    'boss': frozenset({'CultivationTask'}),
    'domain': frozenset({'ForgeryTask', 'SimulationTask', 'TacetTask'}),
    'overworld': frozenset({'BoundedRouteTask'}),
}


def compact_text(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def parse_quantity(text):
    match = re.fullmatch(r'([0-9]{1,7})/([0-9]{1,7})', compact_text(text))
    if match is None or int(match[2]) == 0:
        return None
    return int(match[1]), int(match[2])


@dataclass
class MaterialGoal:
    name: str
    owned: int
    required: int
    origin: str = 'native_verified'
    evidence: str = ''

    def __post_init__(self):
        if not self.name or type(self.owned) is not int or type(self.required) is not int:
            raise ResourcePolicyError('A named material and integer inventory/target are required')
        if self.owned < 0 or self.required <= 0 or self.origin not in ('native_verified', 'user_supplied'):
            raise ResourcePolicyError('Invalid material goal or unlabelled target origin')

    @property
    def missing(self):
        return max(0, self.required - self.owned)


@dataclass(frozen=True)
class SourceMapping:
    material: str
    kind: str
    executor: str
    profile: str
    evidence: str
    runtime: str
    qualified: bool = False

    def matches(self, goal, runtime):
        return (self.material == goal.name
                and self.executor in _SOURCE_EXECUTORS.get(self.kind, ())
                and isinstance(self.profile, str) and bool(self.profile.strip())
                and isinstance(self.evidence, str) and bool(self.evidence.strip())
                and isinstance(self.runtime, str) and bool(self.runtime)
                and self.runtime == runtime and self.qualified is True)


@dataclass
class GoalProgress:
    combat_succeeded: bool = False
    reward_confirmed: bool = False
    reward_received: bool = False
    goal_complete: bool = False
    reason: str = 'unresolved source'


class ResourceGoalQueue:
    """Planning/observation layer consumed by the existing OK task scheduler.

    It neither creates threads nor bypasses task execution/input ownership.
    Mappings require exact material, runtime and calibration/evidence identities.
    """
    def __init__(self, goals=(), mappings=()):
        self.goals = list(goals)
        if any(g.origin == 'native_verified' and not g.evidence for g in self.goals):
            raise ResourcePolicyError('Native goals require observed Guidebook/item-detail evidence')
        if len({g.name for g in self.goals}) != len(self.goals):
            raise ResourcePolicyError('Duplicate material goals are ambiguous')
        self.mappings = list(mappings)
        self.progress = {g.name: GoalProgress(goal_complete=g.missing == 0) for g in self.goals}

    def preview(self, runtime):
        result = []
        for goal in self.goals:
            choices = [s for s in self.mappings if s.matches(goal, runtime)]
            source = choices[0] if len(choices) == 1 else None
            if not goal.missing:
                status, reason = 'COMPLETE', 'Configured material target is already met.'
            elif len(choices) > 1:
                status, reason = 'UNRESOLVED', 'Ambiguous: multiple qualified source mappings.'
            elif source is None:
                status, reason = (
                    'UNRESOLVED',
                    'No compatible, uniquely qualified source for this material and runtime. '
                    'Verify the source kind, matching task, evidence and current version.',
                )
            else:
                status, reason = (
                    'READY',
                    'Mapping candidate only; inherited task runtime, identity, '
                    'spending and post-dispatch inventory gates must still pass.',
                )
            result.append({'material': goal.name, 'owned': goal.owned, 'target': goal.required,
                           'origin': goal.origin, 'deficit': goal.missing,
                           'executor': source.executor if source else None,
                           'profile': source.profile if source else None,
                           'state': status, 'reason': reason})
        return result

    def next_source(self, runtime):
        for goal in self.goals:
            if goal.missing:
                choices = [s for s in self.mappings if s.matches(goal, runtime)]
                if len(choices) == 1:
                    return goal, choices[0]
        return None

    def observe_stage(self, material, *, combat=False, confirmation=False):
        state = self.progress[material]
        state.combat_succeeded |= combat
        state.reward_confirmed |= confirmation
        # A kill or confirmation never updates owned or goal_complete.

    def receive(self, inventory, *, materials=None):
        selected = self.goals if materials is None else [g for g in self.goals if g.name in materials]
        if materials is not None and {g.name for g in selected} != set(materials):
            raise ResourcePolicyError('Unknown goal in inventory batch')
        before = {g.name: g.owned for g in selected}
        verify_inventory(before, inventory)
        for goal in selected:
            goal.owned = inventory[goal.name]
            state = self.progress[goal.name]
            state.reward_received = inventory[goal.name] > before[goal.name]
            state.goal_complete = goal.missing == 0
            state.reason = 'actual inventory verified'
