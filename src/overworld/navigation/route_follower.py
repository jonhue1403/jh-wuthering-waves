"""Generic route following independent of mobs, maps, or combat policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from typing import Callable, Generic, Protocol, Sequence, TypeVar

from .stuck_recovery import (
    RecoveryOutcome,
    RecoveryStage,
    SlidingWindowStuckDetector,
    StuckRecovery,
)


Waypoint = TypeVar("Waypoint")


class NavigationStatus(str, Enum):
    ARRIVED = "ARRIVED"
    COMBAT = "COMBAT"
    STUCK = "STUCK"
    TIMEOUT = "TIMEOUT"
    LOST_LOCALIZATION = "LOST_LOCALIZATION"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class WaypointObservation:
    distance: float
    bearing: float
    position: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class MovementState:
    direction: str | None = None
    adjustment: str | None = None

    @property
    def active(self) -> bool:
        return self.direction is not None or self.adjustment is not None


@dataclass(frozen=True, slots=True)
class NavigationResult(Generic[Waypoint]):
    status: NavigationStatus
    waypoint: Waypoint | None = None
    waypoint_index: int | None = None
    recovery_attempts: int = 0
    error: Exception | None = None


class NavigationBackend(Protocol[Waypoint]):
    """Device/runtime adapter used by :class:`WorldRouteNavigator`."""

    def next_frame(self) -> None:
        ...

    def observe(self, waypoint: Waypoint) -> WaypointObservation | None:
        ...

    def in_combat(self) -> bool:
        ...

    def navigate(self, observation: WaypointObservation, state: MovementState) -> MovementState:
        ...

    def stop(self, state: MovementState) -> None:
        ...

    def recover(self, stage: RecoveryStage) -> None:
        ...


class WorldRouteNavigator(Generic[Waypoint]):
    """Follow a target or ordered waypoints using a caller-provided backend."""

    def __init__(
        self,
        backend: NavigationBackend[Waypoint],
        *,
        clock: Callable[[], float] = time.monotonic,
        stuck_window_seconds: float = 2.0,
        position_threshold: float = 4.0,
        distance_threshold: float = 4.0,
        max_recovery_attempts: int | None = None,
        cancellation_exceptions: tuple[type[Exception], ...] = (),
        diagnostic=None,
    ):
        self.backend = backend
        self.clock = clock
        self.stuck_window_seconds = stuck_window_seconds
        self.position_threshold = position_threshold
        self.distance_threshold = distance_threshold
        self.max_recovery_attempts = max_recovery_attempts
        self.cancellation_exceptions = cancellation_exceptions
        self.diagnostic = diagnostic or (lambda *args, **kwargs: None)
        self._movement_state = MovementState()

    def follow_to(
        self,
        waypoint: Waypoint,
        *,
        arrival_threshold: float,
        timeout: float | None = None,
        stop_condition: Callable[[], bool] | None = None,
        far_distance: float | None = None,
        max_far_observations: int | None = None,
        on_far: Callable[[WaypointObservation], None] | None = None,
    ) -> NavigationResult[Waypoint]:
        result = self._follow(
            (waypoint,),
            start_index=0,
            arrival_threshold=arrival_threshold,
            timeout=timeout,
            stop_condition=stop_condition,
            far_distance=far_distance,
            max_far_observations=max_far_observations,
            on_far=on_far,
        )
        return self._report_result(result)

    def follow_waypoints(
        self,
        waypoints: Sequence[Waypoint],
        *,
        arrival_threshold: float,
        start_index: int = 0,
        timeout: float | None = None,
        stop_condition: Callable[[], bool] | None = None,
        far_distance: float | None = None,
        max_far_observations: int | None = None,
        on_far: Callable[[WaypointObservation], None] | None = None,
    ) -> NavigationResult[Waypoint]:
        if start_index < 0 or start_index > len(waypoints):
            raise ValueError("start_index is outside the waypoint sequence")
        if not waypoints or start_index == len(waypoints):
            return NavigationResult(NavigationStatus.ARRIVED, waypoint_index=start_index)
        result = self._follow(
            waypoints,
            start_index=start_index,
            arrival_threshold=arrival_threshold,
            timeout=timeout,
            stop_condition=stop_condition,
            far_distance=far_distance,
            max_far_observations=max_far_observations,
            on_far=on_far,
        )
        return self._report_result(result)

    def _report_result(self, result):
        self.diagnostic("navigation_result", status=result.status.value,
                        waypoint=str(result.waypoint), waypoint_index=result.waypoint_index,
                        recovery_attempts=result.recovery_attempts, error=str(result.error or ""))
        return result

    def _recover(self, stage):
        self.diagnostic("recovery_stage", stage=stage.value)
        self.backend.recover(stage)

    def stop(self) -> bool:
        """Release movement/camera controls even when no direction is tracked."""
        try:
            self.backend.stop(self._movement_state)
            self.diagnostic("navigation_cleanup", success=True)
            return True
        except Exception as error:
            # Cleanup must not hide the structured navigation result. The
            # backend is still given the opportunity to release controls.
            self.diagnostic("navigation_cleanup", success=False, error=str(error))
            return False
        finally:
            self._movement_state = MovementState()

    def _follow(
        self,
        waypoints: Sequence[Waypoint],
        *,
        start_index: int,
        arrival_threshold: float,
        timeout: float | None,
        stop_condition: Callable[[], bool] | None,
        far_distance: float | None,
        max_far_observations: int | None,
        on_far: Callable[[WaypointObservation], None] | None,
    ) -> NavigationResult[Waypoint]:
        if arrival_threshold < 0:
            raise ValueError("arrival threshold cannot be negative")
        started = self.clock()
        far_observations = 0
        recovery = StuckRecovery(
            perform=self._recover,
            max_attempts=self.max_recovery_attempts,
        )
        detector = SlidingWindowStuckDetector(
            window_seconds=self.stuck_window_seconds,
            position_threshold=self.position_threshold,
            distance_threshold=self.distance_threshold,
            clock=self.clock,
        )
        current_index = start_index

        try:
            while current_index < len(waypoints):
                waypoint = waypoints[current_index]
                if stop_condition and stop_condition():
                    return NavigationResult(NavigationStatus.CANCELLED, waypoint, current_index,
                                             recovery.attempts)
                if timeout is not None and self.clock() - started >= timeout:
                    return NavigationResult(NavigationStatus.TIMEOUT, waypoint, current_index,
                                             recovery.attempts)
                if self.backend.in_combat():
                    self.stop()
                    return NavigationResult(NavigationStatus.COMBAT, waypoint, current_index,
                                             recovery.attempts)

                self.backend.next_frame()
                if self.backend.in_combat():
                    self.stop()
                    return NavigationResult(NavigationStatus.COMBAT, waypoint, current_index,
                                             recovery.attempts)
                observation = self.backend.observe(waypoint)
                if stop_condition and stop_condition():
                    return NavigationResult(NavigationStatus.CANCELLED, waypoint, current_index,
                                             recovery.attempts)
                if timeout is not None and self.clock() - started >= timeout:
                    return NavigationResult(NavigationStatus.TIMEOUT, waypoint, current_index,
                                             recovery.attempts)
                if observation is None:
                    return NavigationResult(NavigationStatus.LOST_LOCALIZATION, waypoint, current_index,
                                             recovery.attempts)
                self.diagnostic("navigation_progress", distance=observation.distance,
                                bearing=observation.bearing, xy=observation.position)
                if self.backend.in_combat():
                    self.stop()
                    return NavigationResult(NavigationStatus.COMBAT, waypoint, current_index,
                                             recovery.attempts)
                if observation.distance <= arrival_threshold:
                    current_index += 1
                    detector.reset()
                    recovery.reset()
                    continue
                if far_distance is not None and observation.distance >= far_distance:
                    far_observations += 1
                    if on_far:
                        on_far(observation)
                    if max_far_observations is not None and far_observations >= max_far_observations:
                        return NavigationResult(NavigationStatus.LOST_LOCALIZATION, waypoint, current_index,
                                                 recovery.attempts)
                    continue

                self._movement_state = self.backend.navigate(observation, self._movement_state)
                if detector.record(
                    position=observation.position,
                    distance=observation.distance,
                    movement_active=self._movement_state.active,
                ):
                    self.diagnostic("stuck_detected", distance=observation.distance,
                                    xy=observation.position, recovery_attempts=recovery.attempts)
                    self.stop()
                    outcome, _ = recovery.attempt()
                    detector.reset()
                    if outcome is RecoveryOutcome.EXHAUSTED:
                        return NavigationResult(NavigationStatus.STUCK, waypoint, current_index,
                                                 recovery.attempts)
        except Exception as error:
            if isinstance(error, self.cancellation_exceptions):
                return NavigationResult(NavigationStatus.CANCELLED, waypoints[current_index],
                                         current_index, recovery.attempts, error)
            return NavigationResult(NavigationStatus.FAILED, waypoints[current_index], current_index,
                                     recovery.attempts, error)
        finally:
            self.stop()

        final_waypoint = waypoints[current_index - 1] if current_index > start_index else None
        return NavigationResult(NavigationStatus.ARRIVED, waypoint=final_waypoint,
                                 waypoint_index=current_index, recovery_attempts=recovery.attempts)
