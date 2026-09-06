"""Spawn clustering, travel cost, and deterministic dry-run route planning."""

from __future__ import annotations

from hashlib import sha1
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from .models import (
    Camp,
    CampOverride,
    HuntPosition,
    HuntSession,
    MapCoordinate,
    MobSpawn,
    RoutePlan,
    RouteStep,
    TravelEstimate,
    TravelMode,
)


def cluster_spawns(
    spawns: Iterable[MobSpawn],
    *,
    radius: float = 250.0,
    overrides: Iterable[CampOverride] = (),
) -> tuple[Camp, ...]:
    """Group nearby spawns, never crossing state or floor boundaries.

    Connected components are used instead of assigning to a centroid. This
    means a long but contiguous camp remains one camp while every comparison
    still uses the same state/floor layer.
    """
    if radius < 0:
        raise ValueError("cluster radius must be non-negative")

    ordered = sorted(
        (spawn for spawn in spawns if spawn.coordinate is not None),
        key=lambda spawn: (spawn.state_id, spawn.floor_id, spawn.spawn_id),
    )
    groups: dict[tuple[int, str], list[MobSpawn]] = {}
    for spawn in ordered:
        groups.setdefault((spawn.state_id, spawn.floor_id), []).append(spawn)

    camps: list[Camp] = []
    for (state_id, floor_id), layer_spawns in groups.items():
        components = _connected_components(layer_spawns, radius)
        for component in components:
            component = tuple(sorted(component, key=lambda spawn: spawn.spawn_id))
            camp_id = _camp_id(state_id, floor_id, component)
            anchor = MapCoordinate(
                sum(spawn.coordinate.x for spawn in component) / len(component),
                sum(spawn.coordinate.y for spawn in component) / len(component),
            )
            camps.append(Camp(camp_id, state_id, floor_id, component, anchor))

    return apply_camp_overrides(tuple(camps), overrides)


def apply_camp_overrides(
    camps: Iterable[Camp], overrides: Iterable[CampOverride]
) -> tuple[Camp, ...]:
    overrides_by_id = {override.camp_id: override for override in overrides}
    return tuple(
        camp.with_override(overrides_by_id[camp.camp_id])
        if camp.camp_id in overrides_by_id
        else camp
        for camp in camps
    )


@dataclass(frozen=True, slots=True)
class TravelCostModel:
    """Simple tunable cost model for dry runs.

    Coordinates are map/game units. Walking is only valid on the same
    ``state_id`` and ``floor_id``; teleporting is represented by a fixed cost
    because this phase intentionally has no game/UI integration.
    """

    walking_speed_units_per_second: float = 120.0
    teleport_seconds: float = 34.0
    local_sweep_radius: float = 2500.0

    def __post_init__(self) -> None:
        if self.walking_speed_units_per_second <= 0:
            raise ValueError("walking speed must be positive")
        if self.teleport_seconds < 0:
            raise ValueError("teleport time cannot be negative")
        if self.local_sweep_radius < 0:
            raise ValueError("local sweep radius cannot be negative")

    def walking_estimate(self, origin: HuntPosition, destination: Camp) -> TravelEstimate | None:
        if (origin.state_id, origin.floor_id) != (destination.state_id, destination.floor_id):
            return None
        distance = origin.coordinate.distance_to(destination.anchor)
        return TravelEstimate(
            TravelMode.WALK,
            distance / self.walking_speed_units_per_second,
            distance,
            "same state/floor",
        )

    def teleport_estimate(self, destination: Camp) -> TravelEstimate:
        return TravelEstimate(
            TravelMode.TELEPORT,
            self.teleport_seconds,
            None,
            "teleport required or cheaper than walking",
        )

    def choose(self, origin: HuntPosition | None, destination: Camp) -> TravelEstimate:
        teleport = self.teleport_estimate(destination)
        if origin is None:
            return TravelEstimate(
                teleport.mode, teleport.estimated_seconds, teleport.distance, "no known start position"
            )

        walking = self.walking_estimate(origin, destination)
        if walking is None:
            return teleport
        if walking.distance is not None and walking.distance <= self.local_sweep_radius:
            if walking.estimated_seconds <= teleport.estimated_seconds:
                return TravelEstimate(
                    walking.mode, walking.estimated_seconds, walking.distance,
                    "nearby local-sweep camp",
                )
        if walking.estimated_seconds <= teleport.estimated_seconds:
            return walking
        return teleport


