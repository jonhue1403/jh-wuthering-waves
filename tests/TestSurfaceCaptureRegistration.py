import unittest

import numpy as np

from scripts.register_surface_capture import extract_minimaps


class TestSurfaceCaptureRegistration(unittest.TestCase):
    def test_calibration_uses_runtime_split_template_rounding(self):
        frame = np.zeros((1440, 2560, 3), np.uint8)
        frame[38:285, 296] = 123
        minis, bounds = extract_minimaps([frame])
        # The packed historical crop was 248 wide; the active split asset is 249.
        self.assertEqual((48, 38, 249, 247), bounds)
        self.assertEqual((247, 249, 3), minis[0].shape)
        self.assertTrue(np.all(minis[0][:, -1] == 123))

    def test_mixed_capture_geometry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "share minimap geometry"):
            extract_minimaps([np.zeros((1440, 2560, 3), np.uint8),
                              np.zeros((1080, 1920, 3), np.uint8)])


if __name__ == "__main__":
    unittest.main()
