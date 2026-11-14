import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.automation.goals import MaterialGoal, ResourceGoalQueue, SourceMapping
from src.automation.observations import RoutineObserver
from src.automation.resource_policy import (
    ActionJournal, ClaimIdentity, ResourceBudget, ResourceLedger, ResourcePolicyError, UncertainReceipt,
)
from src.automation.session import get_session
from src.automation.routines import RoutineObservation
from src.automation.weekly import WeeklyActivityAdapter
from src.task.ResourceRoutineTask import ResourceRoutineTask
from src.task.WWOneTimeTask import WWOneTimeTask


class TestResourceRoutineTask(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.path = self.folder / 'plan.json'
        self.task = ResourceRoutineTask.__new__(ResourceRoutineTask)
        self.task._app = None
        self.task.info = {}
        self.task.logger = Mock()
        self.task.config = {'Plan Path': str(self.path), 'Preview Only': True, 'Maximum Activities': 3,
                            'Reconcile Pending Only': False}
        self.task.click = Mock()
        self.plan = {'schema_version': 1, 'goals': [{'name': 'Known material', 'owned': 4,
                    'required': 28, 'origin': 'user_supplied'}], 'sources': [], 'activities': [],
                    'budget': {'max_spend': 60, 'max_runs': 1, 'max_seconds': 60, 'minimum_balance': 1}}
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')

    def ledger(self):
        return ResourceLedger(ActionJournal(self.folder / 'journal.json'),
                              ClaimIdentity('uid', 'Asia', 'daily', 'cycle-42'),
                              ResourceBudget(60, 1, 60, 1))

    def test_preview_is_reachable_and_does_not_start_or_click(self):
        with patch.object(WWOneTimeTask, 'run', side_effect=AssertionError('preview started game')):
            self.task.run()
        self.task.click.assert_not_called()
        preview = self.task.info['Goal queue preview']
        self.assertEqual('UNRESOLVED', preview[0]['state'])
        self.assertEqual('user_supplied', preview[0]['origin'])

    def test_plan_requires_labelled_targets_and_activity_bound(self):
        del self.plan['goals'][0]['origin']
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')
        with self.assertRaises(ResourcePolicyError):
            self.task.run()
        self.plan['goals'] = []
        self.plan['activities'] = [{}] * 4
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')
        with self.assertRaises(ResourcePolicyError):
            self.task.run()
        self.task.click.assert_not_called()

    def test_config_and_shared_ledger_restore_after_inherited_failure(self):
        child = SimpleNamespace(default_config={'Which to Farm': 'Tacet Suppression'},
                                config={'Which to Farm': 'Tacet Suppression'})
        self.task.get_task_by_class = Mock(return_value=child)
        ledger = self.ledger()
        session = get_session(self.task)
        observed = []
        def dispatch(cls):
            observed.append((child.config['Which to Farm'], child._resource_ledger, session.resource_ledger))
            raise RuntimeError('inherited task failed')
        self.task.run_task_by_class = Mock(side_effect=dispatch)
        with self.assertRaisesRegex(RuntimeError, 'inherited task failed'):
            self.task._dispatch('DailyTask', {'Which to Farm': 'Forgery Challenge'}, ledger)
        self.assertEqual([('Forgery Challenge', ledger, ledger)], observed)
        self.assertEqual('Tacet Suppression', child.config['Which to Farm'])
        self.assertIsNone(child._resource_ledger)
        self.assertIsNone(session.resource_ledger)

    def test_destruction_and_unknown_executor_are_not_dispatched(self):
        child = SimpleNamespace(default_config={},
                                config={'Additional Tasks to Run After Daily Task': ['Merge Echo If discarded > 1000']})
        self.task.get_task_by_class = Mock(return_value=child)
        self.task.run_task_by_class = Mock()
        with self.assertRaises(ResourcePolicyError):
            self.task._dispatch('DailyTask', {}, self.ledger())
        with self.assertRaises(ResourcePolicyError):
            self.task._dispatch('arbitrary.module.DestructiveTask', {}, self.ledger())
        self.task.run_task_by_class.assert_not_called()

    def test_unadapted_domain_material_providers_reject_before_task_lookup(self):
        self.task.get_task_by_class = Mock(side_effect=AssertionError('unsafe inherited task lookup'))
        self.task.run_task_by_class = Mock(side_effect=AssertionError('unsafe inherited task run'))
        goal = MaterialGoal('Known material', 4, 28, origin='user_supplied')
        for provider in ('ForgeryTask', 'SimulationTask', 'TacetTask'):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(ResourcePolicyError, 'PROVIDER_ADAPTER_PENDING'):
                    self.task._dispatch(provider, {}, self.ledger(), queued_goals=[goal])
        self.task.get_task_by_class.assert_not_called()
        self.task.run_task_by_class.assert_not_called()
        with self.assertRaisesRegex(ResourcePolicyError, 'UNSUPPORTED_MATERIAL_PROVIDER'):
            self.task._dispatch('DailyTask', {}, self.ledger(), queued_goals=[goal])
        self.task.get_task_by_class.assert_not_called()

    def test_domain_source_preview_reports_adapter_block_without_input(self):
        source = SourceMapping('Known material', 'domain', 'ForgeryTask',
                               'candidate-observation.json', 'unit-evidence', 'unit-runtime', True)
        queue = ResourceGoalQueue([MaterialGoal('Known material', 4, 28,
                                               origin='user_supplied')], [source])
        self.task._load_plan = Mock(return_value=(self.path, self.plan, queue))
        with (patch('src.task.ResourceRoutineTask.importlib.metadata.version',
                    return_value='unit-runtime'),
              patch.object(WWOneTimeTask, 'run', side_effect=AssertionError('preview started game'))):
            self.task.run()
        self.assertEqual('READY', self.task.info['Goal queue preview'][0]['state'])
        self.assertIn('PROVIDER_ADAPTER_PENDING',
                      self.task.info['Material provider readiness']['Known material'])
        self.task.click.assert_not_called()

    def test_domain_material_dispatch_fails_before_session_or_journal(self):
        from contextlib import ExitStack
        self.task.config.update({'Preview Only': False, 'Maximum Activities': 1})
        source = SourceMapping('Known material', 'domain', 'SimulationTask',
                               'candidate-observation.json', 'unit-evidence', 'unit-runtime', True)
        queue = ResourceGoalQueue([MaterialGoal('Known material', 4, 28,
                                               origin='user_supplied')], [source])
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.task, '_load_plan',
                                             return_value=(self.path, self.plan, queue)))
            stack.enter_context(patch('src.task.ResourceRoutineTask.importlib.metadata.version',
                                      return_value='unit-runtime'))
            start = stack.enter_context(patch.object(WWOneTimeTask, 'run'))
            identity = stack.enter_context(patch('src.task.ResourceRoutineTask.observe_identity'))
            observer = stack.enter_context(patch('src.task.ResourceRoutineTask.RoutineObserver'))
            with self.assertRaisesRegex(ResourcePolicyError, 'Unadapted material providers'):
                self.task.run()
            start.assert_not_called()
            identity.assert_not_called()
            observer.assert_not_called()
        self.assertFalse((self.folder / 'automation-actions.json').exists())
        self.task.click.assert_not_called()

    def test_readonly_reconciliation_remains_allowed_for_pending_domain_provider(self):
        self.task.config.update({'Preview Only': False, 'Reconcile Pending Only': True})
        source = SourceMapping('Known material', 'domain', 'TacetTask',
                               'candidate-observation.json', 'unit-evidence', 'unit-runtime', True)
        queue = ResourceGoalQueue([MaterialGoal('Known material', 4, 28,
                                               origin='user_supplied')], [source])
        plan = dict(self.plan, sources=[], activities=[])
        self.task._load_plan = Mock(return_value=(self.path, plan, queue))
        observer = Mock()
        observer.observe.return_value = (RoutineObservation(
            'uid', 'Asia', 'domain', 'cycle-42', 100, True, False,
            'read-only observation'), {'Known material': 4})
        observer.current_waveplates.return_value = 120
        with patch('src.task.ResourceRoutineTask.importlib.metadata.version',
                   return_value='unit-runtime'), patch(
                   'src.task.ResourceRoutineTask.RoutineObserver', return_value=observer), patch.object(
                   WWOneTimeTask, 'run', side_effect=AssertionError('reconciliation started game')):
            self.task.run()
        self.assertEqual('Fresh observations checked; no claim inputs sent',
                         self.task.info['Reconciliation'])
        self.assertIn('PROVIDER_ADAPTER_PENDING',
                      self.task.info['Material provider readiness']['Known material'])
        self.task.click.assert_not_called()

    def _material_run_context(self, *, other_goal=False, after_inventory=None):
        from contextlib import ExitStack
        self.task.config['Maximum Activities'] = 1
        self.task.config['Preview Only'] = False
        goals = [MaterialGoal('Known material', 4, 28, origin='user_supplied')]
        if other_goal:
            goals.append(MaterialGoal('Other material', 2, 9, origin='user_supplied'))
        source = SourceMapping('Known material', 'overworld', 'BoundedRouteTask',
                               'reviewed-source.json', 'unit-evidence', 'unit-runtime', True)
        mappings = [source]
        if other_goal:
            mappings.append(SourceMapping('Other material', 'overworld', 'BoundedRouteTask',
                                          'reviewed-source.json', 'unit-evidence', 'unit-runtime', True))
        queue = ResourceGoalQueue(goals, mappings)
        plan = {'activities': [], 'sources': [], 'budget_identity_profile': 'budget.json',
                'budget': self.plan['budget'], 'executor_config': {}}
        before = RoutineObservation('uid', 'Asia', 'overworld', 'cycle-42',
                                    100.0, True, False, 'observed-before')
        after = RoutineObservation('uid', 'Asia', 'overworld', 'cycle-42',
                                   101.0, True, False, 'observed-after')
        initial = {'Known material': 4, **({'Other material': 2} if other_goal else {})}
        observer = Mock()
        observer.observe.side_effect = [(before, initial)]
        if after_inventory is not None:
            observer.observe.side_effect.append((after, after_inventory))
        stack = ExitStack()
        stack.enter_context(patch.object(self.task, '_load_plan', return_value=(self.path, plan, queue)))
        stack.enter_context(patch.object(WWOneTimeTask, 'run', return_value=None))
        stack.enter_context(patch('src.task.ResourceRoutineTask.importlib.metadata.version',
                                  return_value='unit-runtime'))
        stack.enter_context(patch('src.task.ResourceRoutineTask.observe_identity',
                                  return_value=ClaimIdentity('uid', 'Asia', 'resource_budget', 'cycle-42')))
        stack.enter_context(patch('src.task.ResourceRoutineTask.RoutineObserver',
                                  return_value=observer))
        return stack, queue, observer, initial, source

    def test_goal_attempt_identity_binds_source_and_fresh_inventory(self):
        identity = ClaimIdentity('uid', 'Asia', 'overworld', 'cycle-42')
        source = SourceMapping('Known material', 'overworld', 'BoundedRouteTask',
                               'one-profile', 'evidence', 'unit-runtime', True)
        goal = MaterialGoal('Known material', 4, 28, origin='user_supplied')
        create = ResourceRoutineTask._goal_attempt_identity
        first = create(identity, source, [goal], {'Known material': 4})
        self.assertEqual(first, create(identity, source, [goal], {'Known material': 4}))
        self.assertNotEqual(first, create(identity, source, [goal], {'Known material': 5}))
        changed = SourceMapping('Known material', 'overworld', 'BoundedRouteTask',
                                'different-profile', 'evidence', 'unit-runtime', True)
        self.assertNotEqual(first, create(identity, changed, [goal], {'Known material': 4}))
        with self.assertRaises(ResourcePolicyError):
            create(identity, source, [goal], {})

    def test_failed_material_dispatch_records_uncertain_and_blocks_replay(self):
        stack, queue, observer, before, source = self._material_run_context()
        dispatch = Mock(side_effect=RuntimeError('inherited executor interrupted'))
        with stack, patch.object(self.task, '_dispatch', dispatch):
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                self.task.run()
            records = ActionJournal(self.folder / 'automation-actions.json').snapshot()['activities']
            self.assertEqual(['UNCERTAIN'], [item['state'] for item in records.values()])
            # Recreate a fresh read, but the same material and inventory baseline.
            observer.observe.side_effect = [(RoutineObservation(
                'uid', 'Asia', 'overworld', 'cycle-42', 102, True, False, 'new-frame'), before)]
            with self.assertRaises(UncertainReceipt):
                self.task.run()
        dispatch.assert_called_once()
        self.assertEqual(4, queue.goals[0].owned)

    def test_material_batch_requires_all_baselines_before_input(self):
        stack, _, observer, _, _ = self._material_run_context(other_goal=True)
        # The observer read lacks the second material; the primary goal alone
        # must never authorize an inherited multi-material executor.
        observation = RoutineObservation('uid', 'Asia', 'overworld', 'cycle-42',
                                         100.0, True, False, 'observed-before')
        observer.observe.side_effect = [(observation, {'Known material': 4})]
        dispatch = Mock()
        with stack, patch.object(self.task, '_dispatch', dispatch):
            with self.assertRaises(ResourcePolicyError):
                self.task.run()
        dispatch.assert_not_called()

    def test_observed_material_gain_completes_durable_attempt(self):
        stack, queue, _, _, _ = self._material_run_context(after_inventory={'Known material': 6})
        dispatch = Mock()
        with stack, patch.object(self.task, '_dispatch', dispatch):
            self.task.run()
        dispatch.assert_called_once()
        self.assertEqual(6, queue.goals[0].owned)
        records = ActionJournal(self.folder / 'automation-actions.json').snapshot()['activities']
        self.assertEqual(['COMPLETE'], [item['state'] for item in records.values()])

    def test_satisfied_goal_is_excluded_from_bounded_receipt_batch(self):
        stack, queue, _, _, _ = self._material_run_context(
            other_goal=True, after_inventory={'Known material': 6})
        queue.goals[1].required = queue.goals[1].owned  # Already complete.
        dispatch = Mock()
        with stack, patch.object(self.task, '_dispatch', dispatch):
            self.task.run()
        self.assertEqual(['Known material'],
                         [g.name for g in dispatch.call_args.kwargs['queued_goals']])
        self.assertEqual(6, queue.goals[0].owned)
        self.assertEqual(2, queue.goals[1].owned)
        self.assertEqual(
            ['COMPLETE'],
            [item['state'] for item in ActionJournal(
                self.folder / 'automation-actions.json').snapshot()['activities'].values()])

    def test_incidental_gain_for_satisfied_goal_cannot_confirm_active_goal(self):
        stack, queue, _, _, _ = self._material_run_context(
            other_goal=True,
            after_inventory={'Known material': 4, 'Other material': 3})
        queue.goals[1].required = queue.goals[1].owned
        dispatch = Mock()
        with stack, patch.object(self.task, '_dispatch', dispatch):
            with self.assertRaisesRegex(UncertainReceipt, 'no actual target inventory increase'):
                self.task.run()
        dispatch.assert_called_once()
        self.assertEqual(4, queue.goals[0].owned)
        self.assertEqual(
            ['UNCERTAIN'],
            [item['state'] for item in ActionJournal(
                self.folder / 'automation-actions.json').snapshot()['activities'].values()])

    def test_multi_material_bounded_route_rejects_before_inventory_or_journal(self):
        stack, _, observer, _, _ = self._material_run_context(other_goal=True)
        dispatch = Mock()
        with stack, patch.object(self.task, '_dispatch', dispatch):
            with self.assertRaisesRegex(ResourcePolicyError, 'exactly one unmet material goal'):
                self.task.run()
        observer.observe.assert_not_called()
        dispatch.assert_not_called()
        self.assertFalse((self.folder / 'automation-actions.json').exists())

    def test_missing_weekly_profile_stops_before_legacy_claim_navigation(self):
        with self.assertRaisesRegex(ResourcePolicyError, 'LIVE_VERIFICATION_PENDING'):
            WeeklyActivityAdapter(self.task, '')
        self.task.click.assert_not_called()


