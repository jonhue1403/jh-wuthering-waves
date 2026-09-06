import cv2
import numpy as np
from pathlib import Path
from ok import BaseTask, TaskDisabledException

from src.overworld.controller import HuntAbort, HuntCancelled, HuntController, HuntOptions, HuntState
from src.overworld.diagnostics import HuntDiagnostics, stationary_localization
from src.overworld.map_data import KuroMapDataProvider
from src.overworld.navigation import WorldRouteNavigator, WWTaskNavigationBackend
from src.overworld.navigation.player_locator import PlayerLocator, SurfaceProfile
from src.overworld.navigation.image_matcher import HybridMapMatcher, MatcherCalibration
from src.overworld.planner import DryRunRoutePlanner, TravelCostModel, cluster_spawns
from src.task.BaseCombatTask import BaseCombatTask, CharDeadException
from src.task.FarmMapTask import create_circle_mask_with_hole
from src.task.WWOneTimeTask import WWOneTimeTask


class HuntMobTask(WWOneTimeTask, BaseCombatTask):
    owns_switch_healer_config = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Overworld Mob Hunt (Surface Test)"
        self.description = "Walk through one verified surface area. Requires a calibrated Hunt Profile."
        self.default_config.update({
            "Target Mob": "",
            "Hunt Profile": "",
            "Safe Test Mode": True,
            "Localization Only": True,
            "Max Camps": 1,
            "Max Camp Retries": 2,
            "Use Teleport": False,
            "Use Motorcycle": False,
            "Surface Only": True,
            "Use Liberation": True,
            "Switch to Healer before and after Combat": True,
        })
        self.controller = None
        self.locator = None
        self.navigator = None
        self.hunt_run = None
        self._hunt_cancelled = False
        self.localization_report = None
        self._hunt_matcher = None
        self._diagnostic = HuntDiagnostics(self.log_info)

    def validate_config(self, key, value):
        if key == "Max Camps" and value != 1:
            return "Controlled validation supports exactly one camp."
        if key == "Max Camp Retries" and not 0 <= value <= 3:
            return "Use 0–3 retries."
        if ((key in ("Use Teleport", "Use Motorcycle") and value)
                or (key in ("Surface Only", "Safe Test Mode") and not value)):
            return "Only safe surface walking is supported."

    def run(self):
        # Validate all inputs before any game input. Safe mode remains mandatory
        # throughout controlled one-camp validation.
        for key in self.default_config:
            message = self.validate_config(key, self.config.get(key))
            if message:
                raise ValueError(message)
        if not self.config.get("Hunt Profile").strip():
            raise ValueError("Select a calibrated Hunt Profile before starting")
        profile = SurfaceProfile.load(self.config.get("Hunt Profile"))
        if profile.matcher_calibration_path and not self.config.get("Localization Only", True):
            raise ValueError("Calibrated hybrid matching is restricted to Localization Only (Test A).")
        if self.config.get("Target Mob").strip() != profile.target_mob:
            raise ValueError("Target Mob must match the verified Hunt Profile")
        image = cv2.imdecode(np.fromfile(profile.image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Hunt Profile map image could not be decoded")
        self._hunt_matcher = None
        if profile.matcher_calibration_path:
            calibration = MatcherCalibration.load(profile.matcher_calibration_path)
            if (calibration.state_id, calibration.floor_id) != profile.layer:
                raise ValueError("Matcher calibration belongs to a different map layer")
            self._hunt_matcher = HybridMapMatcher(image, calibration)
        spawns = KuroMapDataProvider(profile.database_path).query_target_mob_locations(
            profile.target_mob, state_id=profile.state_id, floor_id=profile.floor_id)
        spawns = tuple(s for s in spawns if s.spawn_id in profile.spawn_ids)
        if {s.spawn_id for s in spawns} != profile.spawn_ids:
            raise ValueError("Verified spawn ids do not match the selected mob and map layer")
        self._hunt_image = image
        self._hunt_profile = profile
        self._hunt_cancelled = False
        self._diagnostic = HuntDiagnostics(self.log_info)
        self.locator = PlayerLocator(profile, match_player=self._match_player,
                                     facing=self._facing, image_size=(image.shape[1], image.shape[0]),
                                     diagnostic=self._diagnostic)
        if any(not self.locator.contains(s.coordinate) for s in spawns):
            raise ValueError("Selected spawns are outside the calibrated map image")
        camps = cluster_spawns(spawns, radius=profile.units_per_pixel * 20)
        if len(camps) != 1:
            raise ValueError("Controlled validation requires exactly one verified camp")
        self._diagnostic("validation_profile", profile=str(Path(self.config.get("Hunt Profile")).resolve()),
                         reference=str(profile.image_path), database=str(profile.database_path),
                         reference_size=(image.shape[1], image.shape[0]), frame_size=profile.frame_size,
                         origin=(profile.origin.x, profile.origin.y), units_per_pixel=profile.units_per_pixel,
                         state_id=profile.state_id, floor_id=profile.floor_id,
                         target=profile.target_mob, spawn_ids=sorted(profile.spawn_ids),
                         camp_id=camps[0].camp_id,
                         camp_xy=(camps[0].anchor.x, camps[0].anchor.y),
                         arrival_radius=profile.units_per_pixel * 8,
                         clear_check_radius=profile.units_per_pixel * 16)
        if self.config.get("Localization Only", True):
            # Test A must not enter task startup, camera targeting, navigation,
            # combat, or input cleanup: none of those inputs are owned here.
            self.controller = None
            self.hunt_run = None
            return self._run_localization_test()
        backend = WWTaskNavigationBackend(self, self.locator.observe)
        self.navigator = WorldRouteNavigator(
            backend, position_threshold=profile.units_per_pixel * 4,
            distance_threshold=profile.units_per_pixel * 4,
            max_recovery_attempts=4,  # No utility/grapple in a surface walk-only test.
            cancellation_exceptions=(TaskDisabledException,),
            diagnostic=self._diagnostic,
        )
        options = HuntOptions(max_camps=self.config.get("Max Camps"),
                              max_retries=self.config.get("Max Camp Retries"),
                              arrival_radius=profile.units_per_pixel * 8)
        planner = DryRunRoutePlanner(
            cluster_radius=profile.units_per_pixel * 20,
            travel_cost=TravelCostModel(walking_speed_units_per_second=profile.units_per_pixel * 10,
                                       local_sweep_radius=profile.units_per_pixel * 200),
        )
        self.controller = HuntController(planner, self.navigator, self, options=options)
        self.use_liberation = self.config.get("Use Liberation")
        try:
            WWOneTimeTask.run(self)
            self.wait_in_team_and_world(time_out=10)
            self.hunt_run = self.controller.run(profile.target_mob, spawns, layer=profile.layer)
            self.log_info(f"Hunt finished: {self.hunt_run.reason}")
        except TaskDisabledException:
            self._hunt_cancelled = True
            self.controller.run_state.state = HuntState.CANCELLED
            self.controller.run_state.reason = "Task cancelled"
        finally:
            self.hunt_run = self.controller.run_state
            combat_released = False
            try:
                self._release_combat_inputs()
                combat_released = True
            finally:
                navigation_released = self.navigator.stop() is not False
                if not navigation_released or not combat_released:
                    self.hunt_run.state = HuntState.FAILED
                    self.hunt_run.reason = "Input cleanup failed"
                    self.log_error("Hunt movement input cleanup failed", notify=True)
                self._diagnostic("task_exit", state=self.hunt_run.state.value, reason=self.hunt_run.reason,
                                 cleanup_success=navigation_released and combat_released)

    def _run_localization_test(self):
        self.localization_report = None
        confidences = []

        def check_cancel():
            if self.cancelled():
                raise HuntCancelled()

        def sample():
            position = self.locate()
            confidences.append(self.locator.last_confidence)
            return position

        try:
            # BaseTask.sleep calls the executor wait directly, avoiding
            # BaseWWTask's monthly-card interaction and HuntMobTask.wait's click.
            self.localization_report = stationary_localization(
                sample, lambda seconds: BaseTask.sleep(self, seconds), check_cancel,
                units_per_pixel=self._hunt_profile.units_per_pixel,
                tolerance_pixels=self._hunt_profile.localization_tolerance_pixels,
            )
            self.localization_report["confidence_samples"] = confidences
            self._diagnostic("stationary_localization", **self.localization_report)
            result = self.localization_report["within_tolerance"]
            reason = ("stationary tolerance passed; absolute accuracy requires landmark review" if result is True
                      else "unstable localization; do not begin movement testing" if result is False
                      else "measurements only; no acceptance tolerance supplied")
            self._diagnostic("task_exit", state="LOCALIZATION_ONLY", reason=reason)
            return self.localization_report
        except (TaskDisabledException, HuntCancelled):
            self._diagnostic("task_exit", state="CANCELLED", reason="localization sampling cancelled")
        except Exception as error:
            self._diagnostic("task_exit", state="FAILED", reason=str(error))
            raise

    def _match_player(self):
        self._check_hunt_cancel()
        self.next_frame()
        frame = self.frame
        if (frame.shape[1], frame.shape[0]) != self._hunt_profile.frame_size:
            return None
        if not self.in_team_and_world():
            return None
        minimap = self.get_box_by_name("box_minimap").crop_frame(frame)
        if self._hunt_matcher is not None:
            # Offline-calibrated, reference-bound Test A opt-in only. No inputs.
            return self._hunt_matcher.match(minimap, create_circle_mask_with_hole(minimap))
        match = self.find_one(frame=self._hunt_image, template=minimap,
                              threshold=self._hunt_profile.match_threshold,
                              mask_function=create_circle_mask_with_hole)
        if match is None:
            return None
        return (*match.center(), match.confidence)

    def _facing(self):
        angle, match = self.rotate_arrow_and_find(cancel_check=self._check_hunt_cancel)
        return angle if match is not None and match.confidence >= 0.6 else None

    def locate(self):
        return self.locator.locate()

    def cancelled(self):
        return (self._hunt_cancelled or not self.enabled or self.paused
                or self.executor.paused or self.executor.exit_event.is_set())

    def _check_hunt_cancel(self):
        if self.cancelled():
            raise TaskDisabledException()

    def wait(self, seconds):
        try:
            self.middle_click(interval=0.5)
            self.sleep(seconds)
        except TaskDisabledException as error:
            raise HuntCancelled() from error

    def _release_combat_inputs(self):
        errors = []
        keys = {"1", "2", "3"}
        for name, default in (("Resonance Key", "e"), ("Liberation Key", "r"),
                              ("Echo Key", "q"), ("Dodge Key", "lshift"),
                              ("Jump Key", "space"), ("Tool Key", "t"), ("Wheel Key", "tab")):
            keys.add(self.key_config.get(name, default))
        for key in keys:
            try:
                self.send_key_up(key)
            except Exception as error:
                errors.append(error)
        try:
            self.mouse_up(key="left")
        except Exception as error:
            errors.append(error)
        if errors:
            raise HuntAbort("Combat input release failed") from errors[0]

    def enemy_present(self):
        return bool(self.has_health_bar() or self.has_target())

    def combat_once(self, wait_combat_time=1, raise_if_not_found=False, target=False):
        self._diagnostic("combat_start")
        outcome = "returned"
        try:
            return super().combat_once(wait_combat_time=wait_combat_time,
                                       raise_if_not_found=raise_if_not_found, target=target)
        except TaskDisabledException as error:
            outcome = "cancelled"
            raise HuntCancelled() from error
        except CharDeadException as error:
            outcome = "character_dead"
            raise HuntAbort("Character died; surface test stopped for manual recovery") from error
        except Exception:
            outcome = "exception"
            raise
        finally:
            try:
                self._release_combat_inputs()
                self._diagnostic("combat_cleanup", success=True)
            except Exception as error:
                self._diagnostic("combat_cleanup", success=False, error=str(error))
                raise
            finally:
                self._diagnostic("combat_end", outcome=outcome)

    def sleep_check(self):
        # BaseCombatTask's check can raise on combat ending. Only combat owns
        # this hook while fighting; navigation handles its own interruptions.
        if self.controller:
            self._check_hunt_cancel()
            if self.controller.run_state.state is HuntState.COMBAT:
                super().sleep_check()

    def revive_action(self):
        # BaseCombatTask's default recovery teleports. This task must stop on death.
        return False

    def report(self, state, camp, run):
        self.info_set("Hunt State", state.value)
        self.info_set("Current Camp", camp.camp_id if camp else "")
        self.info_set("Cleared Camps", len(run.session.cleared_camps))
        self.info_set("Failed Camps", len(run.session.failed_camps))
        position = run.session.current_position
        if position is not None:
            self.info_set("Hunt Position", f"{position.coordinate.x:.1f}, {position.coordinate.y:.1f}")
        reason = run.errors.get(camp.camp_id, "") if camp else run.reason
        self._diagnostic("hunt_state", state=state.value, camp_id=camp.camp_id if camp else None,
                         camp_xy=(camp.anchor.x, camp.anchor.y) if camp else None,
                         xy=(position.coordinate.x, position.coordinate.y) if position else None,
                         confidence=self.locator.last_confidence if self.locator else None,
                         camp_status=run.session.status_for(camp.camp_id).value if camp else None,
                         attempts=run.attempts.get(camp.camp_id, 0) if camp else None,
                         cleared=len(run.session.cleared_camps), failed=len(run.session.failed_camps),
                         reason=reason, replan_reason=run.replan_reason)
