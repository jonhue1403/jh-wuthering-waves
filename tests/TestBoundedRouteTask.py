"""Task decision/input tests with synthetic observations, not screenshot passes."""

from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock

import numpy as np

from src.overworld.controller import HuntAbort
from src.task.BoundedRouteTask import BoundedRouteTask


class TestBoundedRouteTask(unittest.TestCase):
    def fake(self):
        task = SimpleNamespace(
            route=SimpleNamespace(inventory_reader={
                "open_steps": [{"screen_feature": "world", "key": "b"}],
                "close_steps": [{"screen_feature": "detail", "key": "esc"}],
                "screen_feature": "detail", "item_text": "Synthetic Material",
                "label_box": [.1, .1, .3, .2], "quantity_box": [.1, .3, .3, .4],
            }), _observed_ui_steps=Mock(), _check_hunt_cancel=Mock(), next_frame=Mock(),
            find_one=Mock(return_value=True), sleep=Mock(), cancelled=Mock(return_value=False),
            in_team_and_world=Mock(return_value=True), frame=np.zeros((10, 10, 3), dtype=np.uint8),
            _quantity=BoundedRouteTask._quantity)
        capture = SimpleNamespace()
        task.executor = SimpleNamespace(interaction=SimpleNamespace(capture=capture, validate_frame=Mock()))
        sequence = 0

        def next_frame():
            nonlocal sequence
            sequence += 1
            capture._jh_frame_timestamp = time.monotonic()
            capture._jh_frame_sequence = sequence
            return task.frame

        task.next_frame.side_effect = next_frame
        task._fresh_route_frame = lambda previous_sequence=None: BoundedRouteTask._fresh_route_frame(
            task, previous_sequence)
        return task

    def test_strict_quantities_accept_normalized_digits_and_reject_ambiguity(self):
        self.assertEqual(1234, BoundedRouteTask._quantity("１,２３４"))
        for text in ("1.2k", "1/20", "12,34", "owned 12", "-1", "1 2", "1O", "", "01"):
            with self.subTest(text=text):
                with self.assertRaises(HuntAbort):
                    BoundedRouteTask._quantity(text)

    def test_item_detail_requires_two_stable_fresh_observations(self):
        task = self.fake()
        task.ocr = Mock(side_effect=[[SimpleNamespace(name="Synthetic Material")],
                                     [SimpleNamespace(name="12")]] * 2)
        observed = BoundedRouteTask._read_material_inventory(task, "fixture-id")
        self.assertEqual(12, observed.quantity)
        self.assertEqual("fixture-id", observed.material_id)
        self.assertEqual(2, task.next_frame.call_count - 1)  # two reads, final world verification
        self.assertEqual(2, task._observed_ui_steps.call_count)

    def test_unknown_screen_or_wrong_item_stops_without_receipt(self):
        for wrong_item in (False, True):
            with self.subTest(wrong_item=wrong_item):
                task = self.fake()
                task.find_one.return_value = wrong_item
                task.ocr = Mock(return_value=[SimpleNamespace(name="Different Item")])
                with self.assertRaises(HuntAbort):
                    BoundedRouteTask._read_material_inventory(task, "fixture-id")

    def test_unstable_count_is_bounded_and_cancel_does_not_close_menu(self):
        task = self.fake()
        task.ocr = Mock(side_effect=[value for count in (1, 2, 3) for value in
                                     ([SimpleNamespace(name="Synthetic Material")],
                                      [SimpleNamespace(name=str(count))])])
        with self.assertRaisesRegex(HuntAbort, "stabilize"):
            BoundedRouteTask._read_material_inventory(task, "fixture-id")
        self.assertEqual(6, task.ocr.call_count)
        task = self.fake()
        task.cancelled.return_value = True
        task._check_hunt_cancel.side_effect = HuntAbort("cancelled")
        with self.assertRaisesRegex(HuntAbort, "cancelled"):
            BoundedRouteTask._read_material_inventory(task, "fixture-id")
        self.assertEqual(1, task._observed_ui_steps.call_count)

    def test_unobserved_inventory_step_issues_no_key_or_click(self):
        task = self.fake()
        task.find_one.return_value = None
        task.send_key, task.click = Mock(), Mock()
        with self.assertRaisesRegex(HuntAbort, "unknown"):
            BoundedRouteTask._observed_ui_steps(task, [{"screen_feature": "world", "key": "b"}])
        task.send_key.assert_not_called()
        task.click.assert_not_called()

    def test_failed_capture_cannot_relabel_cached_inventory(self):
        task = self.fake()
        task.next_frame.side_effect = None
        task.next_frame.return_value = None
        task.ocr = Mock()
        with self.assertRaisesRegex(HuntAbort, "capture failed"):
            BoundedRouteTask._read_material_inventory(task, "fixture-id")
        task.ocr.assert_not_called()

    def test_repeated_capture_sequence_cannot_establish_stable_inventory(self):
        task = self.fake()
        task.next_frame.side_effect = None
        task.next_frame.return_value = task.frame
        task.executor.interaction.capture._jh_frame_timestamp = time.monotonic()
        task.executor.interaction.capture._jh_frame_sequence = 42
        task.ocr = Mock(side_effect=[[SimpleNamespace(name="Synthetic Material")],
                                     [SimpleNamespace(name="12")]] * 2)
        with self.assertRaisesRegex(HuntAbort, "repeats"):
            BoundedRouteTask._read_material_inventory(task, "fixture-id")
        self.assertEqual(2, task.ocr.call_count)  # no second count read from the cached frame

    def test_wrong_capture_window_cannot_establish_receipt(self):
        task = self.fake()
        task.executor.interaction.validate_frame.side_effect = HuntAbort("Capture/input window differs")
        task.ocr = Mock()
        with self.assertRaisesRegex(HuntAbort, "window differs"):
            BoundedRouteTask._read_material_inventory(task, "fixture-id")
        task.ocr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