class TestRoutineObserver(unittest.TestCase):
    def observer(self, inventory):
        observer = RoutineObserver.__new__(RoutineObserver)
        observer.activity = 'daily'
        observer.path = Path('unit-test-profile.json')
        observer.identity_profile = 'unit-identity-profile.json'
        observer.profile = {'page_feature': 'unit_page',
            'status': {'box': [0.1, 0.1, 0.2, 0.2], 'completed_text': 'Complete', 'eligible_text': 'Ready'},
            'inventory': {'material': {'box': [0.2, 0.2, 0.3, 0.3],
                                       'label_box': [0.2, 0.3, 0.3, 0.4], 'item_text': 'material'}}}
        observer.task = SimpleNamespace(find_one=Mock(return_value=True), sleep=Mock(),
            ocr=Mock(side_effect=[[SimpleNamespace(name='Complete')], [SimpleNamespace(name='material')],
                                 [SimpleNamespace(name=str(inventory))]] * 2))
        return observer

    def test_task_return_needs_actual_inventory_progress(self):
        identity = ClaimIdentity('uid', 'Asia', 'daily', 'cycle-42')
        with patch('src.automation.observations.observe_identity', return_value=identity), \
             patch('src.automation.observations.fresh_observation', side_effect=[1, 2]):
            observation, inventory = self.observer(8).observe({'material': 4})
        self.assertTrue(observation.completed)
        self.assertTrue(observation.reward_received)
        self.assertEqual({'material': 8}, inventory)

    def test_completion_label_without_inventory_progress_is_uncertain(self):
        identity = ClaimIdentity('uid', 'Asia', 'daily', 'cycle-42')
        with patch('src.automation.observations.observe_identity', return_value=identity), \
             patch('src.automation.observations.fresh_observation', side_effect=[1, 2]), \
             self.assertRaises(ResourcePolicyError):
            self.observer(4).observe({'material': 4})

    def test_wrong_item_with_plausible_quantity_is_rejected(self):
        identity = ClaimIdentity('uid', 'Asia', 'daily', 'cycle-42')
        observer = self.observer(8)
        observer.task.ocr.side_effect = [[SimpleNamespace(name='Complete')], [SimpleNamespace(name='wrong material')]]
        with patch('src.automation.observations.observe_identity', return_value=identity), \
             patch('src.automation.observations.fresh_observation', return_value=1), \
             self.assertRaisesRegex(ResourcePolicyError, 'item name'):
            observer.observe({'material': 4})


