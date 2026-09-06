"""Bounded, state-free stuck detection and recovery sequencing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import Callable, Deque


class RecoveryStage(str, Enum):
    RECENTER = "recenter"
    JUMP_FORWARD = "jump_forward"
    RIGHT_DETOUR = "right_detour"
    LEFT_DETOUR = "left_detour"
    UTILITY = "utility"
    BACKUP = "backup"
    REQUEST_RELOCALIZATION = "request_relocalization"


class RecoveryOutcome(str, Enum):
    ATTEMPTED = "attempted"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class ProgressSample:
    timestamp: float
    position: tuple[float, float] | None
    distance: float


class SlidingWindowStuckDetector:
    """Detect insufficient progress over a bounded time window.

    Detection requires both little position movement and little distance
    improvement. In particular, it never depends on exact float equality.
    """

    def __init__(
        self,
        *,
        window_seconds: float = 2.0,
        position_threshold: float = 4.0,
        distance_threshold: float = 4.0,
        clock: Callable[[], float],
    ):
        if window_seconds <= 0:
            raise ValueError("stuck window must be positive")
        if position_threshold < 0 or distance_threshold < 0:
            raise ValueError("stuck thresholds cannot be negative")
        self.window_seconds = window_seconds
        self.position_threshold = position_threshold
        self.distance_threshold = distance_threshold
        self.clock = clock
        self._samples: Deque[ProgressSample] = deque()

    def reset(self) -> None:
        self._samples.clear()

    def record(
        self,
        *,
        position: tuple[float, float] | None,
        distance: float,
        movement_active: bool,
        timestamp: float | None = None,
    ) -> bool:
        if not movement_active or position is None:
            self.reset()
            return False

        now = self.clock() if timestamp is None else timestamp
        self._samples.append(ProgressSample(now, position, distance))
        cutoff = now - self.window_seconds
        # Keep the sample immediately before the cutoff. Dropping every older
        # sample makes elapsed < window forever with irregular frame timings.
        while len(self._samples) > 1 and self._samples[1].timestamp <= cutoff:
            self._samples.popleft()

        if len(self._samples) < 2:
            return False
        first = self._samples[0]
        elapsed = now - first.timestamp
        position_movement = hypot(
            position[0] - first.position[0], position[1] - first.position[1]
        )
        distance_improvement = first.distance - distance
        return (
            elapsed >= self.window_seconds
            and position_movement <= self.position_threshold
            and distance_improvement <= self.distance_threshold
        )


class StuckRecovery:
    """Run a finite recovery sequence and report when it is exhausted."""

    DEFAULT_STAGES = (
        RecoveryStage.RECENTER,
        RecoveryStage.JUMP_FORWARD,
        RecoveryStage.RIGHT_DETOUR,
        RecoveryStage.LEFT_DETOUR,
        RecoveryStage.UTILITY,
        RecoveryStage.BACKUP,
        RecoveryStage.REQUEST_RELOCALIZATION,
    )

    def __init__(
        self,
        *,
        perform: Callable[[RecoveryStage], None],
        stages: tuple[RecoveryStage, ...] | None = None,
        max_attempts: int | None = None,
    ):
        self.perform = perform
        self.stages = stages or self.DEFAULT_STAGES
        self.max_attempts = max_attempts if max_attempts is not None else len(self.stages)
        if self.max_attempts < 0:
            raise ValueError("max recovery attempts cannot be negative")
        if not self.stages and self.max_attempts:
            raise ValueError("recovery stages are required when attempts are allowed")
        self.attempts = 0

    def reset(self) -> None:
        self.attempts = 0

    def attempt(self) -> tuple[RecoveryOutcome, RecoveryStage | None]:
        if self.attempts >= self.max_attempts:
            return RecoveryOutcome.EXHAUSTED, None
        stage = self.stages[min(self.attempts, len(self.stages) - 1)]
        self.attempts += 1
        self.perform(stage)
        return RecoveryOutcome.ATTEMPTED, stage
