# Farming Assistant — standalone read-only browser preview

## Why this exists

OK Script 3.0.4 supports the Qt desktop app but removed the legacy WebCustomTab
and `ok web` APIs. The Farming Assistant browser view is now independent of
OK Script; it does not control gameplay.

Use `main.py` for the native Qt app or `run-farming-web.cmd` for the standalone
browser preview. The legacy `main_web.py` and `run-local-web.cmd` remain Qt
compatibility aliases and MUST NOT be advertised as a browser frontend.

## Entry points and contract

- `main_farming_web.py` starts the local HTTP server and opens a browser.
  Use `--no-browser` for headless tests and `--port 0` to select a free port.
- `src/automation/farming_web_server.py` binds exclusively to
  `127.0.0.1` and exposes two GET-only JSON endpoints:
  `/api/targets?kind=material&query=MECH` and
  `/api/preview?kind=material&target_id=ff-mech-core&desired_total=5`.
- `src/web/farming_assistant/standalone.html`, `standalone.js` and
  `standalone.css` adapt the existing `index.js` component using
  `context.query`, `context.t` and `context.notify`. There is no second
  target-selection implementation.
- The native Qt `custom_tabs` registration remains in `config.py`; the
  unsupported `web_tabs` registration is removed. The obsolete
`src/task/FarmingAssistantTask.py` was deleted, as it imported a removed
framework API and is no longer an entry point.

No OK Script executor, input subsystem, browser remote control, screenshot
directory, game files, secrets or profile paths are served.

## Boundary and security

The server rejects non-loopback Host headers, foreign Origin and cross-site
Fetch Metadata, unknown API parameters, duplicate query parameters, request
bodies, cross-origin access and all non-GET methods. Static routes are an exact
allowlist, not a filesystem router. CORS is not enabled. Responses set CSP,
no-store, nosniff and anti-framing headers.

Every preview carries `can_start=false`, `can_pause=false` and
`can_stop=false`. UI Start/Pause/Stop remain disabled. Documented possible
enemy sources and hash-matched historical captures are NEVER sufficient to
authorize farming. No live FF Mech Core route is currently qualified.

This localhost service is designed for use on a trusted PC. It has no
authentication and must never be bound to a public interface, exposed through
port forwarding or hosted on a shared machine.

## Codex Windows qualification

Run the repository-local interpreter:

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingStandaloneWeb.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestConfig.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'TestFarming*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestMainWebCompatibility.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_web_server.py main_farming_web.py
node --check src/web/farming_assistant/index.js
node --check src/web/farming_assistant/standalone.js
.\.venv\Scripts\python.exe scripts/verify_core_routes.py --all --output logs/core-routes/farming-standalone-web
```

Run `run-farming-web.cmd` or `python main_farming_web.py`, inspect the
real page at the printed 127.0.0.1 URL in a browser, and confirm:

- FF Mech Core search, all five documented enemy candidates, material quantity,
  mob encounter limit, calibration checklist and disabled controls.
- Native Qt still launches via `main.py` and the legacy `main_web.py` alias.
- No browser console errors, private data leakage, CORS access, input dispatch,
  Waveplate spending or unexpected game activity.
- Closing the server process releases its loopback listener and port.
- Screen width 1280x720 and the actual user's desktop resolution.

These operations require the Windows checkout and have NOT been executed by the
GitHub-only integration author. Do not report offline qualification CLEAR until
actual full-suite and browser results are obtained. The two prior private-game
fixture skips remain separately tracked.

## Status

FQ-01 framework blocker: standalone design implemented in source; Windows
and real-browser requalification is PENDING.
FQ-04 FF Mech Core source/route verification: LIVE_VERIFICATION_PENDING.
No movement, combat, inventory receipts or independent new Terra review claimed.
