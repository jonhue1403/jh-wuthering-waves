import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.automation.goals import MaterialGoal, ResourceGoalQueue, SourceMapping, parse_quantity
from src.automation.resource_policy import (
    ActionJournal, ClaimIdentity, ResourceBudget, ResourceLedger,
    ResourcePolicyError, UncertainReceipt, verify_debit,
    budget_scope_for,
)
from src.automation.routines import RoutineCoordinator, RoutineObservation


class TestResourceGoals(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'journal.json'
        self.journal = ActionJournal(self.path)
        self.identity = ClaimIdentity('account-uid', 'Asia', 'cultivation', 'observed-cycle-42')
        self.budget = ResourceBudget(120, 2, 600, 1)

    def prepare(self, **kwargs):
        args = dict(cost=60, current=121, inventory={'material': 4})
        args.update(kwargs)
        return self.journal.prepare(self.identity, self.budget, **args)

    def test_excessive_debit_121_to_1_is_uncertain_not_sixty(self):
        action = self.prepare()
        with self.assertRaises(UncertainReceipt):
            self.journal.confirm(action, current=1, inventory={'material': 8})
        receipt = self.journal.snapshot()['actions'][0]
        self.assertEqual('UNCERTAIN', receipt['state'])
        self.assertFalse(receipt['reward_received'])

    def test_missing_debit_and_ambiguous_quantity_rejected(self):
        for after in (121, 62, 60, None, '61'):
            with self.subTest(after=after), self.assertRaises(UncertainReceipt):
                verify_debit(121, after, 60)

    def test_only_independently_observed_regeneration_can_explain_one_point(self):
        self.assertEqual(60, verify_debit(121, 62, 60, observed_regeneration=1))
        with self.assertRaises(UncertainReceipt):
            verify_debit(121, 61, 60, observed_regeneration=1)

    def test_pending_survives_reload_and_prevents_duplicate_click(self):
        self.prepare()
        self.journal = ActionJournal(self.path)
        with self.assertRaises(UncertainReceipt):
            self.prepare()
        self.assertEqual(1, len(self.journal.snapshot()['actions']))

    def test_resume_with_actual_debit_and_inventory_reconciles_once(self):
        action = self.prepare()
        self.assertTrue(ActionJournal(self.path).reconcile(action, observed_identity=self.identity, current=61, inventory={'material': 8}, fresh=True))
        self.assertFalse(self.journal.reconcile(action, observed_identity=self.identity, current=61, inventory={'material': 8}, fresh=True))
        self.assertTrue(self.journal.snapshot()['actions'][0]['reward_received'])

    def test_resume_unchanged_or_missing_state_never_retries(self):
        action = self.prepare()
        with self.assertRaises(UncertainReceipt):
            self.journal.reconcile(action, observed_identity=self.identity, current=121, inventory={'material': 4}, fresh=True)
        with self.assertRaises(UncertainReceipt):
            self.prepare()
        with self.assertRaises(UncertainReceipt):
            self.journal.reconcile(action)

    def test_resume_rejects_wrong_account_server_activity_and_cycle(self):
        action = self.prepare()
        for field in ('account', 'server', 'activity', 'cycle'):
            values = dict(account=self.identity.account, server=self.identity.server,
                          activity=self.identity.activity, cycle=self.identity.cycle)
            values[field] = 'other-identity'
            with self.subTest(field=field), self.assertRaises(UncertainReceipt):
                self.journal.reconcile(action, observed_identity=ClaimIdentity(**values),
                                       current=61, inventory={'material': 8}, fresh=True)
        self.assertEqual('UNCERTAIN', self.journal.snapshot()['actions'][0]['state'])

    def test_resume_debit_only_claim_uses_fresh_matching_identity(self):
        action = self.prepare(inventory={}, receipt_kind='spend')
        self.assertTrue(self.journal.reconcile(action, observed_identity=self.identity, current=61, fresh=True))
        self.assertFalse(self.journal.snapshot()['actions'][0]['reward_received'])

    def test_no_material_progress_does_not_confirm_receipt(self):
        action = self.prepare()
        with self.assertRaises(UncertainReceipt):
            self.journal.confirm(action, current=61, inventory={'material': 4})

    def test_missing_or_regressing_inventory_is_uncertain(self):
        action = self.prepare()
        for inventory in ({}, {'material': 3}, {'other': 8}):
            with self.subTest(inventory=inventory), self.assertRaises(UncertainReceipt):
                self.journal.confirm(action, current=61, inventory=inventory)

    def test_resource_only_debit_is_separate_from_reward_receipt(self):
        action = self.prepare(inventory={}, receipt_kind='spend')
        self.journal.confirm_spend(action, current=61)
        self.assertFalse(self.journal.snapshot()['actions'][0]['reward_received'])

    def test_resource_only_confirmation_cannot_bypass_inventory_claim(self):
        action = self.prepare()
        with self.assertRaises(ResourcePolicyError):
            self.journal.confirm_spend(action, current=61)

    def test_shared_budget_covers_different_activities(self):
        action = self.prepare()
        self.journal.confirm(action, current=61, inventory={'material': 8})
        other = ClaimIdentity('account-uid', 'Asia', 'forgery', 'observed-cycle-42')
        second = self.journal.prepare(other, self.budget, cost=60, current=61, inventory={'material': 8})
        self.journal.confirm(second, current=1, inventory={'material': 12})
        with self.assertRaises(ResourcePolicyError):
            self.prepare(current=121)

    def test_pending_in_other_activity_blocks_shared_spending(self):
        self.prepare()
        other = ClaimIdentity('account-uid', 'Asia', 'daily', 'observed-cycle-42')
        with self.assertRaises(UncertainReceipt):
            self.journal.prepare(other, self.budget, cost=60, current=121, inventory={'material': 4})

    def test_pending_claim_survives_reset_rollover_and_still_blocks_spending(self):
        self.prepare()
        next_cycle = ClaimIdentity('account-uid', 'Asia', 'daily', 'observed-next-cycle')
        self.assertEqual(1, len(self.journal.unresolved(next_cycle)))
        with self.assertRaises(UncertainReceipt):
            self.journal.prepare(next_cycle, self.budget, cost=60, current=121, inventory={'material': 4})

    def test_persisted_plan_budget_scope_spans_daily_and_weekly_reset_ids(self):
        budget = ResourceBudget(60, 1, 600, 0)
        daily = ResourceLedger(self.journal, self.identity, budget, budget_scope='observed-shared-budget-cycle')
        action = daily.prepare_spend(60, 121)
        self.journal.confirm_spend(action, current=61)
        weekly_id = ClaimIdentity('account-uid', 'Asia', 'weekly', 'observed-week-cycle')
        restarted_weekly = ResourceLedger(ActionJournal(self.path), weekly_id, budget,
                                         budget_scope='observed-shared-budget-cycle')
        with self.assertRaises(ResourcePolicyError):
            restarted_weekly.prepare_spend(60, 61)

    def test_standalone_and_queue_entrypoints_share_observed_cycle_allowance(self):
        budget = ResourceBudget(60, 1, 600, 0)
        standalone = ResourceLedger(self.journal, self.identity, budget)
        action = standalone.prepare_spend(60, 121, activity='CultivationTask')
        self.journal.confirm_spend(action, current=61)
        self.assertEqual('CultivationTask', self.journal.snapshot()['actions'][0]['identity']['activity'])
        queue = ResourceLedger(ActionJournal(self.path), self.identity, budget,
                               budget_scope=budget_scope_for(self.identity))
        with self.assertRaises(ResourcePolicyError):
            queue.prepare_spend(60, 61, activity='DailyTask')

    def test_one_source_batch_updates_only_its_verified_material(self):
        first = MaterialGoal('boss-material', 4, 8, origin='user_supplied')
        other = MaterialGoal('mob-material', 2, 9, origin='user_supplied')
        queue = ResourceGoalQueue([first, other])
        queue.receive({'boss-material': 8}, materials={'boss-material'})
        self.assertTrue(queue.progress['boss-material'].goal_complete)
        self.assertEqual(2, other.owned)
        self.assertFalse(queue.progress['mob-material'].reward_received)

    def test_minimum_balance_run_time_and_spend_limits(self):
        for budget, current, elapsed in ((self.budget, 60, 0), (self.budget, 121, 600),
                                          (ResourceBudget(59, 1, 60, 0), 121, 0)):
            with self.subTest(budget=budget), self.assertRaises(ResourcePolicyError):
                self.journal.prepare(self.identity, budget, cost=60, current=current,
                                     inventory={'material': 4}, elapsed=elapsed)
        budget = ResourceBudget(120, 1, 60, 0)
        action = self.journal.prepare(self.identity, budget, cost=60, current=120, inventory={'material': 4})
        self.journal.confirm(action, current=60, inventory={'material': 8})
        with self.assertRaises(ResourcePolicyError):
            self.journal.prepare(self.identity, budget, cost=60, current=60, inventory={'material': 8})

    def test_unconfigured_and_dangerous_budgets_fail_closed(self):
        for kwargs in ({'max_spend': 0}, {'max_runs': 0}, {'max_seconds': 0},
                       {'allow_reserve': True}, {'allow_refill': True}, {'allow_premium': True},
                       {'allow_destruction': True}, {'allow_valuable_items': True}):
            args = dict(max_spend=60, max_runs=1, max_seconds=60, minimum_balance=0)
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ResourcePolicyError):
                ResourceBudget(**args)

    def test_corrupt_or_locked_journal_never_resets_history(self):
        self.path.write_text('{invalid', encoding='utf-8')
        with self.assertRaises(ResourcePolicyError):
            self.prepare()
        self.assertEqual('{invalid', self.path.read_text(encoding='utf-8'))
        lock = self.path.with_suffix('.json.lock')
        lock.write_text('interrupted writer')
        with self.assertRaises(ResourcePolicyError):
            self.journal.snapshot()

    def test_cycle_identity_and_account_isolation(self):
        self.journal.complete(self.identity, 'verified completion frame')
        self.assertTrue(self.journal.is_completed(self.identity))
        self.assertFalse(self.journal.is_completed(ClaimIdentity('other-account', 'Asia', 'cultivation', 'observed-cycle-42')))
        self.assertFalse(self.journal.is_completed(ClaimIdentity('account-uid', 'Asia', 'cultivation', 'observed-cycle-43')))
        with self.assertRaises(ResourcePolicyError):
            ClaimIdentity('', 'Asia', 'cultivation', '2026-11-08')

    def test_time_limit_checked_before_future_action(self):
        clock = Mock(side_effect=[1, 602])
        ledger = ResourceLedger(self.journal, self.identity, self.budget, clock=clock)
        with self.assertRaises(ResourcePolicyError):
            ledger.prepare(60, 121, {'material': 4})
        self.assertFalse(self.path.exists())

    def test_unknown_unqualified_conflicting_and_stale_mappings_stay_unresolved(self):
        goal = MaterialGoal('material', 4, 28, origin='user_supplied')
        mapping = SourceMapping('material', 'boss', 'CultivationTask', 'selected-row', 'screenshot hash', '3.0.4', True)
        self.assertEqual('UNRESOLVED', ResourceGoalQueue([goal]).preview('3.0.4')[0]['state'])
        self.assertEqual('UNRESOLVED', ResourceGoalQueue([goal], [mapping]).preview('3.0.3')[0]['state'])
        self.assertEqual('UNRESOLVED', ResourceGoalQueue([goal], [mapping, mapping]).preview('3.0.4')[0]['state'])
        queue = ResourceGoalQueue([goal], [mapping])
        self.assertEqual('READY', queue.preview('3.0.4')[0]['state'])
        self.assertEqual(mapping, queue.next_source('3.0.4')[1])

    def test_source_kind_must_match_existing_producer_before_selection(self):
        goal = MaterialGoal('material', 1, 10, origin='user_supplied')
        cases = (
            ('boss', 'CultivationTask', True),
            ('domain', 'ForgeryTask', True),
            ('domain', 'SimulationTask', True),
            ('domain', 'TacetTask', True),
            ('overworld', 'BoundedRouteTask', True),
            ('boss', 'BoundedRouteTask', False),
            ('domain', 'BoundedRouteTask', False),
            ('overworld', 'ForgeryTask', False),
            ('overworld', 'CultivationTask', False),
            ('domain', 'FarmEchoTask', False),
            ('daily', 'DailyTask', False),
            ('synthesis', 'BoundedRouteTask', False),
        )
        for kind, executor, permitted in cases:
            with self.subTest(kind=kind, executor=executor):
                mapping = SourceMapping(
                    'material', kind, executor, 'observed-profile',
                    'hashed evidence', '3.0.4', True,
                )
                queue = ResourceGoalQueue([goal], [mapping])
                self.assertEqual(permitted, mapping.matches(goal, '3.0.4'))
                self.assertEqual('READY' if permitted else 'UNRESOLVED',
                                 queue.preview('3.0.4')[0]['state'])
                self.assertEqual(permitted, queue.next_source('3.0.4') is not None)

    def test_truthy_qualification_and_missing_evidence_never_select_a_producer(self):
        goal = MaterialGoal('material', 1, 10, origin='user_supplied')
        for qualified, evidence in ((1, 'hash'), ('true', 'hash'), (True, ''),
                                    (True, '  '), (False, 'hash')):
            with self.subTest(qualified=qualified, evidence=evidence):
                source = SourceMapping(
                    'material', 'overworld', 'BoundedRouteTask', 'profile',
                    evidence, '3.0.4', qualified,
                )
                queue = ResourceGoalQueue([goal], [source])
                self.assertEqual('UNRESOLVED', queue.preview('3.0.4')[0]['state'])
                self.assertIsNone(queue.next_source('3.0.4'))

    def test_preview_explains_runtime_gate_and_ambiguous_mapping(self):
        goal = MaterialGoal('material', 1, 10, origin='user_supplied')
        source = SourceMapping(
            'material', 'boss', 'CultivationTask', 'profile',
            'hash', '3.0.4', True,
        )
        one = ResourceGoalQueue([goal], [source]).preview('3.0.4')[0]
        self.assertEqual('READY', one['state'])
        self.assertIn('runtime', one['reason'])
        two = ResourceGoalQueue([goal], [source, source]).preview('3.0.4')[0]
        self.assertEqual('UNRESOLVED', two['state'])
        self.assertIn('Ambiguous', two['reason'])

    def test_combat_and_reward_confirmation_do_not_complete_goal(self):
        goal = MaterialGoal('material', 4, 8, origin='user_supplied')
        queue = ResourceGoalQueue([goal])
        queue.observe_stage('material', combat=True, confirmation=True)
        self.assertEqual(4, goal.missing)
        self.assertFalse(queue.progress['material'].reward_received)
        self.assertFalse(queue.progress['material'].goal_complete)
        queue.receive({'material': 8})
        self.assertTrue(queue.progress['material'].goal_complete)

    def test_strict_normalized_quantity_rejects_numeric_noise(self):
        self.assertEqual((4, 28), parse_quantity('４ ／ ２８'))
        for text in ('4/28 extra', '-4/28', '4.0/28', '4/0', '4/28/2', '4O/28'):
            self.assertIsNone(parse_quantity(text), text)


