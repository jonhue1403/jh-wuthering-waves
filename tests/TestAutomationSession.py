import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.automation.session import Session, SessionStopped, InputConflict
from src.automation.input_guard import GuardedInteraction, install_input_guard


class TestAutomationSession(unittest.TestCase):
    def test_explicit_pause_remains_paused_after_activity_unwinds(self):
        session = Session()
        with self.assertRaises(SessionStopped):
            with session.activity('story'):
                session.pause('Unrecognized objective')
        self.assertEqual('PAUSED', session.state)
        self.assertEqual('Unrecognized objective', session.reason)

    def test_story_lock_survives_cancel_exception_takeover_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            session = Session(path)
            self.assertFalse(session.allow_story_skip())
            session.select_mode('NORMAL', safe_state=True)
            self.assertTrue(session.allow_story_skip())
            session.enter_story_watch()
            for stop in (session.pause, session.cancel, session.takeover):
                stop('dialogue interrupted')
                restored = Session(path)
                self.assertTrue(restored.story_locked)
                self.assertFalse(restored.allow_story_skip())
            with self.assertRaises(SessionStopped):
                session.select_mode('NORMAL')
            self.assertTrue(session.story_locked)

    def test_conflicting_thread_cannot_take_input(self):
        session = Session()
        errors = []
        def conflicting():
            try:
                with session.activity('second'):
                    pass
            except BaseException as error:
                errors.append(error)
        with session.activity('first'):
            thread = threading.Thread(target=conflicting)
            thread.start()
            thread.join()
            self.assertEqual('first', session.owner)
        self.assertIsInstance(errors[0], InputConflict)

    def test_cancel_invalidates_queued_actions_even_after_explicit_resume(self):
        session = Session()
        action = Mock()
        pending = session.queued_action(action)
        session.cancel()
        session.resume(safe_state=True)
        with self.assertRaises(SessionStopped):
            pending()
        action.assert_not_called()

    def test_expired_activity_releases_held_keys_and_propagates(self):
        now = [0]
        session = Session(clock=lambda: now[0])
        backend = Mock()
        guard = GuardedInteraction(backend, session, lambda: None)
        with self.assertRaises(SessionStopped):
            with session.activity('combat', seconds=1):
                guard.send_key_down('w')
                guard.mouse_down(key='right')
                now[0] = 2
                guard.click(1, 1)
        backend.send_key_up.assert_called_once_with('w')
        backend.mouse_up.assert_called_once_with(key='right')
        backend.click.assert_not_called()
        self.assertIsNone(session.owner)

    def test_exception_cleanup_and_nested_existing_task_delegation(self):
        session = Session()
        backend = Mock()
        guard = GuardedInteraction(backend, session, lambda: None)
        with self.assertRaisesRegex(ValueError, 'failed'):
            with session.activity('daily'):
                with session.activity('forgery'):
                    guard.send_key_down('e')
                    raise ValueError('failed')
        backend.send_key_up.assert_called_once_with('e')
        self.assertEqual('CANCELLED', session.state)

    def test_unknown_or_stale_frame_prevents_input(self):
        session = Session()
        backend = Mock()
        def invalid():
            raise SessionStopped('stale frame')
        guard = GuardedInteraction(backend, session, invalid)
        with self.assertRaisesRegex(SessionStopped, 'stale frame'):
            with session.activity('claim'):
                guard.click(1, 1)
        backend.click.assert_not_called()

    def test_input_requires_an_activity_even_without_contending_owner(self):
        backend = Mock()
        guard = GuardedInteraction(backend, Session(), lambda: None)
        with self.assertRaisesRegex(SessionStopped, 'No activity'):
            guard.click(1, 1)
        backend.click.assert_not_called()

    def test_capture_timeout_does_not_renew_frame_age(self):
        capture = SimpleNamespace(_jh_frame_timestamp=-100)
        backend = SimpleNamespace(capture=capture)
        executor = SimpleNamespace(interaction=backend, next_frame=lambda: None, _last_frame_time=0)
        task = SimpleNamespace(executor=executor)
        install_input_guard(task, Session())
        self.assertIsNone(executor.next_frame())
        self.assertEqual(-100, capture._jh_frame_timestamp)


if __name__ == '__main__':
    unittest.main()
