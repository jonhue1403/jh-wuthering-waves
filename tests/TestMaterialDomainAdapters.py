"""Offline checks for the shared material claim contract used by domain tasks."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.automation.goals import MaterialGoal
from src.automation.material_domain import MaterialDomainAdapter, MATERIAL_DOMAIN_LIVE_ENABLED
from src.automation.resource_policy import (
    ActionJournal, ClaimIdentity, ResourceBudget, ResourceLedger,
    ResourcePolicyError, UncertainReceipt,
)
from src.task.ForgeryTask import ForgeryTask
from src.task.ResourceRoutineTask import ResourceRoutineTask
from src.task.SimulationTask import SimulationTask
from src.task.TacetTask import TacetTask


PROVIDERS = (ForgeryTask, SimulationTask, TacetTask)


class TestMaterialDomainAdapters(unittest.TestCase):
    def _profile(self, provider, selector, material='Test Material'):
        return {
            'schema_version': 1, 'qualified': True, 'framework_version': 'runtime',
            'language': 'zh_CN', 'resolution': [1920, 1080], 'activity': 'domain',
            'qualification_evidence': 'offline calibration fixture', 'screenshot': 'calibration.png',
            'screenshot_sha256': '0' * 64, 'page_feature': 'result_screen',
            'identity_profile': 'identity.json',
            'status': {'box': [0.1, 0.1, 0.2, 0.2], 'eligible_text': 'READY', 'completed_text': 'DONE'},
            'challenge_identity': {'box': [0.1, 0.2, 0.4, 0.3], 'text': 'Exact Challenge'},
            'source_binding': {'provider': provider.PROVIDER_NAME, 'selector': selector,
                               'material': material, 'challenge_text': 'Exact Challenge'},
            'inventory': {material: {'item_text': material, 'label_box': [0.1, 0.3, 0.2, 0.4],
                                     'box': [0.3, 0.3, 0.4, 0.4]}},
        }

    def _task_for_binding(self, provider, selector):
        task = provider.__new__(provider)
        task.config = {provider.SELECTOR_KEY: selector, 'Observation Profile': 'profile.json',
                       'Challenge Identity': 'Exact Challenge'}
        return task

    def test_provider_and_material_profile_binding_is_exact(self):
        for provider, selector in ((ForgeryTask, 3), (SimulationTask, 'Shell Credit'), (TacetTask, 4)):
            with self.subTest(provider=provider.__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'profile.json'
                path.write_text(json.dumps(self._profile(provider, selector)), encoding='utf-8')
                task = self._task_for_binding(provider, selector)
                task.config['Observation Profile'] = str(path)
                observer = SimpleNamespace(profile={'inventory': {'Test Material': {}}}, activity='domain')
                with patch('src.automation.material_domain.RoutineObserver', return_value=observer):
                    task._load_material_binding([MaterialGoal('Test Material', 0, 5, 'user_supplied')])
                self.assertEqual('Test Material', task._material_goals[0].name)

    def test_missing_or_wrong_source_profile_fails_closed(self):
        task = self._task_for_binding(ForgeryTask, 3)
        with self.assertRaisesRegex(ResourcePolicyError, 'qualified provider observation profile'):
            task._load_material_binding([MaterialGoal('Test Material', 0, 5, 'user_supplied')])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            path.write_text(json.dumps(self._profile(ForgeryTask, 2)), encoding='utf-8')
            task.config['Observation Profile'] = str(path)
            observer = SimpleNamespace(profile={'inventory': {'Test Material': {}}}, activity='domain')
            with patch('src.automation.material_domain.RoutineObserver', return_value=observer):
                with self.assertRaisesRegex(ResourcePolicyError, 'exact provider, selector, challenge and material'):
                    task._load_material_binding([MaterialGoal('Test Material', 0, 5, 'user_supplied')])

    def test_fresh_challenge_ocr_must_match_exactly(self):
        task = ForgeryTask.__new__(ForgeryTask)
        task._material_profile = self._profile(ForgeryTask, 3)
        task.ocr = Mock(return_value=[SimpleNamespace(name='Different Challenge')])
        task.sleep = Mock()
        with patch('src.automation.material_domain.fresh_observation', side_effect=[1, 2, 3]):
            with self.assertRaisesRegex(ResourcePolicyError, 'exact challenge OCR mismatch'):
                task._verify_selected_challenge()

    def _claim_fixture(self, provider, baseline, after):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        identity = ClaimIdentity('acct', 'server', 'domain', 'cycle')
        ledger = ResourceLedger(ActionJournal(Path(temporary.name) / 'actions.json'), identity,
                                ResourceBudget(provider.COST * 2, 2, 90, 0))
        task = provider.__new__(provider)
        task._resource_ledger = ledger
        target = next(iter(baseline))
        task._material_goals = [MaterialGoal(target, baseline[target], baseline[target] + 10, 'user_supplied')]
        task._material_inventory = dict(baseline)
        task._material_observer = SimpleNamespace(
            activity='domain',
            identity_profile='identity.json',
            observe=Mock(return_value=(SimpleNamespace(identity=identity), dict(after))))
        task.info_set = Mock()
        task.info_incr = Mock()
        task.get_stamina = Mock(side_effect=[(100, 0, 100), (100 - provider.COST, 0, 100 - provider.COST)])
        def use_stamina(*, once, force_single, allow_reserve, before_confirm):
            before_confirm(once, 100, 0)
            return True, once
        task.use_stamina = Mock(side_effect=use_stamina)
        return task, ledger

    def test_each_provider_journals_cost_and_selected_material_receipt(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider.__name__):
                task, ledger = self._claim_fixture(provider, {'Test Material': 4}, {'Test Material': 5})
                with patch('src.automation.material_domain.observe_identity', return_value=ledger.identity):
                    task._claim_material_receipt(claim_ui_ready=lambda: True)
                action = ledger.journal.snapshot()['actions'][0]
                self.assertEqual('CONFIRMED', action['state'])
                self.assertEqual(provider.COST, action['cost'])
                self.assertEqual({'Test Material': 4}, action['inventory_before'])
                self.assertEqual({'Test Material': 5}, action['inventory_after'])
                self.assertEqual(5, task._material_goals[0].owned)

    def test_unrelated_inventory_gain_cannot_confirm_selected_material(self):
        task, ledger = self._claim_fixture(
            ForgeryTask, {'Test Material': 4, 'Other': 8}, {'Test Material': 4, 'Other': 9})
        with patch('src.automation.material_domain.observe_identity', return_value=ledger.identity):
            with self.assertRaises(UncertainReceipt):
                task._claim_material_receipt(claim_ui_ready=lambda: True)
        self.assertEqual('UNCERTAIN', ledger.journal.snapshot()['actions'][0]['state'])

    def test_failed_claim_ui_sends_no_input_or_journal(self):
        task, ledger = self._claim_fixture(ForgeryTask, {'Test Material': 4}, {'Test Material': 5})
        with self.assertRaisesRegex(ResourcePolicyError, 'claim UI was not recognized'):
            task._claim_material_receipt(claim_ui_ready=lambda: False)
        self.assertEqual([], ledger.journal.snapshot()['actions'])
        task.use_stamina.assert_not_called()

    def test_bounded_loop_stops_at_limit_and_always_leaves_on_cancellation(self):
        task, ledger = self._claim_fixture(ForgeryTask, {'Test Material': 4}, {'Test Material': 5})
        ledger.budget = ResourceBudget(40, 1, 90, 0)
        task.sleep_check = Mock()
        task._material_goals[0].required = 100
        claim = Mock()
        task._claim_material_receipt = claim
        enter, fight, restart, leave = Mock(), Mock(), Mock(), Mock()
        task.get_stamina = Mock(return_value=(100, 0, 100))
        task._material_loop(enter=enter, fight=fight, claim_ui_ready=lambda: True,
                            restart=restart, leave=leave)
        claim.assert_called_once()
        enter.assert_called_once()
        fight.assert_called_once()
        restart.assert_not_called()
        leave.assert_called_once()

        task._claim_material_receipt = Mock(side_effect=RuntimeError('cancelled'))
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            task._material_loop(enter=enter, fight=fight, claim_ui_ready=lambda: True,
                                restart=restart, leave=leave)
        self.assertEqual(2, leave.call_count)

    def test_budget_rejection_occurs_before_claim_confirmation(self):
        task, ledger = self._claim_fixture(ForgeryTask, {'Test Material': 4}, {'Test Material': 5})
        ledger.budget = ResourceBudget(20, 1, 90, 0)
        with patch('src.automation.material_domain.observe_identity', return_value=ledger.identity):
            with self.assertRaisesRegex(ResourcePolicyError, 'budget reached'):
                task._claim_material_receipt(claim_ui_ready=lambda: True)
        self.assertEqual([], ledger.journal.snapshot()['actions'])

    def test_live_domain_execution_is_disabled_without_qualification(self):
        self.assertFalse(MATERIAL_DOMAIN_LIVE_ENABLED)
        task = ForgeryTask.__new__(ForgeryTask)
        task.config = {'Preview Only': False}
        task.info_set = Mock()
        with self.assertRaisesRegex(ResourcePolicyError, 'LIVE_VERIFICATION_PENDING'):
            task._run_material_workflow(enter=Mock(), fight=Mock(), claim_ui_ready=Mock(),
                                        restart=Mock(), leave=Mock())

    def test_identity_change_blocks_journal_preparation_before_confirmation(self):
        task, ledger = self._claim_fixture(ForgeryTask, {'Test Material': 4}, {'Test Material': 5})
        changed = ClaimIdentity('other-account', 'server', 'domain', 'cycle')
        with patch('src.automation.material_domain.observe_identity', return_value=changed):
            with self.assertRaisesRegex(UncertainReceipt, 'identity changed before claim confirmation'):
                task._claim_material_receipt(claim_ui_ready=lambda: True)
        self.assertEqual([], ledger.journal.snapshot()['actions'])

    def test_satisfied_fresh_baseline_skips_entry_and_restores_standalone_ledger(self):
        task = ForgeryTask.__new__(ForgeryTask)
        task.config = {'Preview Only': False}
        task._external_resource_ledger = False
        task._resource_ledger = None
        task._material_goals = [MaterialGoal('Test Material', 5, 5, 'user_supplied')]
        task.info_set = Mock()
        ledger = Mock()
        session = SimpleNamespace(deadline=123)
        task._configure_material_ledger = Mock(side_effect=lambda: setattr(task, '_resource_ledger', ledger))
        task._read_material_baseline = Mock()
        task._material_loop = Mock()
        with patch('src.automation.material_domain.MATERIAL_DOMAIN_LIVE_ENABLED', True), \
             patch('src.automation.session.get_session', return_value=session):
            task._run_material_workflow(enter=Mock(), fight=Mock(), claim_ui_ready=Mock(),
                                        restart=Mock(), leave=Mock())
        task._material_loop.assert_not_called()
        self.assertIsNone(task._resource_ledger)
        self.assertEqual(123, session.deadline)

    def test_resource_routine_reports_provider_runtime_gate(self):
        for provider in ('ForgeryTask', 'SimulationTask', 'TacetTask'):
            supported, reason = ResourceRoutineTask._material_provider_readiness(provider)
            self.assertFalse(supported)
            self.assertIn('publisher permission', reason)


if __name__ == '__main__':
    unittest.main()