class TestFreshIdentity(unittest.TestCase):
    def task(self):
        import time
        window = SimpleNamespace(hwnd=1234, exists=True, visible=True)
        capture = SimpleNamespace(hwnd_window=window, _jh_frame_timestamp=time.monotonic(), _jh_frame_sequence=42)
        return SimpleNamespace(hwnd=window, executor=SimpleNamespace(interaction=SimpleNamespace(capture=capture)),
                               next_frame=Mock(return_value=object()))

    def test_repeated_capture_sequence_cannot_authorize_stable_identity(self):
        from src.automation.identity import fresh_observation
        from src.automation.session import SessionStopped
        task = self.task()
        sequence = fresh_observation(task)
        self.assertEqual(42, sequence)
        with self.assertRaisesRegex(SessionStopped, 'distinct frame'):
            fresh_observation(task, sequence)

    def test_missing_stale_and_wrong_window_captures_fail_closed(self):
        from src.automation.identity import fresh_observation
        from src.automation.session import SessionStopped
        task = self.task()
        task.next_frame.return_value = None
        with self.assertRaises(ResourcePolicyError):
            fresh_observation(task)
        task = self.task()
        task.executor.interaction.capture._jh_frame_timestamp = 0
        with self.assertRaises(SessionStopped):
            fresh_observation(task)
        task = self.task()
        task.executor.interaction.capture.hwnd_window = SimpleNamespace(hwnd=9999)
        with self.assertRaises(SessionStopped):
            fresh_observation(task)


if __name__ == '__main__':
    unittest.main()
