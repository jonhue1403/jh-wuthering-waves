"""Path-free, read-only target selection for the Farming Assistant.

This catalog is for discovery and UI previews, NOT for live authorization.
A runtime-specific verifier must approve every candidate route before READY
can be returned. Catalog entries never substitute for current game evidence.
"""

from dataclasses import dataclass
from enum import Enum
import unicodedata
from typing import Callable


class TargetKind(str, Enum):
    MATERIAL = "material"
    MOB = "mob"


class FarmingReadiness(str, Enum):
    SOURCE_UNRESOLVED = "SOURCE_UNRESOLVED"
    ROUTE_UNQUALIFIED = "ROUTE_UNQUALIFIED"
    READY = "READY"


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


@dataclass(frozen=True)
class FarmingTarget:
    kind: TargetKind
    target_id: str
    name: str
    description: str = ""
    aliases: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.kind, TargetKind):
            raise ValueError("Unknown farming target kind")
        if not self.target_id.strip() or not self.name.strip():
            raise ValueError("Farming targets need an id and display name")
        if any(not value.strip() for value in self.aliases):
            raise ValueError("Target aliases cannot be empty")


@dataclass(frozen=True)
class ObservedMobDrop:
    material_id: str
    mob_id: str
    evidence_reference: str

    def __post_init__(self):
        if not all(value.strip() for value in (
            self.material_id, self.mob_id, self.evidence_reference
        )):
            raise ValueError("Drop mapping requires both ids and genuine evidence reference")


@dataclass(frozen=True)
class CandidateRoute:
    mob_id: str
    route_id: str
    evidence_reference: str

    def __post_init__(self):
        if not all(value.strip() for value in (
            self.mob_id, self.route_id, self.evidence_reference
        )):
            raise ValueError("Route candidate requires ids and review evidence reference")


@dataclass(frozen=True)
class FarmingResolution:
    target: FarmingTarget
    readiness: FarmingReadiness
    candidate_mob_ids: tuple[str, ...]
    qualified_route_ids: tuple[str, ...]
    explanation: str


class FarmingCatalog:
    """Discover targets and resolve qualified routes without exposing file paths.

    The route_is_qualified callback MUST perform a full current-runtime
    qualification and evidence-hash check in the eventual execution adapter.
    Without that callback, no route is ever READY.
    """

    def __init__(
        self,
        targets: tuple[FarmingTarget, ...] = (),
        drops: tuple[ObservedMobDrop, ...] = (),
        routes: tuple[CandidateRoute, ...] = (),
    ):
        self._targets: dict[tuple[TargetKind, str], FarmingTarget] = {}
        for item in targets:
            key = (item.kind, item.target_id)
            if key in self._targets:
                raise ValueError("Duplicate farming target identifier")
            self._targets[key] = item

        self._drops = tuple(drops)
        self._routes = tuple(routes)
        drop_keys: set[tuple[str, str]] = set()
        for entry in self._drops:
            if ((TargetKind.MATERIAL, entry.material_id) not in self._targets
                    or (TargetKind.MOB, entry.mob_id) not in self._targets):
                raise ValueError("Drop mapping references an unknown target")
            key = (entry.material_id, entry.mob_id)
            if key in drop_keys:
                raise ValueError("Duplicate material-to-mob mapping")
            drop_keys.add(key)

        route_keys: set[str] = set()
        for entry in self._routes:
            if (TargetKind.MOB, entry.mob_id) not in self._targets:
                raise ValueError("Route candidate references an unknown mob")
            if entry.route_id in route_keys:
                raise ValueError("Duplicate route identifier")
            route_keys.add(entry.route_id)

    def search(self, query: str = "", *, kind: TargetKind | None = None,
               limit: int = 50) -> tuple[FarmingTarget, ...]:
        if kind is not None and not isinstance(kind, TargetKind):
            raise ValueError("Unknown target kind")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Search limit must be 1..100")
        needle = _normalized(query)
        matches = [
            entry for entry in self._targets.values()
            if (kind is None or entry.kind == kind)
            and (not needle or any(
                needle in _normalized(text)
                for text in (entry.name, entry.target_id, *entry.aliases)
            ))
        ]
        matches.sort(key=lambda item: (item.kind.value, _normalized(item.name), item.target_id))
        return tuple(matches[:limit])

    def resolve(
        self,
        kind: TargetKind,
        target_id: str,
        *,
        route_is_qualified: Callable[[CandidateRoute], bool] | None = None,
    ) -> FarmingResolution:
        if not isinstance(kind, TargetKind) or (kind, target_id) not in self._targets:
            raise ValueError("Unknown farming target")
        target = self._targets[(kind, target_id)]
        if kind == TargetKind.MATERIAL:
            candidates = tuple(sorted(
                drop.mob_id for drop in self._drops if drop.material_id == target_id
            ))
            if not candidates:
                return FarmingResolution(
                    target, FarmingReadiness.SOURCE_UNRESOLVED, (), (),
                    "No evidence-backed material-to-mob source is configured.",
                )
        else:
            candidates = (target_id,)

        candidate_set = set(candidates)
        qualified = tuple(sorted(
            route.route_id for route in self._routes
            if route.mob_id in candidate_set
            and route_is_qualified is not None
            and route_is_qualified(route) is True
        ))
        if qualified:
            return FarmingResolution(
                target, FarmingReadiness.READY, candidates, qualified,
                "Eligible routes passed the caller's current-runtime verification.",
            )
        return FarmingResolution(
            target, FarmingReadiness.ROUTE_UNQUALIFIED, candidates, (),
            "No route has passed current-runtime and evidence qualification.",
        )


def starting_catalog() -> FarmingCatalog:
    """Seed the pictured goal only; unknown enemy drops must not be invented."""
    return FarmingCatalog(targets=(
        FarmingTarget(
            TargetKind.MATERIAL, "ff-mech-core", "FF Mech Core",
            "Weapon and Skill Material; source routes not yet qualified.",
        ),
    ))
