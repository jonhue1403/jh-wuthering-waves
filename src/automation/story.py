"""Deterministic, bounded Story Watch segment contract.

No quest is qualified merely by loading this module. Profiles require real,
reviewed screenshot evidence; unknown screens never generate input.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import time


class StoryScreen(str, Enum):
    TRAVEL = "TRAVEL"
    DIALOGUE = "DIALOGUE"
    CUTSCENE = "CUTSCENE"
    CHOICE = "CHOICE"
    COMBAT = "COMBAT"
    COMPLETE = "COMPLETE"
    UNKNOWN = "UNKNOWN"
    PUZZLE = "PUZZLE"
    QTE = "QTE"


@dataclass(frozen=True)
class StoryObservation:
    screen: StoryScreen
    objective: str
    game_version: str
    captured_at: float
    frame_id: str
    correct_window: bool
    marker: str = ""


@dataclass(frozen=True)
class StoryStep:
    screen: StoryScreen
    objective: str
    marker: str
    post_marker: str
    timeout: float = 60.0
    # Each movement was calibrated on the profile's segment. Never infer routes.
    movement: tuple = ()
    neutral_choice: str = ""
    autoplay_marker: str = ""


@dataclass(frozen=True)
class StoryProfile:
    profile_id: str
    game_version: str
    steps: tuple
    evidence: tuple
    objective_box: tuple
    max_seconds: float = 600.0
    qualified: bool = False

    @classmethod
    def load(cls, path):
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("qualified") or not data.get("reviewed_by"):
            raise ValueError("Story segment requires reviewed live qualification")
        evidence = []
        for item in data.get("evidence", []):
            screenshot = (path.parent / item["path"]).resolve()
            if screenshot.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                raise ValueError("Story evidence must be a captured screenshot")
            digest = hashlib.sha256(screenshot.read_bytes()).hexdigest()
            if digest != item["sha256"]:
                raise ValueError("Story evidence hash mismatch")
            evidence.append((str(screenshot), digest))
        if not evidence:
            raise ValueError("Story segment has no observed screenshot evidence")
        steps = tuple(StoryStep(
            screen=StoryScreen(item["screen"]), objective=item["objective"],
            marker=item["marker"], post_marker=item["post_marker"],
            timeout=float(item.get("timeout", 60)),
            movement=tuple((str(k), float(t)) for k, t in item.get("movement", [])),
            neutral_choice=item.get("neutral_choice", ""),
            autoplay_marker=item.get("autoplay_marker", ""),
        ) for item in data.get("steps", []))
        profile = cls(str(data["profile_id"]), str(data["game_version"]), steps,
                      tuple(evidence), tuple(data["objective_box"]),
                      float(data.get("max_seconds", 600)), True)
        profile.validate()
        return profile

    def validate(self):
        if not self.qualified or not self.evidence or not self.profile_id or not self.game_version:
            raise ValueError("Unqualified story profile")
        if not 1 <= self.max_seconds <= 1800 or not 1 <= len(self.steps) <= 20:
            raise ValueError("Story segment exceeds execution bounds")
        if len(self.objective_box) != 4 or not all(0 <= n <= 1 for n in self.objective_box):
            raise ValueError("Story objective OCR region must be normalized")
        if not (self.objective_box[0] < self.objective_box[2]
                and self.objective_box[1] < self.objective_box[3]):
            raise ValueError("Story objective OCR region is empty")
        screens = {step.screen for step in self.steps}
        if not {StoryScreen.TRAVEL, StoryScreen.DIALOGUE, StoryScreen.COMBAT} <= screens:
            raise ValueError("A qualified segment must include travel, dialogue and combat")
        for step in self.steps:
            if not step.objective or not step.marker or not step.post_marker or not 0 < step.timeout <= 600:
                raise ValueError("Story step needs observed pre/postconditions and a bound")
            if step.marker == step.post_marker:
                raise ValueError("Story postcondition must differ from the precondition")
            if step.screen in (StoryScreen.UNKNOWN, StoryScreen.PUZZLE, StoryScreen.QTE):
                raise ValueError("Unsupported story screen cannot be scripted")
            if len(step.movement) > 20 or any(k not in ("w", "a", "s", "d") or not 0 < t <= .25
                                              for k, t in step.movement):
                raise ValueError("Story travel must use short calibrated surface inputs")
            if step.movement and step.screen != StoryScreen.TRAVEL:
                raise ValueError("Movement belongs only to a travel step")
            if step.screen == StoryScreen.TRAVEL and not step.movement:
                raise ValueError("Travel requires an observed calibrated movement segment")
            if step.neutral_choice and step.screen != StoryScreen.CHOICE:
                raise ValueError("Choice policy belongs only to a choice step")
            if step.autoplay_marker and step.screen != StoryScreen.DIALOGUE:
                raise ValueError("Native autoplay belongs only to dialogue")


class StoryPaused(RuntimeError):
    pass


class StorySegmentRunner:
    """Runs inside the existing task executor, with injected ordinary UI actions."""

    def __init__(self, profile, session, observe, postcondition, travel, combat,
                 native_autoplay, choose, wait, clock=time.monotonic):
        profile.validate()
        self.profile, self.session = profile, session
        self.observe, self.postcondition = observe, postcondition
        self.travel, self.combat = travel, combat
        self.native_autoplay, self.choose = native_autoplay, choose
        self.wait, self.clock = wait, clock
        self.last_objective = ""

    def pause(self, reason):
        self.session.pause(f"{reason}; last objective: {self.last_objective or 'unrecognized'}")
        raise StoryPaused(reason)

    def check(self, observation):
        self.session.check()
        self.last_objective = observation.objective or self.last_objective
        age = self.clock() - observation.captured_at
        if not observation.correct_window or not 0 <= age <= 2 or not observation.frame_id:
            self.pause("Fresh game frame unavailable")
        if observation.game_version != self.profile.game_version:
            self.pause("Story profile game version mismatch")
        if observation.screen in (StoryScreen.UNKNOWN, StoryScreen.PUZZLE, StoryScreen.QTE):
            self.pause(f"Unsupported screen {observation.screen.value}")

    def run(self, allow_neutral_choice=False):
        self.session.check()
        if not self.session.story_locked:
            self.session.enter_story_watch()
        started = self.clock()
        try:
            for step in self.profile.steps:
                self.session.check()
                before = self.observe(step)
                self.check(before)
                if (before.screen, before.objective, before.marker) != (step.screen, step.objective, step.marker):
                    self.pause("Observed quest state does not match the reviewed segment")
                if step.screen == StoryScreen.CHOICE and not (allow_neutral_choice and step.neutral_choice):
                    self.pause("Unapproved dialogue choice")
                deadline = min(started + self.profile.max_seconds, self.clock() + step.timeout)
                if self.clock() >= deadline:
                    self.pause("Story session time limit reached")
                self.session.check()
                # Every action is sent once. Failed postconditions never replay input.
                if step.screen == StoryScreen.TRAVEL:
                    self.travel(step, deadline)
                elif step.screen == StoryScreen.COMBAT:
                    self.combat(deadline)
                elif step.screen == StoryScreen.CHOICE:
                    self.choose(step.neutral_choice)
                elif step.screen == StoryScreen.DIALOGUE and step.autoplay_marker:
                    self.native_autoplay(step.autoplay_marker)
                while True:
                    if self.clock() >= deadline:
                        self.pause("Story step timed out")
                    self.session.check()
                    observed = self.observe(step)
                    self.check(observed)
                    if observed.frame_id == before.frame_id:
                        self.pause("Story postcondition frame was not refreshed")
                    if self.postcondition(step, observed):
                        break
                    if observed.screen == StoryScreen.CHOICE:
                        self.pause("Dialogue choice requires an explicit approved policy")
                    self.wait(.2)
            return True
        except BaseException:
            # No preference restoration: persistent no-skip remains on every exit.
            if self.session.state == 'READY':
                self.session.pause(f"Story interrupted; last objective: {self.last_objective or 'unrecognized'}")
            raise
