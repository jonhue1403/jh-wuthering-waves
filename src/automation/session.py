"""Shared safety state for the existing OK executor, not a second executor.

The story lock is durable. Input leases are exclusive, bounded, and cancelled by
an epoch change; a stale queued callback can never revive an old lease.
"""
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import threading
import time


class SessionStopped(RuntimeError):
    pass


class InputConflict(SessionStopped):
    pass


class Session:
    def __init__(self, path=None, *, clock=time.monotonic):
        self.path = Path(path) if path else None
        self.clock = clock
        self.mode = 'NORMAL'
        self.story_locked = False
        self.skip_approved = False
        self.state = 'READY'
        self.reason = ''
        self.resource_profile = {}
        self.owner = None
        self.thread = None
        self.deadline = 0
        self.epoch = 0
        self.read_only_depth = 0
        self._lock = threading.RLock()
        self._release = []
        self._process_lock = None
        self._load()

    def _load(self):
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.mode = data['mode']
            self.story_locked = bool(data['story_locked'])
            self.skip_approved = bool(data.get('skip_approved', False))
            self.resource_profile = data.get('resource_profile', {})
            # Restart never resumes actions or silently removes a story guard.
            self.state = 'PAUSED'
            self.reason = 'Restart: inspect fresh game state before explicit resume'

    def _save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            with temporary.open('w', encoding='utf-8') as stream:
                json.dump({'mode': self.mode, 'story_locked': self.story_locked,
                           'skip_approved': self.skip_approved,
                           'state': self.state, 'reason': self.reason,
                           'resource_profile': self.resource_profile}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)

    def allow_story_skip(self):
        return self.skip_approved and not self.story_locked and self.mode == 'NORMAL' and self.state == 'READY'

    def enter_story_watch(self):
        with self._lock:
            self.story_locked = True
            self.skip_approved = False
            self.mode = 'STORY_WATCH'
            self.state = 'READY'
            self._save()  # persist BEFORE any game interaction

    def select_mode(self, mode, safe_state=False):
        if mode not in ('NORMAL', 'STORY_WATCH'):
            raise ValueError('Unknown session mode')
        if mode == 'STORY_WATCH':
            return self.enter_story_watch()
        if not safe_state:
            raise SessionStopped('Fresh safe world screen required to enable NORMAL mode')
        with self._lock:
            self.mode = mode
            self.story_locked = False
            self.skip_approved = True
            self.state = 'READY'
            self.reason = ''
            self.epoch += 1
            self._save()

    def resume(self, safe_state=False):
        if not safe_state:
            raise SessionStopped('Fresh safe state required to resume')
        self.state = 'READY'
        self.reason = ''
        self._save()

    def _stop(self, state, reason):
        with self._lock:
            self.state = state
            self.reason = str(reason)
            self.epoch += 1
            self._save()
        # Never hold the session mutex while acquiring an input adapter mutex.
        # Delivery checks acquire them in the opposite order.
        self.release_all()

    def release_all(self):
        failures = []
        for release in self._release:
            try:
                release()
            except BaseException as error:
                failures.append(error)
        if failures:
            if self.state == 'READY':
                self.state = 'CANCELLED'
            self.reason = 'Held-input cleanup incomplete; inspect before explicit resume'
            self.epoch += 1
            self._save()
            raise SessionStopped('One or more input adapters failed cleanup') from failures[0]

    def pause(self, reason='Paused'):
        self._stop('PAUSED', reason)

    def cancel(self, reason='Cancelled'):
        self._stop('CANCELLED', reason)

    def takeover(self, reason='Manual takeover'):
        self._stop('TAKEOVER', reason)

    def check(self, epoch=None):
        if self.state != 'READY':
            raise SessionStopped(self.reason or self.state)
        if epoch is not None and epoch != self.epoch:
            raise SessionStopped('Queued action cancelled')
        if self.owner is not None and self.thread != threading.get_ident():
            raise InputConflict('Another activity owns game input')
        if self.owner is not None and self.clock() >= self.deadline:
            self.pause('Activity time limit reached')
            raise SessionStopped(self.reason)

    check_active = check

    def _acquire_process_lock(self):
        if not self.path:
            return
        # All worktrees/runtimes on this Windows account share one input lock.
        folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'JH-WW'
        folder.mkdir(parents=True, exist_ok=True)
        stream = (folder / 'game-input.lock').open('a+b')
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            stream.close()
            raise InputConflict('Another process owns game input') from error
        self._process_lock = stream

    @contextmanager
    def activity(self, owner, seconds=600):
        if not 0 < seconds <= 3600:
            raise ValueError('Activity time bound must be 1..3600 seconds')
        nested = False
        with self._lock:
            self.check()
            if self.owner is not None:
                if self.thread != threading.get_ident():
                    raise InputConflict('Another activity owns game input')
                nested = True  # existing executor's synchronous task delegation
            else:
                self._acquire_process_lock()
                self.owner, self.thread = owner, threading.get_ident()
                self.deadline = self.clock() + seconds
            epoch = self.epoch
        try:
            yield epoch
            self.check(epoch)
        except BaseException as error:
            if not nested and self.state == 'READY':
                self.cancel(str(error))
            raise
        finally:
            if not nested:
                try:
                    self.release_all()
                finally:
                    self.owner = self.thread = None
                    if self._process_lock:
                        self._process_lock.close()
                        self._process_lock = None

    def queued_action(self, action):
        epoch = self.epoch
        def invoke(*args, **kwargs):
            self.check(epoch)
            return action(*args, **kwargs)
        return invoke


