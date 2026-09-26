import unittest
from unittest.mock import patch

from src.overworld.input_access import require_game_input_access


class TestHuntInputAccess(unittest.TestCase):
    def test_windows_privilege_combinations(self):
        with patch("src.overworld.input_access.sys.platform", "win32"), \
                patch("win32process.GetWindowThreadProcessId", return_value=(1, 123)), \
                patch("src.overworld.input_access._process_privileges") as query:
            for game, task, ui_access, blocked in (
                (True, False, False, True),
                (True, True, False, False),
                (False, False, False, False),
                (False, True, False, False),
                (True, False, True, False),
            ):
                with self.subTest(game=game, task=task, ui_access=ui_access):
                    query.side_effect = [(game, False), (task, ui_access)]
                    if blocked:
                        with self.assertRaisesRegex(RuntimeError, "administrator"):
                            require_game_input_access(10)
                    else:
                        require_game_input_access(10)

    def test_query_failure_and_missing_window_stop_movement(self):
        with patch("src.overworld.input_access.sys.platform", "win32"), \
                patch("win32process.GetWindowThreadProcessId", side_effect=OSError("denied")):
            for hwnd in (None, 10):
                with self.subTest(hwnd=hwnd), self.assertRaisesRegex(RuntimeError, "Cannot verify"):
                    require_game_input_access(hwnd)


if __name__ == "__main__":
    unittest.main()
