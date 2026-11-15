"""All-material offline replay. All quantities, identities and mappings are synthetic."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.automation.farming_selection import SCREENSHOT_MATERIALS, TargetKind
from src.automation.farming_stop_policy import evaluate_stop_criterion
from src.automation.farming_strategy import plan_material_acquisition
from src.automation.goals import MaterialGoal, ResourceGoalQueue, SourceMapping
from src.automation.resource_policy import (
    ActionJournal, ClaimIdentity, ResourceBudget, ResourcePolicyError, UncertainReceipt,
)


RUNTIME = "synthetic-current-runtime"
PROVIDERS = {
    "MOB_DROP": ("overworld", "BoundedRouteTask"),
    "FORGERY_CHALLENGE": ("domain", "ForgeryTask"),
    "SIMULATION_TRAINING": ("domain", "SimulationTask"),
    "TACET_FIELD": ("domain", "TacetTask"),
}
MANUAL_ONLY = {"mysterious-code", "echo-modifier", "transducer"}


class TestFarmingAll27Replay(unittest.TestCase):
    def test_reference_plans_and_inventory_stop_policy(self):
        self.assertEqual(27, len({slug for slug, _ in SCREENSHOT_MATERIALS}))
        for slug, _ in SCREENSHOT_MATERIALS:
            with self.subTest(material=slug):
                plan = plan_material_acquisition(slug)
                self.assertEqual(slug, plan["material_id"])
                self.assertIsNone(plan["selected_provider"])
                self.assertEqual([], plan["qualified_provider_ids"])
                self.assertFalse(plan["can_dispatch"] or plan["can_start"])
                options = plan["possible_methods"]
                self.assertTrue(options)
                self.assertFalse(any(option["can_execute"] for option in options))
                self.assertEqual(slug not in MANUAL_ONLY, bool(plan["possible_automation_adapter_count"]))
                for option in options:
                    if option["method"] == "SYNTHESIS":
                        self.assertEqual("MATERIAL_CONSUMPTION_UNVERIFIED", option["resource_policy"])
                        self.assertFalse(option["automation_candidate_exists"])

                for observed, attempts, expected in (
                    (None, 0, "FRESH_OBSERVATION_REQUIRED"),
                    (4, 0, "BELOW_GOAL_NO_AUTOMATIC_CONTINUE"),
                    (4, 1, "BELOW_GOAL_NO_AUTOMATIC_CONTINUE"),
                    (10, 2, "STOP_TARGET_REACHED"),
                    (4, 3, "STOP_ATTEMPT_LIMIT"),
                ):
                    policy = evaluate_stop_criterion(
                        TargetKind.MATERIAL, 10, observed=observed, attempts=attempts,
                    )
                    self.assertEqual(("INVENTORY_TOTAL", expected),
                                     (policy["mode"], policy["decision"]))
                    self.assertFalse(policy["can_continue"] or policy["can_dispatch"]
                                     or policy["enforced"])

    def test_current_unique_mapping_is_only_a_planning_candidate(self):
        for slug, name in SCREENSHOT_MATERIALS:
            goal = MaterialGoal(name, 4, 10, origin="user_supplied")
            with self.subTest(material=slug, case="no-mapping"):
                self.assertIsNone(ResourceGoalQueue([goal]).next_source(RUNTIME))

            for option in plan_material_acquisition(slug)["possible_methods"]:
                method = option["method"]
                kind, producer = PROVIDERS.get(method, (method.lower(), "BoundedRouteTask"))
                mapping = SourceMapping(name, kind, producer, "synthetic-profile",
                                        "synthetic-evidence", RUNTIME, True)
                for case, mappings, runtime, ready in (
                    ("available", [mapping], RUNTIME, method in PROVIDERS),
                    ("unqualified", [replace(mapping, qualified=False)], RUNTIME, False),
                    ("missing-profile", [replace(mapping, profile="")], RUNTIME, False),
                    ("stale-runtime", [mapping], "synthetic-next-runtime", False),
                    ("other-item", [replace(mapping, material="synthetic-other-item")], RUNTIME, False),
                    ("ambiguous", [mapping, replace(mapping, profile="second-profile")], RUNTIME, False),
                ):
                    with self.subTest(material=slug, method=method, case=case):
                        queue = ResourceGoalQueue([goal], mappings)
                        self.assertEqual("READY" if ready else "UNRESOLVED",
                                         queue.preview(runtime)[0]["state"])
                        self.assertEqual((goal, mapping) if ready else None,
                                         queue.next_source(runtime))

    def test_only_matching_inventory_growth_is_a_receipt(self):
        for slug, name in SCREENSHOT_MATERIALS:
            with self.subTest(material=slug):
                goal = MaterialGoal(name, 4, 10, origin="user_supplied")
                queue = ResourceGoalQueue([goal])
                state = queue.progress[name]
                queue.observe_stage(name, combat=True)
                self.assertTrue(state.combat_succeeded)
                self.assertFalse(state.reward_confirmed or state.reward_received or state.goal_complete)
                queue.observe_stage(name, confirmation=True)
                self.assertTrue(state.reward_confirmed)
                self.assertFalse(state.reward_received or state.goal_complete)
                with self.assertRaises(UncertainReceipt):
                    queue.receive({"synthetic-other-item": 10})
                self.assertEqual(4, goal.owned)
                with self.assertRaises(UncertainReceipt):
                    queue.receive({name: 4})
                self.assertFalse(state.reward_received or state.goal_complete)
                queue.receive({name: 6})
                self.assertTrue(state.reward_received)
                self.assertFalse(state.goal_complete)
                queue.receive({name: 10})
                self.assertTrue(state.goal_complete)
                self.assertEqual("COMPLETE", queue.preview(RUNTIME)[0]["state"])

    def test_cancelled_material_attempt_survives_restart(self):
        for slug, _ in SCREENSHOT_MATERIALS:
            if slug in MANUAL_ONLY:
                continue  # These never have a supported producer to start.
            with self.subTest(material=slug), TemporaryDirectory() as directory:
                identity = ClaimIdentity("synthetic-account", "Asia", "material-goal:" + slug, "cycle")
                path = Path(directory) / "journal.json"
                journal = ActionJournal(path)
                self.assertTrue(journal.begin_activity(identity, "synthetic pre-inventory"))
                journal.uncertain_activity(identity, "synthetic interruption before receipt")
                restarted = ActionJournal(path)
                with self.assertRaises(UncertainReceipt):
                    restarted.begin_activity(replace(identity, cycle="next-cycle"), "synthetic retry")
                self.assertEqual(1, len(restarted.snapshot()["activities"]))

    def test_waveplate_reference_refuses_budget_and_mismatched_receipt(self):
        for slug, name in SCREENSHOT_MATERIALS:
            plan = plan_material_acquisition(slug)
            for option in plan["possible_methods"]:
                if option["method"] not in ("FORGERY_CHALLENGE", "SIMULATION_TRAINING", "TACET_FIELD"):
                    continue
                with self.subTest(material=slug, method=option["method"]), TemporaryDirectory() as directory:
                    self.assertEqual("POTENTIAL_WAVEPLATE_COST", option["resource_policy"])
                    identity = ClaimIdentity("synthetic-account", "Asia", option["method"], "cycle")
                    path = Path(directory) / "journal.json"
                    journal = ActionJournal(path)
                    budget = ResourceBudget(60, 1, 60, 0)
                    with self.assertRaises(ResourcePolicyError):
                        journal.prepare(identity, budget, cost=60, current=59, inventory={name: 4})
                    self.assertEqual([], journal.snapshot()["actions"])
                    action = journal.prepare(identity, budget, cost=60, current=60, inventory={name: 4})
                    restarted = ActionJournal(path)
                    for wrong in (replace(identity, account="other-account"),
                                  replace(identity, cycle="other-cycle")):
                        with self.assertRaises(UncertainReceipt):
                            restarted.reconcile(action, observed_identity=wrong, current=0,
                                                inventory={name: 10}, fresh=True)
                    with self.assertRaises(UncertainReceipt):
                        restarted.prepare(identity, budget, cost=60, current=60, inventory={name: 4})
                    self.assertFalse(restarted.snapshot()["actions"][0]["reward_received"])
                    self.assertTrue(restarted.reconcile(action, observed_identity=identity, current=0,
                                                       inventory={name: 10}, fresh=True))
                    self.assertFalse(restarted.reconcile(action, observed_identity=identity, current=0,
                                                        inventory={name: 10}, fresh=True))
