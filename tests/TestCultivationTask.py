import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from ok import CannotFindException
from src.task.BaseCombatTask import NotInCombatException
from src.task.BaseWWTask import BaseWWTask
from src.task.CultivationTask import CultivationError, CultivationTask, MaterialGoal, parse_quantity
from src.task.DomainTask import DomainTask
from src.automation.resource_policy import ActionJournal, ClaimIdentity, ResourceBudget, ResourceLedger, ResourcePolicyError, UncertainReceipt


class TestCultivationTask(unittest.TestCase):

    def setUp(self):
        self.task = CultivationTask.__new__(CultivationTask)
        self.task._app = None
        self.task.info = {}
        self.task.goals = []
        self.task._combat_deadline = 0
        self.task.logger = Mock()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.task.config = {'Collect Optional Echo': False}
        self.task._pending_claim = None
        self.task._resource_ledger = ResourceLedger(
            ActionJournal(Path(temporary.name) / 'actions.json'),
            ClaimIdentity('test-account', 'test-server', 'cultivation', 'observed-reset-42'),
            ResourceBudget(600, 10, 900, 0))
        for name in ('next_frame', 'sleep', 'click', 'send_key', 'log_info', 'log_warning',
                     'combat_once', 'reset_combat_state', 'send_key_up', 'walk_to_treasure',
                     'pick_f', 'restart_challenge', 'make_sure_in_world',
                     'open_cultivation', 'enter_challenge'):
            setattr(self.task, name, Mock())
        self.task.pick_echo = Mock(return_value=True)
        self.task.ocr = Mock(return_value=[])
        self.task.wait_until = Mock(side_effect=lambda condition, **kwargs: condition())

    def prepare_farm(self, goals, inventories, claims, remaining):
        self.task.goals = goals
        claim_values = iter(claims)
        def claim():
            before, used = next(claim_values)
            self.task._pending_claim = self.task._resource_ledger.prepare(
                used, before, {g.name: g.owned for g in self.task.goals})
            return before, used
        self.task.claim_reward = Mock(side_effect=claim)
        self.task.read_reward_inventory = Mock(side_effect=inventories)
        self.task.read_remaining_stamina = Mock(side_effect=remaining)

    def prepare_claim(self, stamina=121, results=True):
        self.task.get_stamina = Mock(return_value=(stamina, 600, stamina + 600))
        self.task.has_claim_stamina = Mock(return_value=True)
        self.task.goals = [MaterialGoal('材料', 5, 28)]
        def use_stamina(**kwargs):
            kwargs['before_confirm'](60, stamina, 600)
            return True, 60
        self.task.use_stamina = Mock(side_effect=use_stamina)
        self.task.ocr.return_value = [SimpleNamespace(name='退出副本'),
                                      SimpleNamespace(name='重新挑战')] if results else []

    def test_parse_quantity_accepts_zero_exact_and_excess_owned(self):
        for text, expected in (('0/28', (0, 28)), ('28/28', (28, 28)),
                               ('29/28', (29, 28)), ('２８ ／ ２８', (28, 28)),
                               (' \t０ / ２８\n', (0, 28))):
            with self.subTest(text=text):
                self.assertEqual(expected, parse_quantity(text))

    def test_parse_quantity_rejects_zero_required_garbage_and_multiple_fractions(self):
        for text in ('0/0', '28/0', '垃圾文本', '', '0/28 28/28', '0/28/28'):
            with self.subTest(text=text):
                self.assertIsNone(parse_quantity(text))

    def test_material_goal_missing_stops_at_zero(self):
        for owned, missing in ((0, 28), (5, 23), (28, 0), (29, 0)):
            with self.subTest(owned=owned):
                self.assertEqual(missing, MaterialGoal('材料', owned, 28).missing)

    def test_queued_cultivation_goals_allow_only_satisfied_observed_side_items(self):
        self.task.goals = [MaterialGoal('Needed', 4, 28),
                           MaterialGoal('Satisfied', 10, 10)]
        self.task._bind_queued_goals([
            MaterialGoal('Needed', 4, 12, origin='user_supplied')])
        self.assertEqual(12, self.task.goals[0].required)
        self.assertEqual('user_supplied', self.task.goals[0].origin)
        self.assertEqual(10, self.task.goals[1].required)

    def test_queued_cultivation_goals_reject_unrequested_deficit_and_stale_count(self):
        self.task.goals = [MaterialGoal('Needed', 4, 28),
                           MaterialGoal('Also needed', 9, 10)]
        with self.assertRaisesRegex(ResourcePolicyError, 'Guidebook row does not match'):
            self.task._bind_queued_goals([
                MaterialGoal('Needed', 4, 28, origin='user_supplied')])
        self.task.goals[1].owned = 10
        with self.assertRaisesRegex(ResourcePolicyError, 'Queued inventory differs'):
            self.task._bind_queued_goals([
                MaterialGoal('Needed', 5, 28, origin='user_supplied')])

    def test_gain_for_completed_cultivation_material_never_confirms_claim(self):
        self.prepare_farm(
            [MaterialGoal('Needed', 4, 28), MaterialGoal('Satisfied', 9, 9)],
            [{'Needed': 4, 'Satisfied': 10}], [(121, 60)], [61])
        with self.assertRaisesRegex(UncertainReceipt, 'No unmet cultivation material increased'):
            self.task.farm(121)
        records = self.task._resource_ledger.journal.snapshot()['actions']
        self.assertEqual(1, len(records))
        self.assertEqual('UNCERTAIN', records[0]['state'])
        self.assertNotIn('confirmed_at', records[0])
        self.assertEqual(4, self.task.goals[0].owned)

    def test_read_stable_returns_after_two_matching_reads(self):
        reader = Mock(side_effect=[(5, 28), (5, 28)])

        self.assertEqual((5, 28), self.task.read_stable(reader, '库存'))

        self.assertEqual(2, reader.call_count)
        self.assertEqual(2, self.task.next_frame.call_count)
        self.task.sleep.assert_called_once_with(0.3)

    def test_read_stable_rejects_three_missing_reads(self):
        reader = Mock(return_value=None)

        with self.assertRaisesRegex(CultivationError, '库存识别失败'):
            self.task.read_stable(reader, '库存')

        self.assertEqual(3, reader.call_count)
        self.assertEqual(3, self.task.next_frame.call_count)
        self.assertEqual([call(0.3)] * 3, self.task.sleep.call_args_list)

    def test_read_stable_rejects_three_fluctuating_reads(self):
        reader = Mock(side_effect=[5, 8, 5])

        with self.assertRaisesRegex(CultivationError, '库存识别失败'):
            self.task.read_stable(reader, '库存')

        self.assertEqual(3, reader.call_count)
        self.assertEqual(3, self.task.next_frame.call_count)

    def test_read_stable_accepts_zero(self):
        reader = Mock(side_effect=[0, 0])

        self.assertEqual(0, self.task.read_stable(reader, '库存'))

        self.assertEqual(2, reader.call_count)

    def test_farm_does_not_restart_after_actual_inventory_meets_goal(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28)], [{'材料': 29}], [(181, 60)], [121])

        self.task.farm(181)

        self.task.combat_once.assert_called_once_with(wait_combat_time=30, target=True)
        self.task.claim_reward.assert_called_once_with()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(29, self.task.goals[0].owned)
        self.assertEqual(0, self.task.goals[0].missing)
        self.assertEqual('29/28，已满足', self.task.info['材料'])
        self.assertEqual(60, self.task.info['used stamina'])
        self.assertEqual('培养材料已满足需求', self.task.info['停止原因'])

    def test_farm_restarts_once_then_stops_with_insufficient_stamina(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28)],
                          [{'材料': 8}, {'材料': 12}], [(121, 60), (61, 60)], [61, 1])
        states = []
        self.task.restart_challenge.side_effect = lambda: states.append(
            (self.task.goals[0].owned, self.task.goals[0].missing))

        self.task.farm(121)

        self.assertEqual([(8, 20)], states)
        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.combat_once.call_count)
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual(12, self.task.goals[0].owned)
        self.assertEqual(16, self.task.goals[0].missing)
        self.assertEqual(120, self.task.info['used stamina'])
        self.assertEqual('当前结晶波片不足 60 点', self.task.info['停止原因'])

    def test_farm_stops_when_remaining_stamina_is_below_sixty(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28)], [{'材料': 8}], [(119, 60)], [59])

        self.task.farm(119)

        self.task.claim_reward.assert_called_once_with()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(8, self.task.goals[0].owned)
        self.assertEqual('当前结晶波片不足 60 点', self.task.info['停止原因'])

    def test_farm_continues_until_each_material_goal_is_complete(self):
        self.prepare_farm([MaterialGoal('材料甲', 27, 28), MaterialGoal('材料乙', 5, 10)],
                          [{'材料甲': 28, '材料乙': 8}, {'材料甲': 29, '材料乙': 10}],
                          [(121, 60), (61, 60)], [61, 1])
        states = []
        self.task.restart_challenge.side_effect = lambda: states.append(self.task.info.copy())

        self.task.farm(121)

        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual('28/28，已满足', states[0]['材料甲'])
        self.assertEqual('8/10，缺少 2 个', states[0]['材料乙'])
        self.assertNotIn('停止原因', states[0])
        self.assertEqual([29, 10], [goal.owned for goal in self.task.goals])
        self.assertEqual([0, 0], [goal.missing for goal in self.task.goals])
        self.assertEqual('29/28，已满足', self.task.info['材料甲'])
        self.assertEqual('10/10，已满足', self.task.info['材料乙'])
        self.assertEqual('培养材料已满足需求', self.task.info['停止原因'])

    def test_update_goals_rejects_inventory_regression(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, '奖励库存小于领取前库存'):
            self.task.update_goals({'材料甲': 4, '材料乙': 3})

        self.assertEqual([5, 2], [goal.owned for goal in self.task.goals])
        self.assertEqual({}, self.task.info)

    def test_update_goals_rejects_missing_material(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, '奖励库存缺少目标材料'):
            self.task.update_goals({'材料甲': 8})

        self.assertEqual([5, 2], [goal.owned for goal in self.task.goals])
        self.assertEqual({}, self.task.info)

    def test_update_goals_rejects_no_progress(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, '领取后目标材料未增加'):
            self.task.update_goals({'材料甲': 5, '材料乙': 2})

        self.assertEqual([5, 2], [goal.owned for goal in self.task.goals])
        self.assertEqual({}, self.task.info)

    def test_claim_reward_uses_stamina_once_with_force_single(self):
        self.prepare_claim()
        self.task.has_claim_stamina.side_effect = [False, True, True]

        self.assertEqual((121, 60), self.task.claim_reward())

        self.task.use_stamina.assert_called_once_with(once=60, force_single=True, allow_reserve=False, before_confirm=ANY)
        self.task.walk_to_treasure.assert_called_once_with()
        self.task.pick_f.assert_called_once_with(handle_claim=False)
        self.task.click.assert_not_called()
        self.assertEqual(121, self.task.info['current_stamina'])

    def test_claim_reward_relocates_twice_before_using_stamina_once(self):
        self.prepare_claim()
        self.task.has_claim_stamina.side_effect = [False, False, False, True, True]

        self.assertEqual((121, 60), self.task.claim_reward())

        self.assertEqual([call(), call()], self.task.walk_to_treasure.call_args_list)
        self.assertEqual([call(handle_claim=False)] * 2, self.task.pick_f.call_args_list)
        self.task.use_stamina.assert_called_once_with(once=60, force_single=True, allow_reserve=False, before_confirm=ANY)

    def test_claim_reward_stops_after_two_failed_relocations(self):
        self.prepare_claim()
        self.task.has_claim_stamina.return_value = False

        with self.assertRaisesRegex(CultivationError, '未打开领取奖励确认框'):
            self.task.claim_reward()

        self.assertEqual([call(), call()], self.task.walk_to_treasure.call_args_list)
        self.assertEqual([call(handle_claim=False)] * 2, self.task.pick_f.call_args_list)
        self.task.use_stamina.assert_not_called()

    def test_claim_reward_does_not_use_stamina_when_insufficient(self):
        self.prepare_claim(stamina=59)

        with self.assertRaisesRegex(CultivationError, '当前结晶波片不足 60 点'):
            self.task.claim_reward()

        self.task.use_stamina.assert_not_called()
        self.task.walk_to_treasure.assert_not_called()
        self.task.click.assert_not_called()
        self.task.send_key.assert_called_once_with('esc', after_sleep=0.5)

    def test_claim_reward_does_not_retry_after_result_timeout(self):
        self.prepare_claim(results=False)

        with self.assertRaisesRegex(CultivationError, '未确认奖励领取结果'):
            self.task.claim_reward()

        self.task.use_stamina.assert_called_once_with(once=60, force_single=True, allow_reserve=False, before_confirm=ANY)
        self.task.walk_to_treasure.assert_not_called()
        self.task.click.assert_not_called()
        self.assertEqual(15, self.task.wait_until.call_args.kwargs['time_out'])

    def test_claim_reward_does_not_retry_after_helper_error(self):
        self.prepare_claim()
        error = RuntimeError('claim helper failed')
        self.task.use_stamina.side_effect = error

        with self.assertRaises(RuntimeError) as raised:
            self.task.claim_reward()

        self.assertIs(error, raised.exception)
        self.task.use_stamina.assert_called_once_with(once=60, force_single=True, allow_reserve=False, before_confirm=ANY)
        self.task.walk_to_treasure.assert_not_called()
        self.task.click.assert_not_called()
        self.task.ocr.assert_not_called()






    def test_two_failed_fights_stop_without_claiming_reward(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28)], [{'材料': 8}], [(121, 60)], [61])
        self.task.combat_once.side_effect = [NotInCombatException('first fight failed'),
                                             NotInCombatException('retry fight failed')]
        self.task.read_goals = Mock(return_value=[MaterialGoal('材料', 5, 28)])
        self.task.read_current_stamina = Mock(return_value=121)

        with self.assertRaisesRegex(CultivationError, '挑战连续失败 2 次'):
            self.task.farm(121)

        self.assertEqual(2, self.task.combat_once.call_count)
        self.assertEqual(2, self.task.reset_combat_state.call_count)
        self.task.enter_challenge.assert_called_once_with()
        self.task.claim_reward.assert_not_called()
        self.task.read_reward_inventory.assert_not_called()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(5, self.task.goals[0].owned)
        self.assertEqual(0, self.task._combat_deadline)

    def test_combat_timeout_stops_through_sleep_check(self):
        started = 100
        deadline = started + self.task.COMBAT_TIMEOUT

        def combat_once(**kwargs):
            self.assertEqual(deadline, self.task._combat_deadline)
            self.task.sleep_check()
            self.task.sleep_check()

        self.task.combat_once.side_effect = combat_once
        with patch('src.task.CultivationTask.time.monotonic',
                   side_effect=[started, deadline - 1, deadline]), \
                patch.object(DomainTask, 'sleep_check') as parent_sleep_check:
            with self.assertRaisesRegex(CultivationError, '战斗超过 600 秒'):
                self.task.fight()
            parent_sleep_check.assert_called_once_with()

        self.task.combat_once.assert_called_once_with(wait_combat_time=30, target=True)
        self.task.reset_combat_state.assert_called_once_with('cultivation combat ended')
        self.assertEqual(0, self.task._combat_deadline)


if __name__ == '__main__':
    unittest.main()
