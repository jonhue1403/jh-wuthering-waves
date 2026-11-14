"""Path-free, read-only target selection for the Farming Assistant.

This catalog is for discovery and UI previews, NOT for live authorization.
A runtime-specific verifier must approve every candidate route before READY
can be returned. Catalog entries never substitute for current game evidence.
"""

from dataclasses import dataclass
from enum import Enum
import unicodedata
from urllib.parse import urlsplit
from typing import Callable


class TargetKind(str, Enum):
    MATERIAL = "material"
    MOB = "mob"


class FarmingReadiness(str, Enum):
    SOURCE_UNRESOLVED = "SOURCE_UNRESOLVED"
    SOURCE_DOCUMENTED = "SOURCE_DOCUMENTED"
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
class DocumentedMobDrop:
    """An external source claim for discovery, never execution authorization.

    A wiki/article link may be outdated or limited by the game's world level.
    Do not promote this record to an observed drop or a qualified route.
    """

    material_id: str
    mob_id: str
    source_url: str

    def __post_init__(self):
        if not self.material_id.strip() or not self.mob_id.strip():
            raise ValueError("Documented source requires exact material and mob ids")
        parsed = urlsplit(self.source_url)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or any(char.isspace() for char in self.source_url)):
            raise ValueError("Source citation must be an HTTPS page URL")


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
    documented_mob_ids: tuple[str, ...] = ()


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
        documented_drops: tuple[DocumentedMobDrop, ...] = (),
    ):
        self._targets: dict[tuple[TargetKind, str], FarmingTarget] = {}
        for item in targets:
            key = (item.kind, item.target_id)
            if key in self._targets:
                raise ValueError("Duplicate farming target identifier")
            self._targets[key] = item

        self._drops = tuple(drops)
        self._routes = tuple(routes)
        self._documented_drops = tuple(documented_drops)
        documented_keys: set[tuple[str, str]] = set()
        for entry in self._documented_drops:
            if ((TargetKind.MATERIAL, entry.material_id) not in self._targets
                    or (TargetKind.MOB, entry.mob_id) not in self._targets):
                raise ValueError("Documented source references an unknown target")
            key = (entry.material_id, entry.mob_id)
            if key in documented_keys:
                raise ValueError("Duplicate documented source")
            documented_keys.add(key)
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

    def documented_sources(self, material_id: str) -> tuple[DocumentedMobDrop, ...]:
        if (TargetKind.MATERIAL, material_id) not in self._targets:
            raise ValueError("Unknown material")
        return tuple(sorted(
            (entry for entry in self._documented_drops
             if entry.material_id == material_id),
            key=lambda entry: entry.mob_id,
        ))

    def resolve(
        self,
        kind: TargetKind,
        target_id: str,
        *,
        route_is_qualified: Callable[[CandidateRoute], bool] | None = None,
        source_is_qualified: Callable[[ObservedMobDrop], bool] | None = None,
    ) -> FarmingResolution:
        if not isinstance(kind, TargetKind) or (kind, target_id) not in self._targets:
            raise ValueError("Unknown farming target")
        target = self._targets[(kind, target_id)]
        documented = ()
        if kind == TargetKind.MATERIAL:
            documented = tuple(sorted(
                entry.mob_id for entry in self._documented_drops
                if entry.material_id == target_id
            ))
            # A nonempty evidence label is not evidence validation. A separate
            # caller MUST check the actual observed-drop evidence and its hashes.
            candidates = tuple(sorted(
                drop.mob_id for drop in self._drops
                if drop.material_id == target_id
                and source_is_qualified is not None
                and source_is_qualified(drop) is True
            ))
            if not candidates:
                return FarmingResolution(
                    target,
                    (FarmingReadiness.SOURCE_DOCUMENTED if documented
                     else FarmingReadiness.SOURCE_UNRESOLVED),
                    (), (),
                    ("Known possible enemy sources; verify actual drops and "
                     "calibrate a current-runtime route before farming."
                     if documented else
                     "No verified material-to-mob source is configured."),
                    documented,
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
                "Observed material sources and routes passed current-runtime verification.",
                documented,
            )
        return FarmingResolution(
            target, FarmingReadiness.ROUTE_UNQUALIFIED, candidates, (),
            "Material source verified; no route passed current-runtime qualification."
            if kind == TargetKind.MATERIAL else
            "No route has passed current-runtime and evidence qualification.",
            documented,
        )


