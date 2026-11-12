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
        self.assertEqual(1, self.tab.target_list.count())
        self.assertEqual("FF Mech Core", self.tab.target_name.text())
        self.assertEqual(5, self.tab.source_list.count())
        self.assertIn("not calibrated", self.tab.readiness_label.text().lower())
        self.assertIn("not measured", self.tab.inventory_label.text().lower())
        self.assertIn("local receipt", self.tab.calibration_label.text().lower())
        self.assertIn("local route", self.tab.route_calibration_label.text().lower())
        self.assertFalse(self.tab._preview["calibration"]["can_start"])
        self.assertFalse(self.tab._preview["route_calibration"]["can_start"])
        self.assertEqual("PREVIEW_ONLY", self.tab._preview["run_state"])
        self.assertFalse(self.tab.start_button.isEnabled())
        self.assertFalse(self.tab.pause_button.isEnabled())
        self.assertFalse(self.tab.stop_button.isEnabled())

    def test_mob_search_and_optional_inventory_goal(self):
        self.tab.mob_button.click()
        self.assertEqual(5, self.tab.target_list.count())
        self.tab.search.setText("sabercat")
        self.assertEqual(1, self.tab.target_list.count())
        self.assertEqual("Sabercat Reaver", self.tab.target_name.text())
        self.tab.goal.setText("50")
        self.assertEqual(50, self.tab._preview["desired_total"])
        self.assertFalse(self.tab.start_button.isEnabled())

    def test_nonmatch_and_kind_switch_clear_state(self):
        self.tab.search.setText("not-here")
        self.assertEqual(0, self.tab.target_list.count())
        self.assertIsNone(self.tab._preview)
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
        ))
        for forbidden in ("Hunt Profile", "Route Manifest", "Runtime Qualification",
                          "Plan Path", ".json", "C:\\", "Z:\\"):
            self.assertNotIn(forbidden, visible)


if __name__ == "__main__":
    unittest.main()
