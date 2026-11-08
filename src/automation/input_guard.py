"""Guard the real executor interaction boundary, including inherited tasks."""
import threading
import time

from src.automation.session import SessionStopped

INPUT_METHODS = frozenset(('click', 'middle_click', 'right_click', 'send_key',
    'send_key_down', 'send_key_up', 'mouse_down', 'mouse_up', 'move', 'swipe',
    'scroll', 'input_text', 'back', 'activate', 'on_run'))


def validate_observation(task, *, require_input_access=False, previous_sequence=None):
    """Validate an actual captured frame and the capture/input window binding."""
    capture = task.executor.interaction.capture
    window = task.hwnd
    capture_window = getattr(capture, 'hwnd_window', None)
    if not window or not window.exists or not window.visible:
        raise SessionStopped('Target game window unavailable')
    if capture_window is None or capture_window.hwnd != window.hwnd:
        raise SessionStopped('Capture and input target windows differ')
    timestamp = getattr(capture, '_jh_frame_timestamp', None)
    sequence = getattr(capture, '_jh_frame_sequence', None)
    if timestamp is None or sequence is None or not 0 <= time.monotonic() - timestamp <= 2:
        raise SessionStopped('Fresh-frame capture validation required')
    if previous_sequence is not None and previous_sequence == sequence:
        raise SessionStopped('Capture did not advance to a distinct frame')
    if require_input_access:
        from src.overworld.input_access import require_game_input_access
        require_game_input_access(window.hwnd)
    return sequence


def input_checkpoint(task):
    from src.automation.session import get_session, is_runtime
    if not is_runtime(task):
        return
    session = get_session(task)
    session.check()
    if session.owner is None:
        raise SessionStopped('No activity owns game input')
    validate_observation(task, require_input_access=True)


def guard_backend(task, backend):
    """Cover inherited foreground gestures that create an alternate backend."""
    from src.automation.session import get_session, is_runtime
    if not is_runtime(task):
        return backend
    input_checkpoint(task)
    return GuardedInteraction(backend, get_session(task), lambda: input_checkpoint(task))


class GuardedInteraction:
    def __init__(self, wrapped, session, validate, frame_validator=None):
        self.wrapped = wrapped
        self.session = session
        self.validate = validate
        self.frame_validator = frame_validator or validate
        self.keys = set()
        self.buttons = set()
        self.lock = threading.RLock()
        session._release.append(self.release_all)

    @property
    def __class__(self):
        return self.wrapped.__class__

    def __getattr__(self, name):
        value = getattr(self.wrapped, name)
        if name not in INPUT_METHODS or not callable(value):
            return value
        def call(*args, **kwargs):
            if name == 'on_run' and self.session.owner is None:
                # Framework enable/preparation hooks run before the task lease.
                # Deferring focus is safe; tasks activate inside their lease.
                return None
            if name == 'send_key':
                key = args[0] if args else kwargs['key']
                duration = args[1] if len(args) > 1 else kwargs.get('down_time', .02)
                if not 0 <= duration <= 10:
                    raise SessionStopped('Key action exceeds bounded duration')
                self.send_key_down(key)
                epoch = self.session.epoch
                end = time.monotonic() + duration
                try:
                    while time.monotonic() < end:
                        self.session.check(epoch)
                        time.sleep(min(.01, max(0, end - time.monotonic())))
                finally:
                    self.send_key_up(key)
                return None
            foreground_backend = type(getattr(self.wrapped, 'check_clickable', None)) is bool
            if foreground_backend and name == 'swipe':
                x1, y1, x2, y2 = args[:4]
                milliseconds = args[4] if len(args) > 4 else kwargs.get('duration', 500)
                if not 0 <= milliseconds <= 5000:
                    raise SessionStopped('Drag exceeds bounded duration')
                steps = max(1, int(milliseconds / 20))
                self.mouse_down(x1, y1, key='left')
                try:
                    for index in range(1, steps + 1):
                        self.move(int(x1 + (x2 - x1) * index / steps),
                                  int(y1 + (y2 - y1) * index / steps))
                        time.sleep(milliseconds / steps / 1000)
                finally:
                    self.mouse_up(key='left')
                return None
            if foreground_backend and name == 'click':
                x = args[0] if args else kwargs.get('x', -1)
                y = args[1] if len(args) > 1 else kwargs.get('y', -1)
                key = kwargs.get('key', 'left')
                duration = kwargs.get('down_time', .05)
                if not 0 <= duration <= 1:
                    raise SessionStopped('Click exceeds bounded duration')
                self.mouse_down(x, y, key=key)
                try:
                    end = time.monotonic() + duration
                    while time.monotonic() < end:
                        self.session.check()
                        time.sleep(min(.01, max(0, end - time.monotonic())))
                finally:
                    self.mouse_up(key=key)
                return None
            with self.lock:
                # Key/button releases are always allowed during cancellation.
                release = name in ('send_key_up', 'mouse_up')
                if not release:
                    self.session.check()
                    if self.session.owner is None:
                        raise SessionStopped('No activity owns game input')
                    if foreground_backend and not self.wrapped.hwnd_window.is_foreground():
                        self.session.takeover('Game foreground lost; held input released')
                        raise SessionStopped('Game foreground lost; input delivery stopped')
                    self.validate()
                key = args[0] if args else kwargs.get('key')
                if name == 'send_key_down':
                    self.keys.add(key)
                elif name == 'send_key_up':
                    if key not in self.keys:
                        return None
                    self._release_key(key)
                    self.keys.discard(key)
                    return None
                elif name == 'mouse_down':
                    self.buttons.add(kwargs.get('key', 'left'))
                elif name == 'mouse_up':
                    if kwargs.get('key', 'left') not in self.buttons:
                        return None
                    self._release_button(kwargs.get('key', 'left'))
                    self.buttons.discard(kwargs.get('key', 'left'))
                    return None
                return value(*args, **kwargs)
        return call

    def _unconditional_release(self, function, *args, **kwargs):
        # Pynput's normal release refuses a background target. Only release our
        # tracked presses after takeover; never press or move with this override.
        previous = getattr(self.wrapped, 'check_clickable', None)
        if type(previous) is bool:
            self.wrapped.check_clickable = False
        try:
            return function(*args, **kwargs)
        finally:
            if type(previous) is bool:
                self.wrapped.check_clickable = previous

    def _release_key(self, key):
        return self._unconditional_release(self.wrapped.send_key_up, key)

    def _release_button(self, key):
        return self._unconditional_release(self.wrapped.mouse_up, key=key)

    def release_all(self):
        failures = []
        with self.lock:
            for key in list(self.keys):
                try:
                    self._release_key(key)
                    self.keys.discard(key)
                except Exception as error:
                    failures.append(error)
            for key in list(self.buttons):
                try:
                    self._release_button(key)
                    self.buttons.discard(key)
                except Exception as error:
                    failures.append(error)
        if failures:
            raise SessionStopped('Held input cleanup failed') from failures[0]

    def validate_frame(self):
        return self.frame_validator()


