"""Stop-policy acceptance tests never invoke a game task or controller."""
import unittest

from src.automation.farming_selection import TargetKind
from src.automation.farming_stop_policy import (
    MAX_ATTEMPTS, evaluate_stop_criterion,
)
from src.automation.farming_view import FarmingAssistantView


class TestFarmingStopPolicy(unittest.TestCase):
    def test_material_preview_needs_real_inventory(self):
        result = evaluate_stop_criterion(TargetKind.MATERIAL, 12)
        self.assertEqual("INVENTORY_TOTAL", result["mode"])
        self.assertEqual("FRESH_OBSERVATION_REQUIRED", result["decision"])
        self.assertIsNone(result["observed"])
        self.assertFalse(result["enforced"])
        self.assertFalse(result["can_continue"])
        self.assertFalse(result["can_dispatch"])

    def test_mob_encounters_have_different_units(self):
        result = evaluate_stop_criterion(TargetKind.MOB, 2)
        self.assertEqual("ENCOUNTER_LIMIT", result["mode"])
        self.assertEqual("FRESH_OBSERVATION_REQUIRED", result["decision"])

    def test_goal_met_requests_stop_not_farm(self):
        for kind in (TargetKind.MATERIAL, TargetKind.MOB):
            with self.subTest(kind=kind):
                result = evaluate_stop_criterion(kind, 10, observed=10)
                self.assertEqual("STOP_TARGET_REACHED", result["decision"])
                self.assertFalse(result["can_continue"])
                self.assertFalse(result["can_dispatch"])

    def test_below_goal_is_not_execution_authorization(self):
        result = evaluate_stop_criterion(
            TargetKind.MATERIAL, 50, observed=3, attempts=1
        )
        self.assertEqual("BELOW_GOAL_NO_AUTOMATIC_CONTINUE",
                         result["decision"])
        self.assertFalse(result["can_continue"])
        self.assertFalse(result["enforced"])

    def test_bounded_attempt_limit_has_priority_over_incomplete_goal(self):
        result = evaluate_stop_criterion(
            TargetKind.MOB, 50, observed=2, attempts=3, max_attempts=3
        )
        self.assertEqual("STOP_ATTEMPT_LIMIT", result["decision"])
        self.assertFalse(result["can_dispatch"])

    def test_missing_goal_cannot_enable_unbounded_auto_run(self):
        result = evaluate_stop_criterion(TargetKind.MATERIAL, None)
        self.assertEqual("NO_EXPLICIT_GOAL", result["decision"])
        self.assertFalse(result["can_continue"])

    def test_invalid_goal_and_observation_rejected(self):
        for requested in (0, -2, True, False, 1.5, "5", 10_000_000):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                evaluate_stop_criterion(TargetKind.MATERIAL, requested)
        for observed in (-1, True, False, 1.5, "3", 10_000_000):
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                evaluate_stop_criterion(TargetKind.MOB, 2, observed=observed)

    def test_invalid_attempt_limits_rejected(self):
        for attempts, limit in ((-1, 3), (True, 3), (0, 0),
                                (0, 4), (0, True), (1.5, 2)):
            with self.subTest(attempts=attempts, limit=limit):
                with self.assertRaises(ValueError):
                    evaluate_stop_criterion(
                        TargetKind.MOB, 2,
                        attempts=attempts, max_attempts=limit,
                    )
        self.assertEqual(3, MAX_ATTEMPTS)

    def test_invalid_target_kind_rejected(self):
        for kind in ("material", "mob", None, 0):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evaluate_stop_criterion(kind, 1)

    def test_material_first_view_presents_unverified_stop_result(self):
        view = FarmingAssistantView()
        material = view.preview("material", "ff-mech-core", 15)
        mob = view.preview("mob", "geospider-s4", 2)
        for result, mode in (
            (material, "INVENTORY_TOTAL"), (mob, "ENCOUNTER_LIMIT"),
        ):
            criterion = result["stop_criterion"]
            self.assertEqual(mode, criterion["mode"])
            self.assertEqual("PLANNED_ONLY", criterion["state"])
            self.assertEqual("FRESH_OBSERVATION_REQUIRED",
                             criterion["decision"])
            self.assertFalse(criterion["can_dispatch"])
            self.assertFalse(result["can_start"])


if __name__ == "__main__":
    unittest.main()