class DryRunRoutePlanner:
    """Plan camps only; it never presses keys, clicks maps, or reads game state."""

    def __init__(
        self,
        *,
        cluster_radius: float = 250.0,
        travel_cost: TravelCostModel | None = None,
    ):
        self.cluster_radius = cluster_radius
        self.travel_cost = travel_cost or TravelCostModel()

    def plan(
        self,
        target_mob: str,
        spawns: Iterable[MobSpawn],
        *,
        session: HuntSession | None = None,
        overrides: Iterable[CampOverride] = (),
    ) -> RoutePlan:
        raw_spawns = tuple(spawns)
        camps = cluster_spawns(raw_spawns, radius=self.cluster_radius, overrides=overrides)
        active_session = session or HuntSession()
        remaining = [camp for camp in camps if active_session.is_available(camp)]
        origin = active_session.current_position
        steps: list[RouteStep] = []

        while remaining:
            selected, estimate = self._select_next(origin, remaining)
            steps.append(RouteStep(len(steps) + 1, selected, estimate))
            remaining.remove(selected)
            origin = selected.position

        return RoutePlan(str(target_mob), len(raw_spawns), camps, tuple(steps))

    def _select_next(
        self, origin: HuntPosition | None, candidates: Sequence[Camp]
    ) -> tuple[Camp, TravelEstimate]:
        estimates = [(camp, self.travel_cost.choose(origin, camp)) for camp in candidates]
        nearby_walks = [
            (camp, estimate)
            for camp, estimate in estimates
            if estimate.mode is TravelMode.WALK
            and estimate.distance is not None
            and estimate.distance <= self.travel_cost.local_sweep_radius
        ]
        pool = nearby_walks or estimates
        return min(
            pool,
            key=lambda item: (
                item[1].estimated_seconds,
                -item[0].target_count,
                item[0].camp_id,
            ),
        )


def format_dry_run_report(target_mob: str, plan: RoutePlan) -> str:
    lines = [
        f"Target Mob: {target_mob}",
        f"Raw Spawns: {plan.raw_spawn_count}",
        f"Generated Camps: {plan.generated_camp_count}",
        "",
    ]
    lines.extend(
        f"{step.sequence:02d} {step.camp.display_name or step.camp.camp_id} "
        f"{step.mode.value} estimated {step.estimated_seconds:.1f}s "
        f"target mobs={step.camp.target_count}"
        for step in plan.steps
    )
    return "\n".join(lines)


def _connected_components(spawns: Sequence[MobSpawn], radius: float) -> list[list[MobSpawn]]:
    parent = list(range(len(spawns)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(spawns)):
        for right in range(left + 1, len(spawns)):
            if spawns[left].coordinate.distance_to(spawns[right].coordinate) <= radius:
                union(left, right)

    components: dict[int, list[MobSpawn]] = {}
    for index, spawn in enumerate(spawns):
        components.setdefault(find(index), []).append(spawn)
    return list(components.values())


def _camp_id(state_id: int, floor_id: str, spawns: Sequence[MobSpawn]) -> str:
    floor_slug = re.sub(r"[^a-z0-9]+", "_", floor_id.casefold()).strip("_") or "surface"
    spawn_key = "|".join(spawn.spawn_id for spawn in spawns)
    digest = sha1(spawn_key.encode("utf-8")).hexdigest()[:8]
    return f"camp_{state_id}_{floor_slug}_{digest}"
