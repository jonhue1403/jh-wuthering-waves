"""Read-only Windows privilege check before hunt movement owns any inputs."""

import os
import sys


def _process_privileges(pid):
    import win32api
    import win32con
    import win32security

    process = win32api.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    try:
        token = win32security.OpenProcessToken(process, win32con.TOKEN_QUERY)
        try:
            return (
                bool(win32security.GetTokenInformation(token, win32security.TokenElevation)),
                bool(win32security.GetTokenInformation(token, win32security.TokenUIAccess)),
            )
        finally:
            token.Close()
    finally:
        process.Close()


def require_game_input_access(hwnd):
    """Reject a known elevation mismatch; never request elevation or send input."""
    if sys.platform != "win32":
        return
    import win32process

    try:
        if not hwnd:
            raise ValueError("No game window")
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            raise ValueError("No game process")
        game_elevated, _ = _process_privileges(pid)
        task_elevated, task_ui_access = _process_privileges(os.getpid())
    except Exception as error:
        raise RuntimeError("Cannot verify game input privileges; movement was not started") from error
    if game_elevated and not (task_elevated or task_ui_access):
        raise RuntimeError(
            "The game runs as administrator but this OK-WW process does not. "
            "Restart this checkout with matching privileges before movement testing. "
            "Localization Only can still capture without sending inputs."
        )
