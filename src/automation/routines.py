"""Daily/weekly coordination over inherited OK tasks, never a second executor."""
from dataclasses import dataclass
import time

from src.automation.resource_policy import ClaimIdentity, ResourcePolicyError, UncertainReceipt


# Weekly boss Echo runs deliberately do not represent material reward eligibility.
INHERITED_ACTIVITIES = {
    'daily': ('src.task.DailyTask', 'DailyTask'),
    'tacet': ('src.task.TacetTask', 'TacetTask'),
    'forgery': ('src.task.ForgeryTask', 'ForgeryTask'),
    'simulation': ('src.task.SimulationTask', 'SimulationTask'),
    'boss_echo': ('src.task.FarmEchoTask', 'FarmEchoTask'),
    'nightmare_nest': ('src.task.NightmareNestTask', 'NightmareNestTask'),
    'garden': ('src.task.GardenTask', 'GardenTask'),
}


@dataclass(frozen=True)
class RoutineObservation:
    account: str
    server: str
    activity: str
    cycle: str
    observed_at: float
    eligible: bool
    completed: bool
    evidence: str
    reward_received: bool = False
    weekly_claims_remaining: int | None = None
    profile: str = ''
    qualified: bool = False

    @property
    def identity(self):
        return ClaimIdentity(self.account, self.server, self.activity, self.cycle)


class RoutineCoordinator:
    """One bounded scheduler dispatch with verified pre/postconditions.

    Observers must read the game through ordinary capture/OCR. There are no
    bundled screenshots for current Fantasies Weekly Activity or weekly boss
    reward eligibility, so those entries remain unresolved until calibrated.
    """
    def __init__(self, journal, budget, *, clock=time.time, max_frame_age=2):
        self.journal, self.budget = journal, budget
        self.clock, self.max_frame_age = clock, max_frame_age

    def _validate(self, observation):
        age = self.clock() - observation.observed_at
        if age < 0 or age > self.max_frame_age or not observation.evidence:
            raise ResourcePolicyError('Fresh observed routine state required')
        observation.identity  # Reject date-only/unknown account, server or cycle.
        if not observation.qualified or not observation.profile:
            raise ResourcePolicyError('Routine profile is not qualified on this game/runtime')

    def preview(self, observation):
        self._validate(observation)
        if observation.activity in ('fantasies', 'weekly_boss_material'):
            if observation.activity == 'weekly_boss_material' and observation.weekly_claims_remaining is None:
                return 'UNRESOLVED: weekly material claim eligibility is unreadable'
            return 'UNRESOLVED: no qualified current Weekly Activity/material reward adapter'
        if observation.activity not in INHERITED_ACTIVITIES:
            return 'UNRESOLVED: unknown activity'
        if observation.completed or self.journal.is_completed(observation.identity):
            return 'COMPLETE'
        if self.journal.activity_state(observation.identity) in ('PENDING', 'UNCERTAIN'):
            return 'UNCERTAIN: reconcile interrupted routine before resuming'
        if self.journal.unresolved(observation.identity):
            return 'UNCERTAIN: reconcile interrupted action before resuming'
        return 'READY' if observation.eligible else 'INELIGIBLE'

    def run_one(self, before, *, dispatch, observe_after, checkpoint):
        """dispatch uses existing run_task_by_class; checkpoint owns cancellation/time."""
        status = self.preview(before)
        if status != 'READY':
            return status
        checkpoint()
        started = time.monotonic()
        if not self.journal.begin_activity(before.identity, before.evidence):
            return 'COMPLETE'
        try:
            dispatch(INHERITED_ACTIVITIES[before.activity])
            checkpoint()
            if time.monotonic() - started >= self.budget.max_seconds:
                raise ResourcePolicyError('Routine execution time limit exceeded')
            after = observe_after()
            self._validate(after)
            if after.identity != before.identity or after.observed_at <= before.observed_at:
                raise UncertainReceipt('Routine identity/cycle changed or postcondition frame is stale')
            if not after.completed or not after.reward_received:
                raise UncertainReceipt('Task returned without verified completion and reward receipt')
            self.journal.complete(after.identity, after.evidence)
        except BaseException as error:
            self.journal.uncertain_activity(before.identity, error)
            raise
        return 'COMPLETE'