def install_input_guard(task, session):
    executor = task.executor

    def ensure_backend():
        # TaskExecutor.interaction is a read-only property in 3.0.4. Update the
        # actual owner, including a job-specific override, never the property.
        job = getattr(executor, 'current_job', None)
        if (job is not None and getattr(job, 'interaction', None) is not None
                and executor.is_executor_thread()):
            owner = job
        else:
            owner = getattr(executor, 'device_manager', executor)
        backend = getattr(owner, 'interaction', None)
        if backend is not None and not isinstance(backend, GuardedInteraction):
            owner.interaction = GuardedInteraction(
                backend, session,
                lambda: validate_observation(task, require_input_access=True),
                lambda: validate_observation(task))

    ensure_backend()
    if getattr(executor, '_jh_guard_installed', False):
        return
    executor._jh_guard_installed = True
    original_next_frame = executor.next_frame
    def fresh_frame(*args, **kwargs):
        if session.owner is not None:
            session.check()
        ensure_backend()
        frame = original_next_frame(*args, **kwargs)
        ensure_backend()
        if frame is not None:
            stamp = executor._last_frame_time
            capture = executor.interaction.capture
            capture._jh_frame_timestamp = time.monotonic() - (time.time() - stamp)
            capture._jh_frame_sequence = stamp
        return frame
    executor.next_frame = fresh_frame
    original_check = getattr(executor, 'check_enabled', None)
    if original_check:
        def check_enabled(*args, **kwargs):
            if session.owner is not None:
                session.check()
            return original_check(*args, **kwargs)
        executor.check_enabled = check_enabled
    for method_name, stop in (('pause', session.pause), ('stop_current_task', session.cancel), ('stop', session.cancel)):
        original = getattr(executor, method_name, None)
        if original:
            def lifecycle(*args, _original=original, _stop=stop, **kwargs):
                if session.owner is not None:
                    _stop('Framework pause/stop; inspect state before resume')
                return _original(*args, **kwargs)
            setattr(executor, method_name, lifecycle)
    original_wait = getattr(executor, '_wait_for_activity', None)
    if original_wait:
        def bounded_wait(timeout, *args, **kwargs):
            if session.owner is not None:
                session.check()
                timeout = min(timeout, .1)
            return original_wait(timeout, *args, **kwargs)
        executor._wait_for_activity = bounded_wait
    original_prepare = getattr(executor, '_prepare_task_for_run', None)
    if original_prepare:
        def prepare(*args, **kwargs):
            ensure_backend()
            backend = executor.interaction
            if (backend is not None and type(getattr(backend, 'check_clickable', None)) is bool
                    and not backend.should_capture()):
                raise SessionStopped('Foreground capture is unavailable: focus the verified game window manually before starting; no automatic focus was issued')
            return original_prepare(*args, **kwargs)
        executor._prepare_task_for_run = prepare
    manager = getattr(executor, 'device_manager', None)
    if manager is not None:
        original_start = getattr(manager, 'do_start', None)
        if original_start:
            def rebind(*args, **kwargs):
                if session.owner is not None:
                    session.cancel('Capture/input backend changed; requalification required')
                result = original_start(*args, **kwargs)
                ensure_backend()
                return result
            manager.do_start = rebind
