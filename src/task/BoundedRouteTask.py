"""Explicitly reviewed 1–3 camp material route; preview/localization by default."""

from dataclasses import replace
from pathlib import Path
from math import isfinite
import re
import time
import unicodedata

import numpy as np

from src.overworld.controller import HuntAbort, HuntController, HuntState
from src.overworld.map_data import KuroMapDataProvider
from src.overworld.material_route import (
    InventoryObservation, MaterialRoute, MaterialRouteRuntime, ReviewedNavigator, ReviewedPlanner,
)
from src.overworld.navigation.player_locator import SurfaceProfile
from src.task.HuntMobTask import HuntMobTask


class BoundedRouteTask(HuntMobTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Material Route (Reviewed Surface)"
        self.description = "Preview a reviewed route, then qualify localization before bounded execution."
        self.default_config.update({"Route Manifest": "", "Preview Only": True,
                                    "User Material Target": 0, "Max Camps": 1})
        self.config_description.update({
            "Route Manifest": "Reviewed route with observed segments and material/inventory evidence. 已审核路线。",
            "User Material Target": "Explicit user target inventory, not an assumed native goal. 用户明确填写的库存目标。",
            "Preview Only": "No capture, movement, combat or spending. 仅预览，无输入。",
        })
        self.route = None
        self.material_runtime = None

    def validate_config(self, key, value):
        if key == "Max Camps":
            if type(value) is not int or not 1 <= value <= 3:
                return "A reviewed surface route supports at most three camps."
            return None
        if key == "User Material Target" and (type(value) is not int or value < 0):
            return "Use an explicitly supplied nonnegative inventory target."
        return super().validate_config(key, value)

    def _profile_path(self):
        if self.route is None:
            self.route = MaterialRoute.load(self.config.get("Route Manifest", ""))
        return str(self.route.profile_path)

    def _qualification_stage(self, walk_only):
        return "WALK" if walk_only else "MATERIAL_ROUTE"

    def _validate_camps(self, profile, spawns, camps):
        self.route.validate_spawns(profile, spawns)
        if len(camps) != self.config.get("Max Camps"):
            raise ValueError("Max Camps must equal the explicitly reviewed route camp count")
        if self.config.get("Use Teleport") or self.config.get("Use Motorcycle"):
            raise ValueError("Route movement is surface walking only")
        for segment in self.route.segments:
            if any(not self.locator.contains(p.coordinate) for p in segment.waypoints):
                raise ValueError("Route waypoint is outside the calibrated reference")

    def run(self):
        self.material_runtime = None
        self._route_last_capture_sequence = None
        self.route = MaterialRoute.load(self.config.get("Route Manifest", ""))
        profile = SurfaceProfile.load(self.route.profile_path)
        spawns = KuroMapDataProvider(profile.database_path).query_target_mob_locations(
            profile.target_mob, state_id=profile.state_id, floor_id=profile.floor_id)
        spawns = tuple(s for s in spawns if s.spawn_id in profile.spawn_ids)
        camps = self.route.validate_spawns(profile, spawns)
        self.info_set("Route Status", "PREVIEW / LIVE_VERIFICATION_PENDING")
        self.info_set("Route Camps", len(camps))
        self.info_set("Material", self.route.material_id)
        self.info_set("Target Provenance", "USER_SUPPLIED")
        if self.config.get("Preview Only", True):
            return {"route_id": self.route.route_id, "camps": len(camps),
                    "material_id": self.route.material_id,
                    "target": self.config.get("User Material Target"),
                    "max_seconds": self.route.max_seconds, "spending": 0,
                    "status": "PREVIEW"}
        if self.config.get("User Material Target", 0) <= 0:
            raise ValueError("Configure an explicit user material target before execution")
        failed = False
        try:
            result = super().run()
            if self.hunt_run and self.hunt_run.state is HuntState.FAILED:
                raise HuntAbort(self.hunt_run.reason)
            return result
        except Exception:
            failed = True
            raise
        finally:
            material = self.material_runtime
            if material and material.observation:
                self.info_set("Observed Inventory", material.observation.quantity)
                self.info_set("Material Deficit", max(0, material.target - material.observation.quantity))
                self.info_set("Verified Received", sum(r["received"] for r in material.receipts))
                status = ("UNCERTAIN" if failed else
                          "CANCELLED" if self.hunt_run and self.hunt_run.state is HuntState.CANCELLED else
                          "GOAL_COMPLETE" if material.goal_reached() else "DEFICIT_REMAINS")
                self.info_set("Material Goal Status", status)

    def _make_controller(self, planner, profile, spawns, options):
        self.material_runtime = MaterialRouteRuntime(
            self, self.route, self.config.get("User Material Target"),
            read_inventory=self._read_material_inventory, pickup=self._pickup_material)
        self.material_runtime.observe_inventory()
        return HuntController(ReviewedPlanner(self.route, profile),
                              ReviewedNavigator(self.route,
                                                self.route.validate_spawns(profile, spawns),
                                                self.navigator, self.material_runtime),
                              self.material_runtime,
                              options=replace(options, max_camps=len(self.route.segments), max_retries=1))

    def _observed_ui_steps(self, steps):
        if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
            raise HuntAbort("Inventory UI needs 1–8 observed, bounded steps")
        for step in steps:
            self._check_hunt_cancel()
            self._fresh_route_frame()
            if not self.find_one(step["screen_feature"]):
                raise HuntAbort("Inventory UI precondition is unknown; paused without retry")
            if set(step) == {"screen_feature", "click_feature"}:
                button = self.find_one(step["click_feature"])
                if not button:
                    raise HuntAbort("Observed inventory control is missing")
                self.click(button)
            elif set(step) == {"screen_feature", "key"} and step["key"] in ("b", "esc", "m"):
                self.send_key(step["key"])
            else:
                raise HuntAbort("Unqualified inventory UI operation")
            # Wait only for the next qualified screen; never reissue a click.
            self.sleep(.2)

    def _fresh_route_frame(self, previous_sequence=None):
        frame = self.next_frame()
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            raise HuntAbort("Inventory capture failed; cached frame cannot establish a receipt")
        interaction = self.executor.interaction
        validator = getattr(interaction, "validate_frame", None)
        if not callable(validator):
            raise HuntAbort("Inventory capture/window validation is unavailable")
        validator()  # validates the actual capture and input hwnd, without input
        capture = interaction.capture
        observed_at = getattr(capture, "_jh_frame_timestamp", None)
        sequence = getattr(capture, "_jh_frame_sequence", None)
        previous_sequence = (previous_sequence if previous_sequence is not None else
                             getattr(self, "_route_last_capture_sequence", None))
        if (type(observed_at) not in (int, float) or not isfinite(observed_at)
                or not 0 <= time.monotonic() - observed_at <= 2
                or type(sequence) not in (int, float) or not isfinite(sequence)
                or sequence == previous_sequence):
            raise HuntAbort("Inventory capture is stale or repeats the previous frame")
        self._route_last_capture_sequence = sequence
        return frame, observed_at, sequence

    @staticmethod
    def _quantity(text):
        text = unicodedata.normalize("NFKC", text).strip()
        if not re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", text, flags=re.ASCII):
            raise HuntAbort("Inventory quantity is unreadable/ambiguous")
        return int(text.replace(",", ""))

    def _read_material_inventory(self, material_id):
        reader = self.route.inventory_reader
        self._observed_ui_steps(reader.get("open_steps"))
        previous = None
        previous_sequence = None
        observation = None
        try:
            for _ in range(3):
                self._check_hunt_cancel()
                frame, captured_at, sequence = self._fresh_route_frame(previous_sequence)
                previous_sequence = sequence
                if not self.find_one(reader["screen_feature"]):
                    raise HuntAbort("Item-detail screen is not observed")
                labels = self.ocr(*reader["label_box"])
                if len(labels) != 1 or labels[0].name.strip() != reader["item_text"]:
                    raise HuntAbort("Inventory item identity disagrees with the route material")
                values = self.ocr(*reader["quantity_box"])
                if len(values) != 1:
                    raise HuntAbort("Inventory count has missing/conflicting observations")
                quantity = self._quantity(values[0].name)
                if quantity == previous:
                    observation = InventoryObservation(
                        material_id, quantity, captured_at, str(sequence), "ITEM_DETAIL")
                    return observation
                previous = quantity
                self.sleep(.1)
            raise HuntAbort("Inventory count did not stabilize in three fresh frames")
        finally:
            # Cancellation stays with the shared session guard. Never navigate
            # after cancellation in an attempt to restore the old screen.
            if not self.cancelled():
                self._observed_ui_steps(reader.get("close_steps"))
                self._fresh_route_frame()
                if not self.in_team_and_world():
                    raise HuntAbort("Inventory close did not restore the observed world")

    def _pickup_material(self, camp):
        pickup = self.route.inventory_reader.get("pickup")
        if not isinstance(pickup, dict) or pickup.get("evidence") not in self.route.evidence:
            raise HuntAbort("Known material pickup lacks screenshot evidence")
        self._fresh_route_frame()
        if not self.in_team_and_world():
            raise HuntAbort("Pickup requires an observed world screen")
        # One exact, reviewed interaction; no repeated blind F presses.
        prompt = self.find_f_with_text([pickup["prompt_text"]])
        if prompt:
            self.send_key("f")
            self.sleep(.3)
        # Absent prompt is still reread as inventory, never inferred as a drop.