def is_runtime(task):
    executor = getattr(task, '_executor', None)
    return executor is not None and type(executor).__module__.startswith('ok.')


def get_session(task):
    executor = getattr(task, '_executor', None)
    target = executor if is_runtime(task) else task
    session = vars(target).get('_jh_session') if target is not None else None
    if session is None:
        path = Path('configs/automation-session.json') if is_runtime(task) else None
        session = Session(path)
        target._jh_session = session
    return session


def guarded_run(function):
    @wraps(function)
    def run(self, *args, **kwargs):
        if not is_runtime(self):
            return function(self, *args, **kwargs)
        from src.automation.input_guard import install_input_guard, is_effect_free_interaction
        session = get_session(self)
        install_input_guard(self, session)
        # Saved-image tests use the library's exact effect-free backend. Their
        # direct callbacks/run methods have no operational input or spending to
        # own. Task-level story checks still read the same session semantics.
        if is_effect_free_interaction(self.executor.interaction):
            return function(self, *args, **kwargs)
        # The control task must remain usable to cancel/resume a stopped session.
        if type(self).__name__ == 'AutomationSessionTask':
            return function(self, *args, **kwargs)
        if type(self).__name__ in ('MergeEchoTask', 'EnhanceEchoTask', 'FiveToOneTask', 'ChangeEchoTask'):
            raise SessionStopped('Destruction/valuable-item consumption is disabled by shared resource policy')
        if session.story_locked and type(self).__name__ in (
                'AutoDialogTask', 'AutoPickTask', 'AutoCombatTask', 'FastTravelTask', 'AutoLoginTask'):
            return False
        read_only_hunt = False
        if session.story_locked and type(self).__name__ == 'HuntMobTask':
            from src.task.HuntMobTask import HuntMobTask
            read_only_hunt = (type(self) is HuntMobTask and self.config.get('Localization Only') is True)
        if session.story_locked and type(self).__name__ not in ('StoryWatchTask',) and not read_only_hunt:
            raise SessionStopped('STORY_WATCH suspends incompatible tasks; select mode explicitly')
        seconds = session.resource_profile.get('max_seconds', 600)
        with session.activity(type(self).__name__, seconds=seconds):
            if read_only_hunt:
                session.read_only_depth += 1
            try:
                return function(self, *args, **kwargs)
            finally:
                if read_only_hunt:
                    session.read_only_depth -= 1
    return run
