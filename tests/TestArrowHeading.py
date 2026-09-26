from pathlib import Path
import unittest

import cv2
import numpy as np

from src.overworld.navigation.arrow_heading import arrow_heading


class TestArrowHeading(unittest.TestCase):
    def setUp(self):
        self.template = np.zeros((75, 75, 3), np.uint8)
        cv2.fillPoly(self.template, [np.int32([[18, 20], [61, 38], [18, 57], [27, 38]])], (20, 220, 255))

    def test_clockwise_cardinal_and_diagonal_headings_at_multiple_scales(self):
        for scale in (.75, 1, 1.2):
            for angle in (0, 45, 90, 135, 180, 225, 270, 315, 359):
                with self.subTest(scale=scale, angle=angle):
                    matrix = cv2.getRotationMatrix2D((37, 37), -angle, scale)
                    image = cv2.warpAffine(self.template, matrix, (75, 75))
                    result, evidence = arrow_heading(image, self.template)
                    self.assertIsNotNone(result, evidence)
                    self.assertLessEqual(abs((result - angle + 180) % 360 - 180), 4)

    def test_no_arrow_and_symmetric_yellow_icon_reject(self):
        for image in (np.zeros_like(self.template), np.full_like(self.template, 200)):
            self.assertIsNone(arrow_heading(image, self.template)[0])
        circle = np.zeros_like(self.template)
        cv2.circle(circle, (37, 37), 14, (20, 220, 255), -1)
        self.assertIsNone(arrow_heading(circle, self.template)[0])
        white_arrow = self.template.copy()
        white_arrow[np.any(white_arrow > 0, axis=2)] = 255
        self.assertIsNone(arrow_heading(white_arrow, self.template)[0])

    def test_white_highlight_does_not_change_heading(self):
        highlighted = self.template.copy()
        cv2.fillPoly(highlighted, [np.int32([[28, 27], [52, 38], [28, 48], [32, 38]])], (255, 255, 255))
        for angle in (0, 90, 180, 243):
            image = cv2.warpAffine(highlighted, cv2.getRotationMatrix2D((37, 37), -angle, 1), (75, 75))
            result, evidence = arrow_heading(image, self.template)
            self.assertIsNotNone(result, evidence)
            self.assertLessEqual(abs((result - angle + 180) % 360 - 180), 4)

    def test_cancellation_propagates_during_matching(self):
        def cancel():
            raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            arrow_heading(self.template, self.template, cancel)

    def test_saved_west_facing_live_arrow(self):
        capture = Path("assets/overworld/calibration/live-validation-20260926T051550886896Z/last.png")
        if not capture.is_file():
            self.skipTest("Private capture unavailable")
        from ok.feature.FeatureSet import FeatureSet
        features = FeatureSet(False, "assets/coco_annotations.json", 0, 0)
        image = cv2.imread(str(capture))
        crop = features.get_box_by_name(image, "arrow").crop_frame(image)
        template = features.get_feature_by_name(image, "arrow").mat
        angle, evidence = arrow_heading(crop, template)
        self.assertIsNotNone(angle, evidence)
        self.assertLessEqual(abs(angle - 180), 5)


if __name__ == "__main__":
    unittest.main()