# Explicit names and stable UI slugs transcribed from the operator's
# 2026-11-14 in-game material screenshot, in screenshot row order.
# Names are discovery records, NOT evidence of acquisition method, drop tables,
# numeric game IDs, qualified routes or current-game inventory receipts.
SCREENSHOT_MATERIALS: tuple[tuple[str, str], ...] = (
    ("premium-tuner", "Premium Tuner"),
    ("premium-sealed-tube", "Premium Sealed Tube"),
    ("premium-resonance-potion", "Premium Resonance Potion"),
    ("heterized-metallic-drip", "Heterized Metallic Drip"),
    ("mysterious-code", "Mysterious Code"),
    ("ff-whisperin-core", "FF Whisperin Core"),
    ("ff-howler-core", "FF Howler Core"),
    ("tailored-ring", "Tailored Ring"),
    ("mask-of-insanity", "Mask of Insanity"),
    ("flawless-phlogiston", "Flawless Phlogiston"),
    ("presto-helix", "Presto Helix"),
    ("waveworn-residue-239", "Waveworn Residue 239"),
    ("cadence-blossom", "Cadence Blossom"),
    ("premium-energy-core", "Premium Energy Core"),
    ("ff-tidal-residuum", "FF Tidal Residuum"),
    ("ff-polygon-core", "FF Polygon Core"),
    ("echo-modifier", "Echo Modifier"),
    ("ff-exoswarm-core", "FF Exoswarm Core"),
    ("reverb-combustor", "Reverb Combustor"),
    ("ff-mech-core", "FF Mech Core"),
    ("intact-exoswarm-pendant", "Intact Exoswarm Pendant"),
    ("layered-wing-polarizer", "Layered Wing Polarizer"),
    ("melodic-string", "Melodic String"),
    ("ff-carved-crystal", "FF Carved Crystal"),
    ("ff-waveworn-shard", "FF Waveworn Shard"),
    ("transducer", "Transducer"),
    ("ff-autopuppet-kernel", "FF Autopuppet Kernel"),
)


def starting_catalog() -> FarmingCatalog:
    """The 27 screenshot materials plus five possible FF Mech Core mobs.

    Screenshot catalog entries are selectable and searchable only. They must
    not imply that every item can be obtained from mobs or that farming is
    possible. UI slugs are not verified game IDs.
    """
    material_id = "ff-mech-core"
    names = (
        ("geospider-s4", "Geospider S4"),
        ("sabercat-reaver", "Sabercat Reaver"),
        ("spacetrek-explorer", "Spacetrek Explorer"),
        ("twin-nova-collapsar-blade", "Twin Nova: Collapsar Blade"),
        ("twin-nova-nebulous-cannon", "Twin Nova: Nebulous Cannon"),
    )
    source_url = "https://wutheringwaves.fandom.com/wiki/FF_Mech_Core"
    material_targets = tuple(
        FarmingTarget(
            TargetKind.MATERIAL, slug, name,
            ("5-star weapon/skill material; Lahai-Roi. Possible enemy sources "
             "documented; actual drops and routes not qualified.")
            if slug == material_id else
            "Listed material. Acquisition source not verified; farming unavailable.",
        )
        for slug, name in SCREENSHOT_MATERIALS
    )
    return FarmingCatalog(
        targets=(
            *material_targets,
            *(FarmingTarget(TargetKind.MOB, mob_id, name) for mob_id, name in names),
        ),
        documented_drops=tuple(
            DocumentedMobDrop(material_id, mob_id, source_url)
            for mob_id, _ in names
        ),
    )
