import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.task.BaseWWTask import BaseWWTask
from src.automation.resource_policy import ResourcePolicyError, UncertainReceipt


class ClaimFixture:
    use_stamina = BaseWWTask.use_stamina
    def __init__(self, current=121, reserve=95, after=61, split=False, cost=60):
        self.next_frame = Mock()
        self.get_stamina = Mock(return_value=(current, reserve, current + reserve))
        self.get_stamina_claim_cost = Mock(return_value=cost)
        self.get_stamina_claim_result = Mock(return_value=after)
        self.find_one = Mock(side_effect=lambda name: split if name == 'claim_stamina_sign' else False)
        self.click_dialog_left_button = Mock()
        self.click_dialog_right_button = Mock()
        self.wait_until = self.wait
        self.callback = Mock()

    def wait(self, condition, **kwargs):
        for _ in range(6):
            if condition():
                return True
        return False


class TestResourceClaims(unittest.TestCase):
    def test_stamina_parser_rejects_ambiguous_missing_and_embedded_numbers(self):
        for texts in (['121/240'], ['121/240', '95', '95'], ['121/240', '122/240', '95'],
                      ['121/240', 'reserve95'], ['241/240', '95']):
            with self.subTest(texts=texts):
                fixture = SimpleNamespace(wait_ocr=Mock(return_value=[SimpleNamespace(name=s) for s in texts]),
                                          screenshot=Mock(), info_set=Mock())
                self.assertEqual((-1, -1, -1), BaseWWTask.get_stamina(fixture))
        fixture = SimpleNamespace(wait_ocr=Mock(return_value=[SimpleNamespace(name=s) for s in ['１２１ / ２４０', '９５']]),
                                  screenshot=Mock(), info_set=Mock())
        self.assertEqual((121, 95, 216), BaseWWTask.get_stamina(fixture))

    def test_challenge_confirmation_does_not_require_or_enable_story_skip(self):
        from src.automation.session import get_session
        task = SimpleNamespace(next_frame=Mock(), in_team_and_world=Mock(return_value=False),
                               ocr=Mock(return_value=[SimpleNamespace(name='Restart Challenge')]),
                               find_one=Mock(side_effect=[None, object()]), click=Mock())
        task.wait_until = lambda condition, **kwargs: condition()
        self.assertFalse(get_session(task).allow_story_skip())
        self.assertTrue(BaseWWTask.wait_confirm_challenge_action(task, 'restart'))
        task.click.assert_called_once()
        self.assertFalse(get_session(task).allow_story_skip())
        get_session(task).enter_story_watch()
        task.click.reset_mock()
        self.assertFalse(BaseWWTask.wait_confirm_challenge_action(task, 'restart'))
        task.click.assert_not_called()

    def test_expected60_before121_after1_is_not_valid60_receipt(self):
        task = ClaimFixture(after=1)
        with self.assertRaises(UncertainReceipt):
            task.use_stamina(force_single=True, before_confirm=task.callback)
        task.click_dialog_right_button.assert_called_once()
        task.callback.assert_called_once_with(60, 121, 95)

    def test_current59_reserve95_never_confirms_refill(self):
        task = ClaimFixture(current=59)
        task.find_one = Mock(return_value=True)
        with self.assertRaises(ResourcePolicyError):
            task.use_stamina(force_single=True, before_confirm=task.callback)
        task.click_dialog_right_button.assert_not_called()
        task.click_dialog_left_button.assert_not_called()
        task.callback.assert_not_called()

    def test_existing_split_single_and_double_paths_observe_actual_debit(self):
        for force_single, after, debit in ((True, 61, 60), (False, 1, 120)):
            with self.subTest(force_single=force_single):
                task = ClaimFixture(after=after, split=True)
                self.assertEqual((after >= 60, debit), task.use_stamina(
                    force_single=force_single, before_confirm=task.callback))
                task.callback.assert_called_once_with(debit, 121, 95)
                (task.click_dialog_left_button if force_single else task.click_dialog_right_button).assert_called_once()

    def test_plain_confirmation_uses_single_claim(self):
        task = ClaimFixture()
        self.assertEqual((True, 60), task.use_stamina(before_confirm=task.callback))
        task.click_dialog_right_button.assert_called_once()

    def test_unknown_unreadable_or_conflicting_cost_never_clicks(self):
        for cost in (None, 40, -1):
            task = ClaimFixture(cost=cost)
            with self.assertRaises(ResourcePolicyError):
                task.use_stamina(before_confirm=task.callback)
            task.click_dialog_right_button.assert_not_called()
            task.callback.assert_not_called()

    def test_changed_current_or_refill_prompt_stops_at_last_boundary(self):
        task = ClaimFixture()
        task.get_stamina.side_effect = [(121, 95, 216), (59, 95, 154)]
        with self.assertRaises(UncertainReceipt):
            task.use_stamina(before_confirm=task.callback)
        task.callback.assert_not_called()
        task = ClaimFixture()
        task.find_one.side_effect = [False, False, True]
        with self.assertRaises(UncertainReceipt):
            task.use_stamina(before_confirm=task.callback)
        task.callback.assert_called_once()
        task.click_dialog_right_button.assert_not_called()

    def test_delayed_result_only_waits_does_not_reissue_confirmation(self):
        task = ClaimFixture()
        task.get_stamina_claim_result.side_effect = [None, None, 61, 61]
        self.assertEqual((True, 60), task.use_stamina(before_confirm=task.callback))
        task.click_dialog_right_button.assert_called_once()
        self.assertEqual(4, task.get_stamina_claim_result.call_count)

    def test_missing_or_ambiguous_debit_remains_uncertain(self):
        for after in (121, 60, None):
            task = ClaimFixture(after=after)
            with self.assertRaises(UncertainReceipt):
                task.use_stamina(before_confirm=task.callback)
            task.click_dialog_right_button.assert_called_once()

    def test_cancellation_after_confirm_propagates_without_second_click(self):
        task = ClaimFixture()
        task.get_stamina_claim_result.side_effect = InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):
            task.use_stamina(before_confirm=task.callback)
        task.click_dialog_right_button.assert_called_once()


if __name__ == '__main__':
    unittest.main()
