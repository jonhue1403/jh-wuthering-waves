"""Offline behavior tests; no test data here qualifies a live quest segment."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

from src.automation.session import Session, SessionStopped, get_session
from src.automation.story import (StoryObservation, StoryPaused, StoryProfile,
                                  StoryScreen, StorySegmentRunner, StoryStep)


class TestStoryWatch(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.session = Session(clock=lambda: self.now)
        self.steps = tuple(StoryStep(screen, 'Reach courtyard', f'pre_{screen.value}',
                                    f'post_{screen.value}', timeout=3,
                                    movement=(('w', .1),) if screen == StoryScreen.TRAVEL else ())
                           for screen in (StoryScreen.TRAVEL, StoryScreen.DIALOGUE, StoryScreen.COMBAT))
        self.profile = StoryProfile('offline-test', 'test-version', self.steps,
                                    (('mock-only-not-live-evidence', 'mock'),), (.1, .1, .5, .4),
                                    10, True)
        self.travel, self.combat = Mock(), Mock()
        self.autoplay, self.choose = Mock(), Mock()

    def observation(self, step, frame='before', screen=None, marker=None):
        return StoryObservation(screen or step.screen, step.objective, 'test-version', self.now,
                                frame, True, marker or step.marker)

    def runner(self, observations):
        observe = Mock(side_effect=observations)
        def wait(seconds):
            self.now += seconds
        return StorySegmentRunner(self.profile, self.session, observe,
                                  lambda step, obs: obs.marker == step.post_marker,
                                  self.travel, self.combat, self.autoplay, self.choose,
                                  wait, clock=lambda: self.now)

    def complete_observations(self):
        observations = []
        for index, step in enumerate(self.steps):
            observations.extend([self.observation(step, f'before{index}'),
                                 self.observation(step, f'after{index}', StoryScreen.COMPLETE, step.post_marker)])
        return observations

    def test_bounded_segment_hands_combat_to_engine_and_passively_watches(self):
        runner = self.runner(self.complete_observations())
        self.assertTrue(runner.run())
        self.travel.assert_called_once()
        self.combat.assert_called_once()
        self.autoplay.assert_not_called()
        self.choose.assert_not_called()
        self.assertTrue(self.session.story_locked)
        self.assertFalse(self.session.allow_story_skip())

    def test_cancel_during_dialogue_preserves_lock_and_cancelled_state(self):
        observations = self.complete_observations()
        def observe(step):
            if step.screen == StoryScreen.DIALOGUE:
                self.session.cancel('operator cancelled during dialogue')
            return observations.pop(0)
        runner = self.runner([])
        runner.observe = observe
        with self.assertRaises(SessionStopped):
            runner.run()
        self.assertEqual(self.session.state, 'CANCELLED')
        self.assertFalse(self.session.allow_story_skip())
        self.combat.assert_not_called()

    def test_restart_keeps_old_enabled_skip_preference_ineffective(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'session.json'
            session = Session(path)
            session.enter_story_watch()
            session.cancel('dialogue')
            restored = Session(path)
            self.assertTrue(restored.story_locked)
            self.assertFalse(restored.allow_story_skip())
            with self.assertRaises(SessionStopped):
                restored.select_mode('NORMAL', safe_state=False)
            restored.select_mode('NORMAL', safe_state=True)
            self.assertTrue(restored.allow_story_skip())

    def test_fresh_or_legacy_session_requires_explicit_skip_opt_in(self):
        self.assertFalse(self.session.allow_story_skip())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy-session.json'
            path.write_text(json.dumps({'mode': 'NORMAL', 'story_locked': False}), encoding='utf-8')
            restored = Session(path)
            restored.resume(safe_state=True)
            self.assertFalse(restored.allow_story_skip())
            restored.select_mode('NORMAL', safe_state=True)
            self.assertTrue(restored.allow_story_skip())

    def test_stale_frame_or_wrong_window_never_moves(self):
        first = self.observation(self.steps[0])
        for observation in (replace(first, captured_at=1), replace(first, captured_at=11),
                            replace(first, correct_window=False), replace(first, frame_id='')):
            with self.subTest(observation=observation):
                self.session = Session(clock=lambda: self.now)
                with self.assertRaises(StoryPaused):
                    self.runner([observation]).run()
                self.travel.assert_not_called()

    def test_version_or_objective_mismatch_never_moves(self):
        before = self.observation(self.steps[0])
        for observation in (replace(before, game_version='other'), replace(before, objective='Different route')):
            with self.subTest(observation=observation):
                self.session = Session(clock=lambda: self.now)
                with self.assertRaises(StoryPaused):
                    self.runner([observation]).run()
                self.travel.assert_not_called()

    def test_postcondition_needs_another_frame(self):
        step = self.steps[0]
        observations = [self.observation(step, 'same'),
                        self.observation(step, 'same', StoryScreen.COMPLETE, step.post_marker)]
        with self.assertRaises(StoryPaused):
            self.runner(observations).run()
        self.travel.assert_called_once()
        self.combat.assert_not_called()

    def test_unknown_puzzle_qte_pause_with_last_objective(self):
        for screen in (StoryScreen.UNKNOWN, StoryScreen.PUZZLE, StoryScreen.QTE):
            with self.subTest(screen=screen):
                self.session = Session(clock=lambda: self.now)
                with self.assertRaises(StoryPaused):
                    self.runner([self.observation(self.steps[0], screen=screen)]).run()
                self.assertIn('Reach courtyard', self.session.reason)
                self.travel.assert_not_called()

    def test_unapproved_choice_during_passive_playback_never_clicks(self):
        observations = self.complete_observations()[:3]
        observations.append(self.observation(self.steps[1], 'choice', StoryScreen.CHOICE))
        with self.assertRaises(StoryPaused):
            self.runner(observations).run()
        self.choose.assert_not_called()
        self.autoplay.assert_not_called()
        self.combat.assert_not_called()

    def test_reviewed_choice_requires_explicit_policy(self):
        choice = StoryStep(StoryScreen.CHOICE, 'Reach courtyard', 'choice', 'choice_done',
                           neutral_choice='reviewed_neutral')
        self.profile = replace(self.profile, steps=(choice,) + self.steps)
        with self.assertRaises(StoryPaused):
            self.runner([self.observation(choice)]).run(False)
        self.choose.assert_not_called()

    def test_reviewed_neutral_choice_runs_once_with_explicit_policy(self):
        choice = StoryStep(StoryScreen.CHOICE, 'Reach courtyard', 'choice', 'choice_done',
                           neutral_choice='reviewed_neutral')
        self.profile = replace(self.profile, steps=(choice,) + self.steps)
        observations = [self.observation(choice),
                        self.observation(choice, 'chosen', StoryScreen.COMPLETE, 'choice_done')]
        observations.extend(self.complete_observations())
        self.assertTrue(self.runner(observations).run(True))
        self.choose.assert_called_once_with('reviewed_neutral')

    def test_dialogue_timeout_does_not_replay_actions(self):
        step = self.steps[0]
        runner = self.runner([])
        sequence = 0
        def observe(_step):
            nonlocal sequence
            sequence += 1
            return self.observation(step, str(sequence))
        runner.observe = observe
        with self.assertRaises(StoryPaused):
            runner.run()
        self.travel.assert_called_once()
        self.assertGreaterEqual(self.now, 13)

    def test_exception_preserves_no_skip_lock(self):
        self.travel.side_effect = RuntimeError('lost localization')
        with self.assertRaises(RuntimeError):
            self.runner([self.observation(self.steps[0])]).run()
        self.assertFalse(self.session.allow_story_skip())
        self.assertIn('Reach courtyard', self.session.reason)

    def test_profile_load_rejects_missing_or_changed_real_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.json'
            screenshot = Path(folder) / 'capture.png'
            # Deliberately simulated bytes: a loader hash test, no live evidence claim.
            screenshot.write_bytes(b'simulated-hash-test')
            data = {'qualified': True, 'reviewed_by': 'offline-test', 'profile_id': 'test',
                    'game_version': 'test-version', 'objective_box': [.1, .1, .5, .4],
                    'evidence': [{'path': 'capture.png', 'sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()}],
                    'steps': [dict(screen=s.screen.value, objective=s.objective, marker=s.marker,
                                   post_marker=s.post_marker, timeout=3, movement=list(s.movement)) for s in self.steps]}
            path.write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(StoryProfile.load(path).game_version, 'test-version')
            screenshot.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                StoryProfile.load(path)
            data['evidence'] = []
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no observed screenshot'):
                StoryProfile.load(path)


class TestStoryTriggerGuards(unittest.TestCase):
    def test_no_profile_still_locks_story_and_pauses_without_input(self):
        from src.task.StoryWatchTask import StoryWatchTask
        task = StoryWatchTask.__new__(StoryWatchTask)
        task.config = {'Story Profile': ''}
        task.click, task.send_key = Mock(), Mock()
        self.assertFalse(task.run())
        session = get_session(task)
        self.assertTrue(session.story_locked)
        self.assertEqual(session.state, 'PAUSED')
        self.assertIn('LIVE_VERIFICATION_PENDING', session.reason)
        task.click.assert_not_called()
        task.send_key.assert_not_called()

    def test_recording_status_output_limits_and_growth_are_required(self):
        from src.task.StoryWatchTask import StoryWatchTask
        task = StoryWatchTask.__new__(StoryWatchTask)
        task.config = {'Recording Required': True}
        task._story_recording = None
        task._executor = Mock()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'existing-recording.mkv'
            output.write_bytes(b'initial')
            status = dict(active=True, output_path=str(output), remaining_seconds=120,
                          remaining_bytes=1024, max_seconds=600, max_bytes=4096,
                          observed_at=time.monotonic(), limits_enforced=True)
            task._executor.recording_status.return_value = status
            task._check_recording()
            with self.assertRaisesRegex(StoryPaused, 'continuity'):
                task._check_recording(verify_growth=True)
            output.write_bytes(b'initial plus recorded output')
            task._check_recording(verify_growth=True)
            for invalid in (dict(status, active=False), dict(status, remaining_seconds=0),
                            dict(status, remaining_bytes=0), dict(status, output_path=str(output) + '.missing'),
                            dict(status, observed_at=time.monotonic() - 10), dict(status, limits_enforced=False),
                            dict(status, max_bytes=1), dict(status, max_seconds=1)):
                with self.subTest(invalid=invalid):
                    task._executor.recording_status.return_value = invalid
                    with self.assertRaises(StoryPaused):
                        task._check_recording()

    def test_inherited_narrative_and_pickup_entry_points_are_suppressed(self):
        from src.task.SkipDialogTask import AutoDialogTask
        from src.task.AutoPickTask import AutoPickTask
        from src.task.SkipBaseTask import SkipBaseTask
        from src.task.AutoCombatTask import AutoCombatTask
        for cls, method in ((AutoDialogTask, 'run'), (AutoDialogTask, 'skip_message'),
                            (SkipBaseTask, 'skip_confirm'), (SkipBaseTask, 'check_skip'),
                            (SkipBaseTask, 'try_click_skip'), (SkipBaseTask, 'find_skip'),
                            (AutoPickTask, 'run'), (AutoPickTask, 'send_fs'),
                            (AutoCombatTask, 'run'), (AutoCombatTask, 'run_auto_combat')):
            with self.subTest(cls=cls.__name__, method=method):
                task = cls.__new__(cls)
                task.find_one = Mock()
                task.click = Mock()
                task.send_key = Mock()
                session = get_session(task)
                session.enter_story_watch()
                session.cancel('during dialogue; persisted skip setting was enabled')
                self.assertFalse(getattr(task, method)())
                task.find_one.assert_not_called()
                task.click.assert_not_called()
                task.send_key.assert_not_called()

    def test_new_skip_trigger_defaults_disabled(self):
        from src.task.SkipDialogTask import AutoDialogTask
        task = AutoDialogTask(Mock(), None)
        self.assertFalse(task.default_config['_enabled'])


if __name__ == '__main__':
    unittest.main()
