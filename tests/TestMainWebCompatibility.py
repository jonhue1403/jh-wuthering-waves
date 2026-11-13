import unittest
import warnings
from unittest.mock import patch

import main_web
from config import config


class TestMainWebCompatibility(unittest.TestCase):
    def test_legacy_launcher_warns_and_starts_supported_qt_ui(self):
        with patch.object(main_web, "OK") as ok:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                main_web.main()

        self.assertTrue(any(
            warning.category is FutureWarning
            and "removed the web frontend" in str(warning.message)
            for warning in caught
        ))
        ok.assert_called_once_with(config)
        ok.return_value.start.assert_called_once_with()
        self.assertEqual({"type": "qt"}, config["gui"])


if __name__ == "__main__":
    unittest.main()
