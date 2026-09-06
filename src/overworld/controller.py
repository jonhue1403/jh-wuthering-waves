"""Surface hunt orchestration; no OK-Script, input, or recognition imports."""

from dataclasses import dataclass, field
from enum import Enum
import time

from .models import HuntSession, TravelMode
from .navigation import NavigationStatus


class HuntState(str, Enum):
    INITIALIZE = "INITIALIZE"
    LOCALIZE = "LOCALIZE"
    PLAN = "PLAN"
    TRAVELLING = "TRAVELLING"
    APPROACH = "APPROACH"
    COMBAT = "COMBAT"
    CLEAR_CHECK = "CLEAR_CHECK"
    CLEARED = "CLEARED"
    RETRY = "RETRY"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class HuntCancelled(Exception):
    pass


class HuntAbort(RuntimeError):
    """A session-wide dependency failure, such as lost localization or death."""


@dataclass(frozen=True)
class HuntOptions:
    max_camps: int = 1
    max_retries: int = 2
    arrival_radius: float = 100
    navigation_timeout: float = 60
    clear_seconds: float = 3
    check_interval: float = 0.25
    max_interruptions: int = 6

    def __post_init__(self):
        if self.max_camps < 1 or self.max_retries < 0 or self.max_interruptions < 1:
            raise ValueError("Invalid hunt attempt limits")
        if min(self.arrival_radius, self.navigation_timeout,
               self.clear_seconds, self.check_interval) <= 0:
            raise ValueError("Hunt distances and time limits must be positive")


@dataclass
class HuntRun:
    session: HuntSession = field(default_factory=HuntSession)
    state: HuntState = HuntState.INITIALIZE
    attempts: dict[str, int] = field(default_factory=dict)
    interruptions: dict[str, int] = field(default_factory=dict)
    visited: set[str] = field(default_factory=set)
    errors: dict[str, str] = field(default_factory=dict)
    reason: str = ""
    replan_reason: str = "initial localization"


class HuntController:
    """Runtime supplies locate/in_combat/enemy_present/combat_once/wait/cancelled.

    Only the first planner step is consumed. Every combat, failed attempt, and
    clear discards that plan and starts again from an actual localization.
    """

    def __init__(self, planner, navigator, runtime, *, options=None, clock=time.monotonic):
        self.planner = planner
        self.navigator = navigator
        self.runtime = runtime
        self.options = options or HuntOptions()
        self.clock = clock
        self.run_state = HuntRun()

    def _state(self, state, camp=None):
        self.run_state.state = state
        self.runtime.report(state, camp, self.run_state)

    def _check_cancel(self):
        if self.runtime.cancelled():
            raise HuntCancelled()

    def _stop(self):
        if self.navigator.stop() is False:
            raise HuntAbort("Navigation input release failed; combat handoff refused")

    def _locate(self, layer):
        self._stop()
        self._check_cancel()
        position = self.runtime.locate()
        if position is None or (position.state_id, position.floor_id) != layer:
            raise HuntAbort("Player localization lost or outside the selected surface area")
        self.run_state.session.set_current_position(position)
        self._state(HuntState.LOCALIZE)
        return position

    def _failed(self, camp, reason):
        run = self.run_state
        count = run.attempts.get(camp.camp_id, 0) + 1
        run.attempts[camp.camp_id] = count
        run.errors[camp.camp_id] = reason
        run.replan_reason = f"camp attempt failed: {reason}"
        if count > self.options.max_retries:
            run.session.mark_failed(camp.camp_id)
            self._state(HuntState.FAILED, camp)
        else:
            self._state(HuntState.RETRY, camp)

    def _combat(self, camp, layer):
        self._stop()
        self._check_cancel()
        self._state(HuntState.COMBAT, camp)
        failed = False
        try:
            self.runtime.combat_once()
        except (HuntCancelled, HuntAbort):
            raise
        except Exception as error:
            self._failed(camp, f"Combat failed: {error}")
            failed = True
        finally:
            self._stop()
        self.run_state.replan_reason = "post-combat actual position"
        self._locate(layer)
        if failed:
            return
        count = self.run_state.interruptions.get(camp.camp_id, 0) + 1
        self.run_state.interruptions[camp.camp_id] = count
        if count >= self.options.max_interruptions:
            self._failed(camp, "Combat interruption budget exhausted")
            self.run_state.interruptions[camp.camp_id] = 0

    def _navigation_result(self, result, camp, layer):
        self._stop()
        self._check_cancel()
        if result.status is NavigationStatus.CANCELLED:
            raise HuntCancelled()
        if result.status is NavigationStatus.COMBAT:
            self._combat(camp, layer)
            return False
        if result.status is not NavigationStatus.ARRIVED:
            self._failed(camp, str(result.error or result.status.value))
            return False
        return True

    def run(self, target, spawns, *, layer):
        self.run_state = HuntRun()
        run = self.run_state
        # The runtime profile attests surface status; never infer it from a blank floor id.
        spawns = tuple(s for s in spawns if (s.state_id, s.floor_id) == layer)
        try:
            self._state(HuntState.INITIALIZE)
            while True:
                self._locate(layer)
                self._state(HuntState.PLAN)
                plan = self.planner.plan(target, spawns, session=run.session)
                if not plan.steps or plan.steps[0].mode is not TravelMode.WALK:
                    run.reason = "No remaining locally walkable camps"
                    break
                camp = plan.steps[0].camp
                if camp.camp_id not in run.visited and len(run.visited) >= self.options.max_camps:
                    run.reason = "Max Camps reached"
                    break
                run.visited.add(camp.camp_id)
                kwargs = dict(arrival_threshold=self.options.arrival_radius,
                              timeout=self.options.navigation_timeout,
                              stop_condition=self.runtime.cancelled)
                self._state(HuntState.TRAVELLING, camp)
                result = self.navigator.follow_to(camp.position, **kwargs)
                if not self._navigation_result(result, camp, layer):
                    continue
                # Visit each known spawn; a centroid alone does not prove camp coverage.
                self._state(HuntState.APPROACH, camp)
                result = self.navigator.follow_waypoints([s.position for s in camp.spawns], **kwargs)
                if not self._navigation_result(result, camp, layer):
                    continue
                self._state(HuntState.CLEAR_CHECK, camp)
                started = self.clock()
                clear = True
                while True:
                    self._check_cancel()
                    if self.runtime.in_combat():
                        self._combat(camp, layer)
                        clear = False
                        break
                    if self.runtime.enemy_present():
                        self._failed(camp, "Enemy evidence remains after approach")
                        clear = False
                        break
                    # Verify actual location throughout the check, including its end.
                    position = self.runtime.locate()
                    if (position is None or (position.state_id, position.floor_id) != layer
                            or min(position.coordinate.distance_to(s.coordinate)
                                   for s in camp.spawns) > self.options.arrival_radius * 2):
                        self._failed(camp, "Clear check lost camp localization")
                        clear = False
                        break
                    if self.clock() - started >= self.options.clear_seconds:
                        break
                    self.runtime.wait(self.options.check_interval)
                if clear:
                    # The final clear-check sample is fresh and still inside the
                    # camp. Store it before announcing or marking completion.
                    run.session.set_current_position(position)
                    run.session.mark_cleared(camp.camp_id)
                    run.replan_reason = "camp clear verified"
                    self._state(HuntState.CLEARED, camp)
            self._state(HuntState.COMPLETE)
        except HuntCancelled:
            run.reason = "Task cancelled"
            self._state(HuntState.CANCELLED)
        except Exception as error:
            run.reason = str(error)
            self._state(HuntState.FAILED)
            raise
        finally:
            self._stop()
        return run
