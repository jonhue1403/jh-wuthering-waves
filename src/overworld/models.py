"""Pure data models for offline Overworld Mob Hunt planning."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import hypot


class TravelMode(str, Enum):
    WALK = "WALK"
    TELEPORT = "TELEPORT"


class CampStatus(str, Enum):
    ACTIVE = "active"
    CLEARED = "cleared"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class MapCoordinate:
    x: float
    y: float

    def distance_to(self, other: "MapCoordinate") -> float:
        return hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True, slots=True)
class HuntPosition:
    """A player/camp position with the map layer it belongs to."""

    state_id: int
    floor_id: str
    coordinate: MapCoordinate


@dataclass(frozen=True, slots=True)
class MobSpawn:
    spawn_id: str
    mob_id: str
    mob_name: str
    state_id: int
    floor_id: str
    coordinate: MapCoordinate
    description: str = ""

    @property
    def position(self) -> HuntPosition:
        return HuntPosition(self.state_id, self.floor_id, self.coordinate)


@dataclass(frozen=True, slots=True)
class CampOverride:
    """Stable, hand-maintained corrections for a generated camp.

    Overrides deliberately only alter planning metadata. They do not add or
    remove raw map spawns, which keeps source data and manual corrections
    auditable and lets later route-execution code consume the same camp model.
    """

    camp_id: str
    anchor: MapCoordinate | None = None
    display_name: str | None = None
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class Camp:
    camp_id: str
    state_id: int
    floor_id: str
    spawns: tuple[MobSpawn, ...]
    anchor: MapCoordinate
    display_name: str | None = None
    disabled: bool = False

    @property
    def target_count(self) -> int:
        return len(self.spawns)

    @property
    def position(self) -> HuntPosition:
        return HuntPosition(self.state_id, self.floor_id, self.anchor)

    def with_override(self, override: CampOverride) -> "Camp":
        return replace(
            self,
            anchor=override.anchor or self.anchor,
            display_name=override.display_name or self.display_name,
            disabled=override.disabled,
        )


@dataclass(frozen=True, slots=True)
class TravelEstimate:
    mode: TravelMode
    estimated_seconds: float
    distance: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class RouteStep:
    sequence: int
    camp: Camp
    estimate: TravelEstimate

    @property
    def mode(self) -> TravelMode:
        return self.estimate.mode

    @property
    def estimated_seconds(self) -> float:
        return self.estimate.estimated_seconds


@dataclass(frozen=True, slots=True)
class RoutePlan:
    target_mob: str
    raw_spawn_count: int
    camps: tuple[Camp, ...]
    steps: tuple[RouteStep, ...]

    @property
    def generated_camp_count(self) -> int:
        return len(self.camps)


@dataclass
class HuntSession:
    """Mutable session-only state; no game or UI objects are involved."""

    current_position: HuntPosition | None = None
    cleared_camps: set[str] = field(default_factory=set)
    failed_camps: set[str] = field(default_factory=set)
    blocked_camps: set[str] = field(default_factory=set)

    def status_for(self, camp_id: str) -> CampStatus:
        if camp_id in self.cleared_camps:
            return CampStatus.CLEARED
        if camp_id in self.failed_camps:
            return CampStatus.FAILED
        if camp_id in self.blocked_camps:
            return CampStatus.BLOCKED
        return CampStatus.ACTIVE

    def is_available(self, camp: Camp) -> bool:
        return not camp.disabled and self.status_for(camp.camp_id) is CampStatus.ACTIVE

    def mark(self, camp_id: str, status: CampStatus) -> None:
        self.cleared_camps.discard(camp_id)
        self.failed_camps.discard(camp_id)
        self.blocked_camps.discard(camp_id)
        if status is CampStatus.CLEARED:
            self.cleared_camps.add(camp_id)
        elif status is CampStatus.FAILED:
            self.failed_camps.add(camp_id)
        elif status is CampStatus.BLOCKED:
            self.blocked_camps.add(camp_id)

    def mark_cleared(self, camp_id: str) -> None:
        self.mark(camp_id, CampStatus.CLEARED)

    def mark_failed(self, camp_id: str) -> None:
        self.mark(camp_id, CampStatus.FAILED)

    def mark_blocked(self, camp_id: str) -> None:
        self.mark(camp_id, CampStatus.BLOCKED)

    def set_current_position(self, position: HuntPosition) -> None:
        self.current_position = position
