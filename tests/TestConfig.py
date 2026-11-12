import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config


class TestCalculatePcExePath(unittest.TestCase):

    def test_documented_daily_cli_task_index_remains_one(self):
        self.assertEqual(['src.task.DailyTask', 'DailyTask'], config.config['onetime_tasks'][0])

    def test_farming_assistant_is_registered_only_as_a_web_custom_tab(self):
        from ok import WebCustomTab
        from src.task.FarmingAssistantTask import FarmingAssistantTask

        entry = ['src.task.FarmingAssistantTask', 'FarmingAssistantTask']
        self.assertEqual([entry], config.config.get('web_tabs'))
        self.assertNotIn(entry, config.config.get('onetime_tasks', []))
        self.assertNotIn(entry, config.config.get('trigger_tasks', []))
        self.assertTrue(issubclass(FarmingAssistantTask, WebCustomTab))
        self.assertEqual('farming-assistant', FarmingAssistantTask.web_tab.id)
        self.assertFalse(FarmingAssistantTask.web_tab.task_controls)
        self.assertTrue(
            (FarmingAssistantTask.web_tab.asset_dir / 'index.js').is_file()
        )

    def test_none_path_uses_most_recently_run_executable(self):
        expected = r"C:\Games\Wuthering Waves.exe"

        with patch.object(config, "_find_most_recently_run_pc_exe", return_value=expected) as find:
            with patch.object(config, "_find_pc_exe_from_registry") as find_registry:
                result = config.calculate_pc_exe_path(None)

        find.assert_called_once_with()
        find_registry.assert_not_called()
        self.assertEqual(expected, result)

    def test_none_path_falls_back_to_registry_lookup(self):
        expected = r"C:\Games\Wuthering Waves.exe"

        with patch.object(config, "_find_most_recently_run_pc_exe", return_value=None):
            with patch.object(config, "_find_pc_exe_from_registry", return_value=expected) as find:
                result = config.calculate_pc_exe_path(None)

        find.assert_called_once_with()
        self.assertEqual(expected, result)

    def test_none_path_returns_none_when_no_installation_is_found(self):
        with patch.object(config, "_find_most_recently_run_pc_exe", return_value=None):
            with patch.object(config, "_find_pc_exe_from_registry", return_value=None):
                result = config.calculate_pc_exe_path(None)

        self.assertIsNone(result)

    def test_running_path_still_derives_game_executable(self):
        running_path = (
            r"C:\Games\Wuthering Waves Game\Client\Binaries"
            r"\Win64\Client-Win64-Shipping.exe"
        )

        result = config.calculate_pc_exe_path(running_path)

        self.assertEqual(r"C:\Games\Wuthering Waves Game\Wuthering Waves.exe", result)

    def test_registered_launcher_path_finds_sibling_game_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            install_root = Path(temp)
            launcher = install_root / "Wuthering Waves bilibili" / "launcher.exe"
            game_exe = install_root / "Wuthering Waves Game" / "Wuthering Waves.exe"
            launcher.parent.mkdir()
            game_exe.parent.mkdir()
            game_exe.touch()

            result = config._find_pc_exe_near_registered_path(str(launcher))

        self.assertEqual(str(game_exe), result)


if __name__ == "__main__":
    unittest.main()
