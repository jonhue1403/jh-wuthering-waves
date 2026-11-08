"""Integration regressions against the installed OK executor API.

These tests use TaskExecutor's real read-only properties and wait/lifecycle
methods, with fake capture/input backends. No test sends real OS/game input.
"""
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ok.task.TaskExecutor import TaskExecutor
from ok.device.interaction_methods.do_nothing import DoNothingInteraction

from src.automation.input_guard import (GuardedInteraction, install_input_guard,
                                        is_effect_free_interaction, validate_observation)
from src.automation.session import Session, SessionStopped, guarded_run


class FakeFocusBackend:
    """Models Pynput's background-release refusal without creating controllers."""

    def __init__(self, capture):
        self.capture = capture
        self.check_clickable = True
        self.foreground = True
        self.events = []
        self.hwnd_window = SimpleNamespace(hwnd=capture.hwnd_window.hwnd,
                                           is_foreground=lambda: self.foreground)
        self.on_move = None

    def should_capture(self):
        return not self.check_clickable or self.foreground

    def _event(self, name, key):
        if self.check_clickable and not self.foreground:
            return
        self.events.append((name, key))

    def send_key_down(self, key):
        self._event('key_down', key)

    def send_key_up(self, key):
        self._event('key_up', key)

    def mouse_down(self, x=-1, y=-1, name=None, key='left'):
        self._event('mouse_down', key)

    def mouse_up(self, key='left'):
        self._event('mouse_up', key)

    def move(self, x, y):
        self._event('move', (x, y))
        if self.on_move:
            self.on_move()

    def swipe(self, *args, **kwargs):
        self.events.append(('raw_swipe', args))

    def click(self, *args, **kwargs):
        self.events.append(('raw_click', args))

    def scroll(self, x, y, amount):
        # Real Pynput.scroll has no clickable check: the adapter must block it.
        self.events.append(('scroll', (x, y, amount)))

    def on_run(self):
        self.events.append(('focus', None))


