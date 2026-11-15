"""Actual selected-material OCR quantity deltas, no game or input needed."""
from dataclasses import FrozenInstanceError
import unittest

from src.automation.material_receipt import (
    MAX_QUANTITY, MaterialReceiptDelta, verify_selected_inventory_receipt,
)
from src.automation.resource_policy import UncertainReceipt


class TestMaterialReceipt(unittest.TestCase):
    def test_single_selected_material_gain(self):
        result = verify_selected_inventory_receipt(
            {'FF Mech Core': 4}, {'FF Mech Core': 7}, {'FF Mech Core'})
        self.assertEqual((
            MaterialReceiptDelta('FF Mech Core', 4, 7, 3),
        ), result)
        self.assertTrue(result[0].target_gained)
        with self.assertRaises(FrozenInstanceError):
            result[0].received = 10

    def test_multiple_selected_materials_partial_gain(self):
        rows = verify_selected_inventory_receipt(
            {'Needed A': 1, 'Needed B': 5, 'Other': 4},
            {'Needed A': 2, 'Needed B': 5, 'Other': 6},
            {'Needed A', 'Needed B'})
        self.assertEqual(['Needed A', 'Needed B'], [r.material for r in rows])
        self.assertEqual([1, 0], [r.received for r in rows])

    def test_only_unrelated_item_gain_does_not_count(self):
        with self.assertRaisesRegex(UncertainReceipt, 'no actual target inventory increase'):
            verify_selected_inventory_receipt(
                {'FF Mech Core': 4, 'Premium Tuner': 2},
                {'FF Mech Core': 4, 'Premium Tuner': 3},
                {'FF Mech Core'})

    def test_zero_gain_does_not_count(self):
        with self.assertRaises(UncertainReceipt):
            verify_selected_inventory_receipt(
                {'FF Mech Core': 4}, {'FF Mech Core': 4},
                {'FF Mech Core'})

    def test_missing_or_extra_inventory_labels_rejected(self):
        before = {'FF Mech Core': 4}
        for after in ({}, {'Premium Tuner': 5},
                      {'FF Mech Core': 5, 'Other': 1}):
            with self.subTest(after=after), self.assertRaises(UncertainReceipt):
                verify_selected_inventory_receipt(
                    before, after, {'FF Mech Core'})

    def test_regression_on_other_material_is_uncertain(self):
        with self.assertRaises(UncertainReceipt):
            verify_selected_inventory_receipt(
                {'FF Mech Core': 4, 'Premium Tuner': 7},
                {'FF Mech Core': 5, 'Premium Tuner': 6},
                {'FF Mech Core'})

    def test_ambiguous_normalized_material_names_rejected(self):
        with self.assertRaisesRegex(UncertainReceipt, 'Ambiguous duplicate'):
            verify_selected_inventory_receipt(
                {'FF Mech Core': 1, 'ＦＦ  Mech Core': 4},
                {'FF Mech Core': 2, 'ＦＦ  Mech Core': 4},
                {'FF Mech Core'})

    def test_invalid_quantities_and_booleans_rejected(self):
        for wrong in (-1, None, True, False, 4.0, '4', MAX_QUANTITY + 1):
            with self.subTest(wrong=wrong), self.assertRaises(UncertainReceipt):
                verify_selected_inventory_receipt(
                    {'FF Mech Core': 4}, {'FF Mech Core': wrong},
                    {'FF Mech Core'})

    def test_invalid_before_quantities_rejected(self):
        for wrong in (-1, True, False, '4', MAX_QUANTITY + 1):
            with self.subTest(wrong=wrong), self.assertRaises(UncertainReceipt):
                verify_selected_inventory_receipt(
                    {'FF Mech Core': wrong}, {'FF Mech Core': 5},
                    {'FF Mech Core'})

    def test_unrecognized_duplicate_and_missing_targets_rejected(self):
        before = {'FF Mech Core': 4, 'Premium Tuner': 6}
        after = {'FF Mech Core': 5, 'Premium Tuner': 6}
        for selected in (
            [], (), {'Unknown'}, ['FF Mech Core', 'FF Mech Core'],
            ['FF Mech Core', 'Unknown'], 'FF Mech Core', None,
        ):
            with self.subTest(selected=selected), self.assertRaises(UncertainReceipt):
                verify_selected_inventory_receipt(before, after, selected)

    def test_missing_material_name_or_duplicate_alias_rejected(self):
        for before, after in (
            ({'': 4}, {'': 5}),
            ({'  ': 4}, {'  ': 5}),
            ({'FF Mech Core': 4, 'ff mech core': 1},
             {'FF Mech Core': 5, 'ff mech core': 1}),
        ):
            with self.subTest(before=before), self.assertRaises(UncertainReceipt):
                verify_selected_inventory_receipt(
                    before, after, set(before))


if __name__ == '__main__':
    unittest.main()
