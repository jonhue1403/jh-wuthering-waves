from pathlib import Path
import unittest

from src.overworld.models import HuntPosition, MapCoordinate
from src.overworld.navigation.player_locator import PlayerLocator, SurfaceProfile


class TestHuntPlayerLocator(unittest.TestCase):
    def setUp(self):
        self.profile = SurfaceProfile(Path("map.png"), Path("map.db"), "Target", 8, "",
                                      MapCoordinate(-100, 200), 10, (1920, 1080), frozenset({"1"}))
        self.match = (20, 30, 0.9)
        self.locator = PlayerLocator(self.profile, match_player=lambda: self.match,
                                     facing=lambda: 0, image_size=(100, 100))

    def test_image_to_kuro_position_and_back(self):
        position = self.locator.locate()
        self.assertEqual(MapCoordinate(100, 500), position.coordinate)
        self.assertEqual((20, 30), self.profile.image_coordinate(position.coordinate))

    def test_bearing_matches_clockwise_image_axes(self):
        observation = self.locator.observe(HuntPosition(8, "", MapCoordinate(100, 600)))
        self.assertEqual(90, observation.bearing)
        self.assertEqual(100, observation.distance)

    def test_wrong_layer_target_rejected(self):
        self.assertIsNone(self.locator.observe(HuntPosition(8, "B1", MapCoordinate(100, 600))))

    def test_low_confidence_and_invalid_matches_rejected(self):
        for match in ((20, 30, 0.4), (1000, 30, 0.9), (float("nan"), 30, 0.9), None):
            with self.subTest(match=match):
                self.match = match
                self.assertIsNone(self.locator.locate())

    def test_uncertain_facing_prevents_navigation(self):
        self.locator.facing = lambda: None
        self.assertIsNone(self.locator.observe(HuntPosition(8, "", MapCoordinate(100, 600))))