class FakeCondition:
    def __init__(self):
        self.wait = Mock(return_value=False)
        self.notify_all = Mock()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TestAutomationAdapter(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.window = SimpleNamespace(hwnd=2718, exists=True, visible=True)
        self.capture = SimpleNamespace(hwnd_window=self.window,
                                       _jh_frame_timestamp=time.monotonic(),
                                       _jh_frame_sequence=1)
        self.backend = FakeFocusBackend(self.capture)
        # Preserve the installed class's interaction/_job_override properties.
        # Its normal constructor would start framework/OCR setup unnecessarily.
        self.executor = TaskExecutor.__new__(TaskExecutor)
        self.executor.thread = threading.current_thread()
        self.executor.current_job = None
        self.executor.current_task = SimpleNamespace(disable=Mock(), unpause=Mock())
        self.executor.device_manager = SimpleNamespace(interaction=self.backend,
                                                        capture_method=self.capture,
                                                        do_start=Mock())
        self.executor._last_frame_time = time.time()
        self.executor._wake_condition = FakeCondition()
        self.executor._wake_version = 7
        self.executor.exit_event = threading.Event()
        self.executor.paused = False
        self.executor.reset_scene = Mock()
        self.executor.check_enabled = Mock(return_value=True)
        self.capture_frame = Mock(return_value=object())
        self.executor.next_frame = self.capture_frame
        self.executor._jh_session = self.session
        self.task = SimpleNamespace(executor=self.executor, _executor=self.executor,
                                    hwnd=self.window)

    def own_input(self):
        self.session.owner = 'offline-adapter-test'
        self.session.thread = threading.get_ident()
        self.session.deadline = time.monotonic() + 60

    def test_installs_on_manager_without_assigning_readonly_executor_property(self):
        self.assertIsNone(TaskExecutor.interaction.fset)
        with self.assertRaises(AttributeError):
            self.executor.interaction = self.backend
        install_input_guard(self.task, self.session)
        self.assertIsInstance(self.executor.device_manager.interaction, GuardedInteraction)
        self.assertIs(self.executor.interaction.wrapped, self.backend)
        install_input_guard(self.task, self.session)
        self.assertEqual(len(self.session._release), 1)

    def test_actual_framework_noop_remains_unwrapped_for_saved_image_callbacks(self):
        fixture_backend = DoNothingInteraction(self.capture)
        self.executor.device_manager.interaction = fixture_backend
        install_input_guard(self.task, self.session)
        self.assertIs(self.executor.interaction, fixture_backend)
        self.assertEqual(self.session._release, [])
        self.assertIsNone(self.session.owner)
        # TestMap.load_stars calls inherited input directly outside task.run().
        self.executor.interaction.click(10, 10)
        self.executor.interaction.send_key_down('w')

    def test_actual_noop_run_avoids_operational_lease_and_consumption_gate_only(self):
        fixture_backend = DoNothingInteraction(self.capture)
        self.executor.device_manager.interaction = fixture_backend
        self.session.enter_story_watch()
        self.session.pause('offline fixture has no operational lease')
        def fixture_run(task):
            task.executor.interaction.click(10, 10)
            return 'fixture branch exercised'
        FixtureTask = type('MergeEchoTask', (), {'run': guarded_run(fixture_run)})
        task = FixtureTask()
        task._executor = task.executor = self.executor
        task.hwnd = self.window
        self.assertEqual(task.run(), 'fixture branch exercised')
        self.assertIsNone(self.session.owner)
        self.assertTrue(self.session.story_locked)
        self.assertFalse(self.session.allow_story_skip())
        # Switching back to an input-capable backend restores all operative gates.
        self.executor.device_manager.interaction = self.backend
        with self.assertRaisesRegex(SessionStopped, 'valuable-item consumption'):
            task.run()
        self.assertEqual(self.backend.events, [])

    def test_noop_bypass_rejects_names_subclasses_and_class_spoofing(self):
        Lookalike = type('DoNothingInteraction', (FakeFocusBackend,), {})
        class OverriddenNoop(DoNothingInteraction):
            def click(self, *args, **kwargs):
                raise AssertionError('An overridden backend is not effect-free')
        class ClassSpoof:
            @property
            def __class__(self):
                return DoNothingInteraction
        for backend in (self.backend, Lookalike(self.capture), OverriddenNoop(self.capture), ClassSpoof()):
            with self.subTest(backend=type(backend).__name__):
                self.assertFalse(is_effect_free_interaction(backend))
        self.executor.device_manager.interaction = Lookalike(self.capture)
        install_input_guard(self.task, self.session)
        self.assertIsInstance(self.executor.interaction, GuardedInteraction)
        with self.assertRaisesRegex(SessionStopped, 'No activity owns'):
            self.executor.interaction.click(1, 1)

    def test_wraps_current_job_override_only_on_its_executor_thread(self):
        job_backend = FakeFocusBackend(self.capture)
        self.executor.current_job = SimpleNamespace(interaction=job_backend, capture=self.capture)
        install_input_guard(self.task, self.session)
        self.assertIsInstance(self.executor.current_job.interaction, GuardedInteraction)
        self.assertIs(self.executor.interaction.wrapped, job_backend)
        self.assertIs(self.executor.device_manager.interaction, self.backend)

        # A different thread sees the manager backend under the real property.
        self.executor.thread = object()
        install_input_guard(self.task, self.session)
        self.assertIsInstance(self.executor.device_manager.interaction, GuardedInteraction)
        self.assertIs(self.executor.interaction.wrapped, self.backend)

    def test_rebind_guards_new_backend_and_cancels_owned_activity(self):
        replacement = FakeFocusBackend(self.capture)
        def replace_backend():
            self.executor.device_manager.interaction = replacement
            return 'rebound'
        self.executor.device_manager.do_start = replace_backend
        install_input_guard(self.task, self.session)
        self.own_input()
        self.assertEqual(self.executor.device_manager.do_start(), 'rebound')
        self.assertEqual(self.session.state, 'CANCELLED')
        self.assertIsInstance(self.executor.interaction, GuardedInteraction)
        self.assertIs(self.executor.interaction.wrapped, replacement)
        with self.assertRaises(SessionStopped):
            self.executor.interaction.send_key_down('w')
        self.assertEqual(replacement.events, [])

    def test_next_frame_guards_a_job_override_created_after_initial_install(self):
        install_input_guard(self.task, self.session)
        job_backend = FakeFocusBackend(self.capture)
        self.executor.current_job = SimpleNamespace(interaction=job_backend, capture=self.capture)
        self.assertIs(self.executor.interaction, job_backend)
        self.assertIsNotNone(self.executor.next_frame())
        self.assertIsInstance(self.executor.interaction, GuardedInteraction)
        self.assertIs(self.executor.interaction.wrapped, job_backend)
        self.assertEqual(self.capture._jh_frame_sequence, self.executor._last_frame_time)
        self.assertLessEqual(time.monotonic() - self.capture._jh_frame_timestamp, 2)

    def test_wait_preserves_real_wake_version_signature_and_bounds_owned_wait(self):
        install_input_guard(self.task, self.session)
        self.own_input()
        self.assertFalse(self.executor._wait_for_activity(1, 7))
        self.executor._wake_condition.wait.assert_called_once_with(.1)
        self.executor._wake_condition.wait.reset_mock()
        self.assertTrue(self.executor._wait_for_activity(1, wake_version=6))
        self.executor._wake_condition.wait.assert_not_called()

    def test_framework_pause_stop_and_stop_current_release_immediately(self):
        for method, expected in (('pause', 'PAUSED'), ('stop', 'CANCELLED'),
                                 ('stop_current_task', 'CANCELLED')):
            with self.subTest(method=method):
                self.setUp()
                install_input_guard(self.task, self.session)
                guard = self.executor.interaction
                self.own_input()
                with patch('src.overworld.input_access.require_game_input_access'):
                    guard.send_key_down('w')
                    guard.mouse_down(key='left')
                getattr(self.executor, method)()
                self.assertEqual(self.session.state, expected)
                self.assertEqual(self.backend.events[-2:], [('key_up', 'w'), ('mouse_up', 'left')])
                self.assertFalse(guard.keys)
                self.assertFalse(guard.buttons)

    def test_takeover_releases_only_tracked_inputs_even_when_not_foreground(self):
        guard = GuardedInteraction(self.backend, self.session, lambda: None)
        self.own_input()
        guard.send_key_down('w')
        guard.mouse_down(key='left')
        self.backend.foreground = False
        # Direct fake Pynput release would refuse this background target.
        self.backend.send_key_up('w')
        self.assertEqual(self.backend.events, [('key_down', 'w'), ('mouse_down', 'left')])
        self.session.takeover('operator switched away')
        self.assertEqual(self.backend.events[-2:], [('key_up', 'w'), ('mouse_up', 'left')])
        self.assertTrue(self.backend.check_clickable)
        count = len(self.backend.events)
        guard.send_key_up('manual-untracked-key')
        guard.mouse_up(key='right')
        guard.release_all()
        self.assertEqual(len(self.backend.events), count)

    def test_unowned_prepare_and_on_run_have_no_focus_effect(self):
        install_input_guard(self.task, self.session)
        self.executor.interaction.on_run()
        self.executor._prepare_task_for_run(False)
        self.assertEqual(self.backend.events, [])
        self.own_input()
        with patch('src.overworld.input_access.require_game_input_access'):
            self.executor.interaction.on_run()
        self.assertEqual(self.backend.events, [('focus', None)])

    def test_unfocused_prerun_fails_before_focus_or_first_capture(self):
        install_input_guard(self.task, self.session)
        self.backend.foreground = False
        with self.assertRaisesRegex(SessionStopped, 'focus.*manually'):
            self.executor._prepare_task_for_run(False)
        self.assertEqual(self.backend.events, [])
        self.capture_frame.assert_not_called()
        self.assertEqual(self.capture._jh_frame_sequence, 1)
        self.assertIsNone(self.session.owner)

    def test_foreground_loss_mid_swipe_releases_drag_and_stops_movement(self):
        guard = GuardedInteraction(self.backend, self.session, lambda: None)
        self.own_input()
        self.backend.on_move = lambda: setattr(self.backend, 'foreground', False)
        with patch('src.automation.input_guard.time.sleep'):
            with self.assertRaisesRegex(SessionStopped, 'foreground lost'):
                guard.swipe(10, 10, 100, 100, 100)
        self.assertEqual(self.session.state, 'TAKEOVER')
        self.assertEqual([name for name, _ in self.backend.events],
                         ['mouse_down', 'move', 'mouse_up'])
        self.assertEqual(self.backend.events[-1], ('mouse_up', 'left'))
        self.assertFalse(guard.buttons)
        self.assertTrue(self.backend.check_clickable)

    def test_scroll_refuses_wrong_foreground_and_releases_prior_held_key(self):
        guard = GuardedInteraction(self.backend, self.session, lambda: None)
        self.own_input()
        guard.send_key_down('w')
        self.backend.foreground = False
        with self.assertRaisesRegex(SessionStopped, 'foreground lost'):
            guard.scroll(10, 10, -1)
        self.assertEqual(self.backend.events, [('key_down', 'w'), ('key_up', 'w')])
        self.assertEqual(self.session.state, 'TAKEOVER')

    def test_cleanup_failure_in_one_adapter_does_not_strand_another_adapter(self):
        first = GuardedInteraction(self.backend, self.session, lambda: None)
        other_backend = FakeFocusBackend(self.capture)
        second = GuardedInteraction(other_backend, self.session, lambda: None)
        self.own_input()
        first.send_key_down('w')
        second.send_key_down('a')
        self.backend.send_key_up = Mock(side_effect=OSError('first backend unavailable'))
        with self.assertRaisesRegex(SessionStopped, 'adapters failed cleanup'):
            self.session.pause('stop every adapter')
        self.assertEqual(self.session.state, 'PAUSED')
        self.assertEqual(other_backend.events, [('key_down', 'a'), ('key_up', 'a')])
        self.assertFalse(second.keys)
        self.assertEqual(first.keys, {'w'})  # retained for a visible retry/error

    def test_frame_validation_checks_window_age_and_sequence_before_safe_unlock(self):
        self.assertEqual(validate_observation(self.task), 1)
        for change in ('stale', 'wrong_window', 'same_frame'):
            with self.subTest(change=change):
                self.capture._jh_frame_timestamp = time.monotonic()
                self.capture.hwnd_window = self.window
                previous = None
                if change == 'stale':
                    self.capture._jh_frame_timestamp -= 3
                elif change == 'wrong_window':
                    self.capture.hwnd_window = SimpleNamespace(hwnd=-1)
                else:
                    previous = 1
                with self.assertRaises(SessionStopped):
                    validate_observation(self.task, previous_sequence=previous)

    def test_session_control_failed_capture_cannot_unlock_story_or_old_skip_setting(self):
        from src.task.AutomationSessionTask import AutomationSessionTask
        task = AutomationSessionTask.__new__(AutomationSessionTask)
        task._executor = self.executor
        task.config = {'Operation': 'NORMAL'}
        task.info_set = Mock()
        task.in_team_and_world = Mock(return_value=True)
        task.next_frame = Mock(return_value=None)
        self.session.enter_story_watch()
        self.session.cancel('previous story cancellation')
        with self.assertRaises(SessionStopped):
            task.run()
        self.assertTrue(self.session.story_locked)
        self.assertFalse(self.session.skip_approved)
        self.assertFalse(self.session.allow_story_skip())
        task.in_team_and_world.assert_not_called()

        task.next_frame.return_value = object()
        with patch('src.automation.input_guard.validate_observation',
                   side_effect=SessionStopped('wrong capture window')):
            with self.assertRaises(SessionStopped):
                task.run()
        self.assertTrue(self.session.story_locked)
        self.assertFalse(self.session.allow_story_skip())
        task.in_team_and_world.assert_not_called()


if __name__ == '__main__':
    unittest.main()