class TestRoutineCoordination(unittest.TestCase):
    setUp = TestResourceGoals.setUp
    def observation(self, **kwargs):
        data = dict(account='account-uid', server='Asia', activity='daily', cycle='observed-cycle-42',
                    observed_at=100, eligible=True, completed=False, evidence='fresh frame hash',
                    profile='reviewed-daily-profile', qualified=True)
        data.update(kwargs)
        return RoutineObservation(**data)

    def coordinator(self):
        return RoutineCoordinator(self.journal, self.budget, clock=lambda: 101)

    def test_completed_and_ineligible_routine_skip_dispatch(self):
        for before in (self.observation(completed=True), self.observation(eligible=False)):
            dispatch = Mock()
            self.coordinator().run_one(before, dispatch=dispatch, observe_after=Mock(), checkpoint=Mock())
            dispatch.assert_not_called()

    def test_success_requires_fresh_completion_and_actual_reward(self):
        before = self.observation()
        after = self.observation(observed_at=101, completed=True, reward_received=True)
        dispatch = Mock()
        self.assertEqual('COMPLETE', self.coordinator().run_one(before, dispatch=dispatch,
                         observe_after=lambda: after, checkpoint=Mock()))
        dispatch.assert_called_once_with(('src.task.DailyTask', 'DailyTask'))
        self.assertTrue(self.journal.is_completed(before.identity))

    def test_failed_return_or_interruption_blocks_duplicate_resume(self):
        before = self.observation()
        dispatch = Mock()
        with self.assertRaises(UncertainReceipt):
            self.coordinator().run_one(before, dispatch=dispatch,
                 observe_after=lambda: self.observation(observed_at=101, completed=True, reward_received=False), checkpoint=Mock())
        self.assertEqual('UNCERTAIN', self.journal.activity_state(before.identity))
        self.assertTrue(self.coordinator().preview(before).startswith('UNCERTAIN'))
        self.coordinator().run_one(before, dispatch=dispatch, observe_after=Mock(), checkpoint=Mock())
        self.assertEqual(1, dispatch.call_count)

    def test_task_failure_propagates_and_is_durable(self):
        before = self.observation()
        with self.assertRaisesRegex(RuntimeError, 'combat failed'):
            self.coordinator().run_one(before, dispatch=Mock(side_effect=RuntimeError('combat failed')),
                                      observe_after=Mock(), checkpoint=Mock())
        self.assertEqual('UNCERTAIN', ActionJournal(self.path).activity_state(before.identity))

    def test_stale_frames_and_changed_cycle_rejected(self):
        with self.assertRaises(ResourcePolicyError):
            self.coordinator().preview(self.observation(observed_at=90))
        with self.assertRaises(UncertainReceipt):
            self.coordinator().run_one(self.observation(), dispatch=Mock(), checkpoint=Mock(),
                         observe_after=lambda: self.observation(observed_at=101, completed=True,
                                                               reward_received=True, cycle='next-cycle'))

    def test_weekly_material_eligibility_is_separate_from_echo_runs(self):
        self.assertTrue(self.coordinator().preview(self.observation(activity='weekly_boss_material')).startswith('UNRESOLVED'))
        self.assertEqual('READY', self.coordinator().preview(self.observation(activity='boss_echo')))
        self.assertTrue(self.coordinator().preview(self.observation(activity='fantasies')).startswith('UNRESOLVED'))


if __name__ == '__main__':
    unittest.main()
