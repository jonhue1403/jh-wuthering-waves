"""Offline-only contracts: native F2 selector safety is NOT live qualification."""
import unittest
from unittest.mock import Mock

from src.automation.domain_selection import (
    DOMAIN_SELECTORS, inspect_domain_selector, validate_domain_selector,
)
from src.automation.resource_policy import ResourcePolicyError


class TestDomainSelection(unittest.TestCase):
    def test_native_layout_matches_existing_task_structures(self):
        self.assertEqual(20, DOMAIN_SELECTORS['ForgeryTask'][1])
        self.assertEqual(21, DOMAIN_SELECTORS['TacetTask'][1])
        self.assertEqual('Material Selection', DOMAIN_SELECTORS['SimulationTask'][0])

    def test_forgery_and_tacet_reject_zero_negative_bool_float_and_overflow(self):
        for provider, upper in (('ForgeryTask', 20), ('TacetTask', 21)):
            for value in (0, -1, True, False, 1.0, '1', upper + 1, None):
                with self.subTest(provider=provider, value=value):
                    with self.assertRaises(ResourcePolicyError):
                        validate_domain_selector(provider, value, count=upper)
            self.assertEqual(upper, validate_domain_selector(provider, upper, count=upper))
            with self.assertRaisesRegex(ResourcePolicyError, 'layout drift'):
                validate_domain_selector(provider, 1, count=upper + 1)

    def test_simulation_never_falls_back_to_shell_credit(self):
        for selected in ('Resonator EXP', 'Weapon EXP', 'Shell Credit'):
            self.assertEqual(selected, validate_domain_selector('SimulationTask', selected))
        for invalid in ('', 'Wrong Challenge', 'shell credit', 1, True, None):
            with self.subTest(selection=invalid):
                with self.assertRaisesRegex(ResourcePolicyError, 'no fallback'):
                    validate_domain_selector('SimulationTask', invalid)

    def test_plan_inspection_never_calls_selection_ready_or_authorized(self):
        self.assertIn('STATIC_SELECTOR_MISSING', inspect_domain_selector('ForgeryTask', {}))
        self.assertIn('STATIC_SELECTOR_INVALID', inspect_domain_selector(
            'TacetTask', {'Which Tacet Suppression to Farm': False}))
        self.assertIn('STATIC_SELECTOR_INVALID', inspect_domain_selector('SimulationTask', []))
        ready = inspect_domain_selector('SimulationTask', {'Material Selection': 'Weapon EXP'})
        self.assertIn('STATIC_SELECTOR_SHAPE_ONLY', ready)
        self.assertIn('CURRENT_GAME_CHALLENGE_UNOBSERVED', ready)
        self.assertNotIn('AUTHORIZED', ready)
        with self.assertRaises(ResourcePolicyError):
            validate_domain_selector('DailyTask', 1)

    def test_native_navigation_rejects_invalid_selection_before_any_input(self):
        # Actual game, Qt and inherited task initialization are not invoked.
        from src.task.ForgeryTask import ForgeryTask
        from src.task.SimulationTask import SimulationTask
        from src.task.TacetTask import TacetTask
        forgery = Mock()
        forgery.total_number = 20
        simulation = Mock()
        tacet = Mock()
        tacet.total_number = 21
        with self.assertRaises(ResourcePolicyError):
            ForgeryTask.teleport_into_domain(forgery, 0)
        with self.assertRaises(ResourcePolicyError):
            SimulationTask.teleport_into_domain(simulation, 'Unrecognized')
        with self.assertRaises(ResourcePolicyError):
            TacetTask.teleport_to_tacet(tacet, -1)
        forgery.open_boss_book.assert_not_called()
        simulation.open_boss_book.assert_not_called()
        tacet.info_set.assert_not_called()


if __name__ == '__main__':
    unittest.main()
