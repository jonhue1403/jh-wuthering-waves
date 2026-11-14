"""Small reviewed routes over the existing hunt controller and navigator.

No global routing, arbitrary terrain, invented material mappings, or drop rates.
An empty camp can be clear while its material receipt remains zero/unverified.
"""

from dataclasses import dataclass, replace
import json
from math import isfinite
from pathlib import Path
import time

from .controller import HuntAbort, HuntCancelled, HuntController, HuntOptions, HuntState
from .models import HuntPosition, MapCoordinate
from .navigation import NavigationResult, NavigationStatus
from .planner import DryRunRoutePlanner, TravelCostModel, cluster_spawns
from .qualification import LIVE_PENDING, file_sha256, verify_files


@dataclass(frozen=True)
class CampSegment:
    camp_id: str
    spawn_ids: frozenset[str]
    waypoints: tuple[HuntPosition, ...]


@dataclass(frozen=True)
class MaterialRoute:
    path: Path
    route_id: str
    profile_path: Path
    profile_sha256: str
    material_id: str
    target_mob: str
    layer: tuple[int, str]
    segments: tuple[CampSegment, ...]
    rejoin_radius: float
    max_seconds: float
    inventory_reader: dict
    evidence: dict

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("schema_version") != 1 or data.get("status") != "REVIEWED"
                or data.get("surface_only") is not True):
            raise ValueError(f"{LIVE_PENDING}: route needs reviewed surface segments")
        layer = int(data["state_id"]), str(data["floor_id"])
        segments = tuple(CampSegment(str(s["camp_id"]), frozenset(map(str, s["spawn_ids"])),
                                    tuple(HuntPosition(*layer, MapCoordinate(*xy))
                                          for xy in s["waypoints"]))
                         for s in data["segments"])
        radius, seconds = float(data["rejoin_radius"]), float(data["max_seconds"])
        if (not 1 <= len(segments) <= 3 or len({s.camp_id for s in segments}) != len(segments)
                or not isfinite(radius) or radius <= 0
                or not isfinite(seconds) or not 1 <= seconds <= 1800
                or any(not s.spawn_ids or not 2 <= len(s.waypoints) <= 32 for s in segments)
                or any(not all(isfinite(v) for v in (p.coordinate.x, p.coordinate.y))
                       for s in segments for p in s.waypoints)):
            raise ValueError("Routes require 1–3 distinct camps, bounded time and finite observed waypoints")
        profile_path = (path.parent / data["profile"]).resolve()
        if not profile_path.is_file() or file_sha256(profile_path) != data["profile_sha256"]:
            raise ValueError("Route is bound to another/stale surface profile")
        # The file hash records source evidence, not a self-declared drop table.
        evidence = data.get("evidence_sha256")
        verify_files(path.parent, evidence)
        mapping = data.get("material_source", {})
        if (mapping.get("kind") != "observed_mob_drop" or not mapping.get("material_id")
                or not mapping.get("target_mob") or mapping.get("evidence") not in evidence):
            raise ValueError("Unknown material-to-mob mapping remains unresolved")
        for segment, raw in zip(segments, data["segments"]):
            if raw.get("evidence") not in evidence:
                raise ValueError(f"Unobserved camp segment: {segment.camp_id}")
        reader = data.get("inventory_reader", {})
        if (reader.get("evidence") not in evidence or not reader.get("screen_feature")
                or not reader.get("item_text") or mapping.get("item_text") != reader["item_text"]):
            raise ValueError("Inventory reading requires a reviewed compatible screenshot")
        for key in ("label_box", "quantity_box"):
            box = reader.get(key, [])
            if (not isinstance(box, list) or len(box) != 4
                    or not all(type(v) in (float, int) and isfinite(v) and 0 <= v <= 1 for v in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError("Inventory OCR region must be a reviewed normalized rectangle")
        for key in ("open_steps", "close_steps"):
            steps = reader.get(key)
            if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
                raise ValueError("Inventory UI needs 1–8 observed bounded steps")
            for step in steps:
                if (not isinstance(step, dict) or not step.get("screen_feature")
                        or not ((set(step) == {"screen_feature", "click_feature"} and step["click_feature"])
                                or (set(step) == {"screen_feature", "key"}
                                    and step["key"] in ("b", "esc", "m")))):
                    raise ValueError("Inventory step must use one exact observed control")
        pickup = reader.get("pickup", {})
        if pickup.get("evidence") not in evidence or not pickup.get("prompt_text"):
            raise ValueError("Material pickup requires an observed exact interaction")
        return cls(path, str(data["route_id"]), profile_path, str(data["profile_sha256"]),
                   str(mapping["material_id"]), str(mapping["target_mob"]), layer, segments,
                   radius, seconds, reader, evidence)

    def validate_spawns(self, profile, spawns):
        if (self.layer != profile.layer or self.target_mob != profile.target_mob
                or file_sha256(self.profile_path) != self.profile_sha256):
            raise ValueError("Route profile, target or layer changed")
        camps = cluster_spawns(spawns, radius=profile.units_per_pixel * 20)
        actual = {camp.camp_id: frozenset(s.spawn_id for s in camp.spawns) for camp in camps}
        expected = {s.camp_id: s.spawn_ids for s in self.segments}
        if actual != expected or frozenset(s.spawn_id for s in spawns) != profile.spawn_ids:
            raise ValueError("Route camps do not match all selected, calibrated spawns")
        by_id = {camp.camp_id: camp for camp in camps}
        for index, segment in enumerate(self.segments):
            if segment.waypoints[-1] != by_id[segment.camp_id].position:
                raise ValueError("Reviewed segment must reach the actual camp anchor")
            if index and segment.waypoints[0] != self.segments[index - 1].waypoints[-1]:
                raise ValueError("Connecting camp segment has an unreviewed gap")
        return camps


@dataclass(frozen=True)
class InventoryObservation:
    material_id: str
    quantity: int
    observed_at: float
    frame_id: str
    screen: str

    def validate(self, material_id, *, now, previous=None):
        if (self.material_id != material_id or type(self.quantity) is not int or self.quantity < 0
                or not self.frame_id or self.screen != "ITEM_DETAIL"
                or not isfinite(self.observed_at) or not 0 <= now - self.observed_at <= 5
                or (previous and (self.frame_id == previous.frame_id
                                  or self.observed_at <= previous.observed_at))):
            raise HuntAbort("Fresh, identified item inventory observation required")


class ReviewedPlanner(DryRunRoutePlanner):
    def __init__(self, route, profile):
        self.route = route
        super().__init__(cluster_radius=profile.units_per_pixel * 20,
                         travel_cost=TravelCostModel(profile.units_per_pixel * 10,
                                                     local_sweep_radius=profile.units_per_pixel * 200))

    def plan(self, *args, **kwargs):
        plan = super().plan(*args, **kwargs)
        order = {s.camp_id: i for i, s in enumerate(self.route.segments)}
        if any(step.camp.camp_id not in order for step in plan.steps):
            raise HuntAbort("Planner produced an unreviewed camp")
        steps = tuple(replace(step, sequence=i + 1)
                      for i, step in enumerate(sorted(plan.steps, key=lambda s: order[s.camp.camp_id])))
        return replace(plan, steps=steps)


class ReviewedNavigator:
    """Replace centroid shortcuts with exact reviewed waypoint sequences."""

    def __init__(self, route, camps, navigator, runtime):
        self.route, self.navigator, self.runtime = route, navigator, runtime
        self.camps = {camp.position: camp for camp in camps}

    def stop(self):
        return self.navigator.stop()

    def follow_to(self, target, **kwargs):
        camp = self.camps.get(target)
        if camp is None:
            raise HuntAbort("Navigation requested an unreviewed camp")
        segment = next(s for s in self.route.segments if s.camp_id == camp.camp_id)
        self.stop()
        position = self.runtime.locate()  # fresh after combat/transition; never reuse planner origin
        if position is None or (position.state_id, position.floor_id) != self.route.layer:
            raise HuntAbort("Route lost map/layer localization")
        distances = [position.coordinate.distance_to(p.coordinate) for p in segment.waypoints]
        index = min(range(len(distances)), key=distances.__getitem__)
        if distances[index] > self.route.rejoin_radius:
            raise HuntAbort("Outside reviewed route rejoin area; manual relocalization required")
        result = self.navigator.follow_waypoints(segment.waypoints[index:], **kwargs)
        if result.status is NavigationStatus.ARRIVED:
            return self.navigator.follow_to(target, **kwargs)
        return result

    def follow_waypoints(self, targets, **kwargs):
        # HuntController supplies spawn positions from the profile-bound database.
        permitted = {s.position for camp in self.camps.values() for s in camp.spawns}
        if not targets or any(p not in permitted for p in targets):
            raise HuntAbort("Unreviewed camp approach")
        return self.navigator.follow_waypoints(targets, **kwargs)


class MaterialRouteRuntime:
    """Delegate combat to the inherited engine and inventory to a reviewed observer."""

    def __init__(self, runtime, route, target, *, read_inventory, pickup, clock=time.monotonic):
        if type(target) is not int or target < 1:
            raise ValueError("An explicitly labelled positive user material target is required")
        self.runtime, self.route, self.target = runtime, route, target
        self.read_inventory, self.pickup, self.clock = read_inventory, pickup, clock
        self.started = clock()
        self.observation = None
        self.receipts = []

    def __getattr__(self, name):
        return getattr(self.runtime, name)

    def cancelled(self):
        if self.clock() - self.started >= self.route.max_seconds:
            raise HuntAbort("Material route execution time limit reached")
        return self.runtime.cancelled()

    def observe_inventory(self):
        # The inventory reader may issue reviewed UI controls. A cancellation
        # before or during observation must not permit another UI action or
        # become a confirmed inventory/receipt result.
        if self.cancelled():
            raise HuntCancelled()
        value = self.read_inventory(self.route.material_id)
        if self.cancelled():
            raise HuntCancelled()
        if not isinstance(value, InventoryObservation):
            raise HuntAbort("Inventory observer returned no qualified item detail")
        value.validate(self.route.material_id, now=self.clock(), previous=self.observation)
        if self.observation and value.quantity < self.observation.quantity:
            raise HuntAbort("Inventory decreased/changed ambiguously; stop with uncertainty")
        self.observation = value
        return value

    def goal_reached(self):
        return self.observation is not None and self.observation.quantity >= self.target

    def camp_cleared(self, camp, run):
        before = self.observation
        if before is None:
            raise HuntAbort("Fresh pre-encounter material inventory baseline required")
        # cancelled() is a boolean predicate. Ignoring True previously allowed
        # a pickup and fresh UI navigation after Stop was already requested.
        if self.cancelled():
            raise HuntCancelled()
        self.pickup(camp)  # Issued pickup is deliberately not a receipt.
        if self.cancelled():
            raise HuntCancelled()
        after = self.observe_inventory()
        self.receipts.append({"camp_id": camp.camp_id,
                              "before": before.quantity, "after": after.quantity,
                              "received": after.quantity - before.quantity,
                              "frame_id": after.frame_id})
        # HuntController emits CLEARED once, after camp_cleared returns.
        # Do not emit a duplicate transition before its receipt check finishes.


def run_material_route(route, profile, spawns, navigator, runtime, *, target,
                       read_inventory, pickup, clock=time.monotonic):
    spawns = tuple(spawns)
    camps = route.validate_spawns(profile, spawns)
    wrapped = MaterialRouteRuntime(runtime, route, target, read_inventory=read_inventory,
                                  pickup=pickup, clock=clock)
    wrapped.observe_inventory()
    controller = HuntController(ReviewedPlanner(route, profile),
                                ReviewedNavigator(route, camps, navigator, wrapped), wrapped,
                                options=HuntOptions(max_camps=len(camps), max_retries=1,
                                                    arrival_radius=profile.units_per_pixel * 8),
                                clock=clock)
    return controller.run(route.target_mob, spawns, layer=route.layer), wrapped


@dataclass(frozen=True)
class TransitionObservation:
    state: str
    frame_id: str
    observed_at: float


def known_beacon_transition(*, observe, issue, locate, destination, qualification,
                            profile_path, profile, runtime_version, game_version, source_root,
                            beacon_id,
                            clock=time.monotonic, wait, cancelled, timeout=30,
                            destination_radius=None):
    """One prequalified beacon action, observed loading, fresh destination localization.

    ``observe`` must return a fresh TransitionObservation from a compatible
    screenshot recognizer. An unknown screen never causes a blind retry.
    """
    qualification.assert_compatible(profile_path, profile, runtime_version=runtime_version,
                                    game_version=game_version, stage="BEACON", source_root=source_root)
    beacon = qualification.data.get("known_beacons", {}).get(beacon_id, {})
    expected = [destination.state_id, destination.floor_id,
                destination.coordinate.x, destination.coordinate.y]
    if (beacon.get("destination") != expected or beacon.get("evidence")
            not in qualification.data.get("evidence_sha256", {})):
        raise HuntAbort("Beacon/destination lacks reviewed transition evidence")
    reviewed_radius = beacon.get("destination_radius")
    if (type(reviewed_radius) not in (int, float) or not isfinite(reviewed_radius)
            or reviewed_radius <= 0 or (destination_radius is not None
                                       and destination_radius != reviewed_radius)):
        raise HuntAbort("Beacon destination tolerance requires reviewed calibration")
    destination_radius = reviewed_radius
    last = None

    def screen():
        nonlocal last
        value = observe()
        if (not isinstance(value, TransitionObservation) or not value.frame_id
                or not isfinite(value.observed_at) or not 0 <= clock() - value.observed_at <= 2
                or (last and (value.frame_id == last.frame_id or value.observed_at <= last.observed_at))):
            raise HuntAbort("Beacon transition frame is stale or unqualified")
        last = value
        return value.state

    if (not 1 <= timeout <= 60 or not isfinite(destination_radius) or destination_radius <= 0
            or screen() != "BEACON_READY"):
        raise HuntAbort("Known beacon transition precondition not observed")
    if cancelled():
        raise HuntAbort("Beacon transition cancelled before input")
    issued = clock()
    issue()  # exactly once; timeout/interruptions never issue it again
    saw_loading = False
    while clock() - issued < timeout:
        if cancelled():
            raise HuntAbort("Beacon transition cancelled; destination requires reconciliation")
        state = screen()
        if state == "LOADING":
            saw_loading = True
        elif state == "WORLD" and saw_loading:
            position = locate()
            if (position is None or (position.state_id, position.floor_id)
                    != (destination.state_id, destination.floor_id)
                    or position.coordinate.distance_to(destination.coordinate) > destination_radius):
                raise HuntAbort("Fresh beacon destination localization disagrees")
            return position
        elif state not in ("BEACON_READY", "WORLD"):
            raise HuntAbort("Unknown screen after beacon input; do not retry")
        wait(.1)
    raise HuntAbort("Beacon result uncertain: loading/destination not verified")
