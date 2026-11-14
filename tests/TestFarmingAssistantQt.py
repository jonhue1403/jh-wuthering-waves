"""Offscreen Qt preview smoke tests; no game process or task executor required."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from src.gui.FarmingAssistantTab import FarmingAssistantTab
except ImportError:
    QApplication = None
    FarmingAssistantTab = None


@unittest.skipIf(QApplication is None, "PySide6/Qt frontend not installed")
class TestFarmingAssistantQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.tab = FarmingAssistantTab()

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()

    def test_default_material_preview_is_read_only(self):
        self.assertEqual("Farming Assistant", self.tab.name)
        self.assertEqual(27, self.tab.target_list.count())
        self.assertEqual("FF Mech Core", self.tab.target_name.text())
        self.assertEqual(5, self.tab.source_list.count())
        self.assertIn("not calibrated", self.tab.readiness_label.text().lower())
        self.assertIn("not measured", self.tab.inventory_label.text().lower())
        self.assertIn("local receipt", self.tab.calibration_label.text().lower())
        self.assertIn("local route", self.tab.route_calibration_label.text().lower())
        self.assertIn("cross-check", self.tab.reconciliation_label.text().lower())
        self.assertIn("preflight", self.tab.preflight_label.text().lower())
        self.assertIn("version not observed", self.tab.preflight_label.text().lower())
        self.assertEqual(7, self.tab.guide_list.count())
        self.assertIn("next:", self.tab.guide_list.item(0).text().lower())
        self.assertEqual("GUIDED_READ_ONLY",
                         self.tab._preview["calibration_guide"]["mode"])
        self.assertFalse(self.tab._preview["calibration_guide"]["can_start"])
        self.assertEqual(0, self.tab._preview["reconciliation"]["candidate_match_count"])
        self.assertFalse(self.tab._preview["reconciliation"]["can_start"])
        self.assertFalse(self.tab._preview["calibration"]["can_start"])
        self.assertFalse(self.tab._preview["route_calibration"]["can_start"])
        self.assertEqual("PREVIEW_ONLY", self.tab._preview["run_state"])
        self.assertFalse(self.tab.start_button.isEnabled())
        self.assertFalse(self.tab.pause_button.isEnabled())
        self.assertFalse(self.tab.stop_button.isEnabled())

    def test_new_material_search_and_unqualified_read_only_preview(self):
        self.tab.search.setText("premium tuner")
        self.assertEqual(1, self.tab.target_list.count())
        self.assertEqual("Premium Tuner", self.tab.target_name.text())
        self.assertIn("unresolved", self.tab.readiness_label.text().lower())
        self.assertEqual(0, self.tab.source_list.count())
        self.tab.goal.setText("6")
        self.assertEqual("INVENTORY_TOTAL",
                         self.tab._preview["stop_criterion"]["mode"])
        self.assertEqual(6, self.tab._preview["stop_criterion"]["requested"])
        self.assertEqual("PLANNED_ONLY",
                         self.tab._preview["stop_criterion"]["state"])
        self.assertFalse(self.tab.start_button.isEnabled())
        self.assertFalse(self.tab.pause_button.isEnabled())
        self.assertFalse(self.tab.stop_button.isEnabled())

    def test_material_acquisition_guidance_does_not_unlock_farming(self):
        self.tab.search.setText("mysterious code")
        self.assertEqual("Mysterious Code", self.tab.target_name.text())
        self.assertIn("Casket Delivery", self.tab.acquisition_label.text())
        self.assertEqual("SOURCE_UNRESOLVED", self.tab._preview["readiness"])
        self.assertFalse(self.tab.start_button.isEnabled())

        self.tab.search.setText("premium energy core")
        self.assertIn("Simulation Training", self.tab.acquisition_label.text())
        self.assertEqual("SOURCE_UNRESOLVED", self.tab._preview["readiness"])
        self.assertFalse(self.tab.start_button.isEnabled())

        self.tab.search.setText("ff-mech core")
        self.assertIn("Clamorling", self.tab.acquisition_label.text())
        self.assertEqual(5, self.tab.source_list.count())
        self.assertFalse(self.tab.start_button.isEnabled())

    def test_provider_planning_stays_blocked_for_challenge_and_quest_materials(self):
        self.tab.search.setText("presto helix")
        self.assertIn("forgery challenge", self.tab.strategy_label.text())
        self.assertIn("Waveplates", self.tab.strategy_label.text())
        self.assertFalse(self.tab._preview["acquisition_plan"]["can_dispatch"])
        self.assertFalse(self.tab.start_button.isEnabled())

        self.tab.search.setText("mysterious code")
        self.assertIn("No supported automated", self.tab.strategy_label.text())
        self.assertFalse(self.tab.start_button.isEnabled())

        self.tab.mob_button.click()
        self.assertIn("bounded overworld", self.tab.strategy_label.text())
        self.assertFalse(self.tab.start_button.isEnabled())

    def test_mob_search_and_optional_inventory_goal(self):
        self.tab.mob_button.click()
        self.assertIn("encounters", self.tab.goal_label.text().lower())
        self.assertIn("mob encounters", self.tab.inventory_label.text().lower())
        self.assertEqual(5, self.tab.target_list.count())
        self.tab.search.setText("sabercat")
        self.assertEqual(1, self.tab.target_list.count())
        self.assertEqual("Sabercat Reaver", self.tab.target_name.text())
        self.assertEqual(6, self.tab.guide_list.count())
        self.tab.goal.setText("50")
        self.assertEqual(50, self.tab._preview["desired_total"])
        self.assertEqual("ENCOUNTER_LIMIT", self.tab._preview["stop_criterion"]["mode"])
        self.assertFalse(self.tab._preview["stop_criterion"]["enforced"])
        self.assertFalse(self.tab.start_button.isEnabled())

    def test_nonmatch_and_kind_switch_clear_state(self):
        self.tab.search.setText("not-here")
        self.assertEqual(0, self.tab.target_list.count())
        self.assertIsNone(self.tab._preview)
        self.assertIn("cross-check", self.tab.reconciliation_label.text().lower())
        self.assertIn("no target selected", self.tab.preflight_label.text().lower())
        self.assertEqual(0, self.tab.guide_list.count())
        self.assertFalse(self.tab.reference_button.isEnabled())
        self.tab.search.clear()
        self.tab.source_list.setCurrentRow(0)
        self.assertTrue(self.tab.reference_button.isEnabled())
        self.tab.goal.setText("8")
        self.tab.mob_button.click()
        self.assertEqual("", self.tab.goal.text())
        self.assertEqual(0, self.tab.source_list.count())
        self.assertFalse(self.tab.reference_button.isEnabled())
        self.assertFalse(self.tab.start_button.isEnabled())

    def test_invalid_reference_never_exposes_browser_button(self):
        self.assertFalse(self.tab._is_safe_reference("http://example.org/"))
        self.assertFalse(self.tab._is_safe_reference("https://user:pass@example.org/"))
        self.assertFalse(self.tab._is_safe_reference("https://example.org/a b"))
        self.assertTrue(self.tab._is_safe_reference("https://example.org/wiki/Drop"))

    def test_no_developer_file_path_on_visible_surface(self):
        visible = " ".join((
            self.tab.target_name.text(),
            self.tab.target_description.text(),
            self.tab.reason_label.text(),
            self.tab.readiness_label.text(),
            self.tab.next_step.text(),
            self.tab.reconciliation_label.text(),
            self.tab.preflight_label.text(),
            " ".join(self.tab.guide_list.item(i).text()
                     for i in range(self.tab.guide_list.count())),
        ))
        for forbidden in ("Hunt Profile", "Route Manifest", "Runtime Qualification",
                          "Plan Path", ".json", "C:\\", "Z:\\"):
            self.assertNotIn(forbidden, visible)


if __name__ == "__main__":
    unittest.main()
