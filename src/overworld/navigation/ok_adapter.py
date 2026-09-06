"""Adapter from the generic navigator to the existing OK-WW task helpers."""

from __future__ import annotations

from typing import Callable, TypeVar

from .route_follower import MovementState, NavigationBackend, WaypointObservation
from .stuck_recovery import RecoveryStage


Waypoint = TypeVar("Waypoint")


class WWTaskNavigationBackend(NavigationBackend[Waypoint]):
    """Keep OK-WW input and bearing logic behind the generic route follower."""

    def __init__(
        self,
        task,
        observe: Callable[[Waypoint], WaypointObservation | None],
    ):
        self.task = task
        self._observe = observe

    def next_frame(self) -> None:
        self.task.sleep(0.01)
        self.task.middle_click(interval=1, after_sleep=0.2)

    def observe(self, waypoint: Waypoint) -> WaypointObservation | None:
        return self._observe(waypoint)

    def in_combat(self) -> bool:
        return self.task.in_combat()

    def navigate(self, observation: WaypointObservation, state: MovementState) -> MovementState:
        direction, adjustment, _ = self.task._navigate_based_on_angle(
            observation.bearing, state.direction, state.adjustment
        )
        return MovementState(direction, adjustment)

    def stop(self, state: MovementState) -> None:
        errors = []
        keys = dict.fromkeys(("w", "a", "s", "d", "space", state.direction, state.adjustment))
        config = getattr(self.task, "key_config", {})
        keys[config.get("Tool Key", "t")] = None
        keys[config.get("Jump Key", "space")] = None
        for key in keys:
            if key is not None:
                try:
                    self.task.send_key_up(key)
                except Exception as error:
                    errors.append(error)
        for button in ("right", "middle"):
            try:
                self.task.mouse_up(key=button)
            except Exception as error:
                errors.append(error)
        if errors:
            raise errors[0]

    def recover(self, stage: RecoveryStage) -> None:
        """Perform one short, bounded recovery action using OK-WW helpers."""
        if stage is RecoveryStage.RECENTER:
            self.task.center_camera()
        elif stage is RecoveryStage.JUMP_FORWARD:
            self.task.send_key("space", down_time=0.02, after_sleep=0.1)
            self._short_direction("w")
        elif stage is RecoveryStage.RIGHT_DETOUR:
            self._short_direction("d")
        elif stage is RecoveryStage.LEFT_DETOUR:
            self._short_direction("a")
        elif stage is RecoveryStage.UTILITY:
            self.task.send_key(self.task.key_config.get("Tool Key", "t"),
                               down_time=0.02, after_sleep=0.1)
        elif stage is RecoveryStage.BACKUP:
            self._short_direction("s")
        elif stage is RecoveryStage.REQUEST_RELOCALIZATION:
            self.task.log_info("requesting relocalization after stuck recovery")

    def _short_direction(self, direction: str) -> None:
        self.task.send_key_down(direction)
        try:
            self.task.sleep(0.5)
        finally:
            self.task.send_key_up(direction)
