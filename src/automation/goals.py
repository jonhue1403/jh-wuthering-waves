"""Material goals and source selection; unknown mappings stay unresolved.

MaterialGoal/quantity parsing are adapted from EEEEEEEdison's upstream PR #1837
(61464cb8). Upstream license and attribution apply to the adapted implementation.
"""
from dataclasses import dataclass
import re
import unicodedata

from src.automation.resource_policy import ResourcePolicyError, verify_inventory


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
        return (self.material == goal.name and self.kind in ('boss', 'domain', 'overworld')
                and self.executor and self.profile and self.evidence
                and self.runtime == runtime and self.qualified)


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
            result.append({'material': goal.name, 'owned': goal.owned, 'target': goal.required,
                           'origin': goal.origin, 'deficit': goal.missing,
                           'executor': source.executor if source else None,
                           'profile': source.profile if source else None,
                           'state': 'COMPLETE' if not goal.missing else 'READY' if source else 'UNRESOLVED'})
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
