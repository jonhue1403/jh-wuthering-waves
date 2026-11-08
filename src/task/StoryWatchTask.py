"""Story Watch task; operates only a separately observed and reviewed segment."""
import time
from pathlib import Path

from src.automation.session import get_session
from src.automation.story import (StoryObservation, StoryPaused, StoryProfile,
                                  StoryScreen, StorySegmentRunner)
from src.task.BaseCombatTask import BaseCombatTask
from src.task.task_icons import task_icon


class StoryWatchTask(BaseCombatTask):
    owns_switch_healer_config = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Story Watch"
        self.description = "Watch dialogue without skipping; pause at unknown objectives or choices. 剧情观看，不跳过对话。"
        self.icon = task_icon('skip-dialog')
        self.default_config.update({
            "Story Profile": "",
            "Observed Game Version": "",
            "Allow Reviewed Neutral Choice": False,
            "Recording Required": False,
            "Switch to Healer before and after Combat": True,
        })
        self.config_description.update({
            "Story Profile": "Reviewed segment JSON with real screenshot hashes. 已审核剧情片段。",
            "Observed Game Version": "Version read from the running game during qualification; never infer from the PC date.",
            "Allow Reviewed Neutral Choice": "Only the exact neutral choice recorded in a reviewed profile may be selected.",
            "Recording Required": "Require an existing recorder's verified status, output and enforced limits; never starts/stops recording.",
        })
        self._story_objective = ""
        self._story_deadline = None
        self._story_profile = None
        self._story_recording = None

    def run(self):
        session = get_session(self)
        self._story_recording = None
        self._story_objective = ""
        # Lock before parsing profile/config: even invalid config must not restore
        # a persisted skip trigger, or allow background pickup/combat.
        session.enter_story_watch()
        try:
            path = self.config.get("Story Profile", "").strip()
            if not path:
                session.pause("Story Watch active; LIVE_VERIFICATION_PENDING: select an observed, reviewed quest segment")
                return False
            self._story_profile = StoryProfile.load(path)
            version = self.config.get("Observed Game Version", "").strip()
            if version != self._story_profile.game_version:
                raise StoryPaused("Observe the running game version; it must match the reviewed Story Profile")
            self._check_recording()
            self._story_deadline = time.monotonic() + self._story_profile.max_seconds
            runner = StorySegmentRunner(
                self._story_profile, session, self._observe_story,
                lambda step, obs: obs.marker == step.post_marker,
                self._travel_story, self._combat_story,
                self._native_autoplay, self._choose_story, self.sleep,
            )
            result = runner.run(self.config.get("Allow Reviewed Neutral Choice", False))
            self._check_recording(verify_growth=True)
            self.info_set("Story Watch", "Reviewed segment postconditions observed; no-skip remains active")
            return result
        except BaseException as exc:
            if session.state == 'READY':
                session.pause(f"Story Watch paused: {exc}")
            raise
        finally:
            self._story_deadline = None

    def _observe_story(self, step):
        self.next_frame()
        self._check_recording()
        profile = self._story_profile
        objective = " ".join(box.name.strip() for box in self.ocr(*profile.objective_box))
        self._story_objective = objective or self._story_objective
        # This region and all marker names must have been calibrated together in
        # the reviewed segment. Unknown choices cannot produce generic inputs.
        matches = []
        if self.find_one(step.marker, threshold=.9):
            matches.append((step.screen, step.marker))
        if self.find_one(step.post_marker, threshold=.9):
            matches.append((StoryScreen.COMPLETE, step.post_marker))
        # Detect configured choice controls ahead of ordinary dialogue. No choice
        # control can be clicked through the passive playback path.
        for candidate in profile.steps:
            if candidate.screen == StoryScreen.CHOICE and self.find_one(candidate.marker, threshold=.9):
                matches = [(StoryScreen.CHOICE, candidate.marker)]
                break
        matches = list(dict.fromkeys(matches))
        if len(matches) != 1:
            screen, marker = StoryScreen.UNKNOWN, ""
        else:
            screen, marker = matches[0]
        self.info_set("Last recognized objective", self._story_objective or "unrecognized")
        capture = self.executor.interaction.capture
        timestamp = getattr(capture, '_jh_frame_timestamp', None)
        frame_id = getattr(capture, '_jh_frame_sequence', timestamp)
        window = self.hwnd
        capture_window = getattr(capture, 'hwnd_window', None)
        correct_window = bool(window and window.exists and window.visible and capture_window
                              and capture_window.hwnd == window.hwnd)
        return StoryObservation(screen, self._story_objective, self.config.get("Observed Game Version", ""),
                                timestamp if timestamp is not None else float('-inf'),
                                str(frame_id) if frame_id is not None else '', correct_window, marker)

    def _travel_story(self, step, deadline):
        for key, duration in step.movement:
            if time.monotonic() + duration >= deadline:
                raise StoryPaused("Calibrated travel exceeds story time limit")
            # The shared input owner performs fresh-frame/window validation and
            # cancellation checks. Never replay a movement on postcondition failure.
            self.send_key(key, down_time=duration)
            self.next_frame()

    def _combat_story(self, deadline):
        previous = self._story_deadline
        self._story_deadline = min(previous, deadline)
        try:
            if not self.in_team_and_world() or not self.in_combat():
                raise StoryPaused("Reviewed story combat precondition is absent")
            self.combat_once(wait_combat_time=1, raise_if_not_found=True)
        finally:
            self._story_deadline = previous

    def _native_autoplay(self, marker):
        # Existing btn_auto_play_dialog alone does not prove Semi-Auto is safe.
        # Only a qualified, profile-specific marker can request a single click.
        button = self.find_one(marker, threshold=.95)
        if button is None:
            raise StoryPaused("Qualified native Semi-Auto control not observed")
        self.click(button)

    def _choose_story(self, marker):
        button = self.find_one(marker, threshold=.95)
        if button is None:
            raise StoryPaused("Reviewed neutral choice not observed")
        self.click(button)

    def sleep_check(self):
        get_session(self).check()
        if self._story_deadline is not None and time.monotonic() >= self._story_deadline:
            raise StoryPaused("Story execution time limit reached")
        self._check_recording()
        super().sleep_check()

    def _check_recording(self, verify_growth=False):
        if not self.config.get("Recording Required", False):
            return
        provider = getattr(self.executor, "recording_status", None)
        if not callable(provider):
            raise StoryPaused("Existing recording status/limits are unavailable")
        status = provider()
        if not isinstance(status, dict) or not status.get("active"):
            raise StoryPaused("Configured recording is not verified active")
        observed_at = status.get('observed_at')
        if (not isinstance(observed_at, (int, float))
                or not 0 <= time.monotonic() - observed_at <= 2
                or status.get('limits_enforced') is not True):
            raise StoryPaused("Fresh recorder status and enforced time/storage limits are required")
        output = Path(status.get("output_path", ""))
        if not output.is_file() or status.get("remaining_seconds", 0) <= 0 or status.get("remaining_bytes", 0) <= 0:
            raise StoryPaused("Recording output or actual time/storage allowance is unavailable")
        current = (str(output.resolve()), output.stat().st_size)
        if (not 0 < status['remaining_seconds'] <= status.get('max_seconds', 0)
                or not 0 < status['remaining_bytes'] <= status.get('max_bytes', 0) - current[1]):
            raise StoryPaused("Recording time/storage allowance conflicts with its configured limits")
        if verify_growth and (self._story_recording is None or current[0] != self._story_recording[0]
                              or current[1] <= self._story_recording[1]):
            raise StoryPaused("Recording continuity/output growth is unverified")
        if self._story_recording is None:
            self._story_recording = current
