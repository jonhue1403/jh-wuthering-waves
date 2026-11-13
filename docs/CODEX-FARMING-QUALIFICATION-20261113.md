# Farming Assistant qualification — 2026-11-13

## Result

**Offline qualification: NOT COMPLETE. Live qualification: LIVE_VERIFICATION_PENDING.**

The native Qt Farming Assistant launches, renders, searches, switches between
Materials and Mobs, accepts a mob encounter limit, and keeps execution controls
disabled without qualified evidence. The pinned OK Script package does not
provide the `WebCustomTab` API imported by the web registration, so the required
WebCustomTab integration and its `TestConfig` contract fail. The full offline
suite therefore has one known error. No game input or farming was performed.

## Checkout and environment

- Canonical branch: `agent/material-first-farming`
- Base/verified remote HEAD: `dae99e4ee5f77a2884605f1f9d8f92d8561cbc66`
- Working checkout: isolated `Z:\Game\jh-ww-farming-qualification`; the
  user's `qa/android-gt30pro-validation` checkout and the existing
  `codex/core-and-routes-20261108` worktree were left unchanged.
- Qualification fix is on top of the base SHA; this report and the fix are
  committed together in the local qualification branch.
- Python `3.13.15`; `ok-script==3.0.4`; `ok-pyside-minimal==6.12.0.post2`;
  `pytest==9.2.0`; Node `v22.23.1`.
- The repository-local `.venv` was created in the isolated worktree from the
  repository's documented dependency procedure. The user's other checkout's
  environment was not modified.
- The game process was already running. Its input was not used. OK-WW was
  launched with the worktree venv using `main.py`; the app showed the game
  connection label and `Start OK-WW` control, but the executor was not started.

## Test results

| Check | Result |
| --- | --- |
| `unittest discover -s tests -p 'TestFarming*.py' -v` | 200 run: 196 passed, 4 skipped, 0 failed |
| `unittest discover -s tests -p 'TestConfig.py' -v` | 8 run: 7 passed, 1 error |
| `unittest discover -s tests -p 'TestHuntMobTask.py' -v` | 9 passed |
| `tests/test_autopick_abyss.py` after fixture correction | 14 tests plus 2 subtests passed |
| `node --check src/web/farming_assistant/index.js` | Passed |
| Full isolated repository verifier | 96 modules; 1,003 run: 996 passed, 6 skipped, 1 error; 95 modules passed, 1 failed, 0 zero-test modules; exit 1 |

Full verification command:

```powershell
.\.venv\Scripts\python.exe scripts/verify_core_routes.py --all --output logs/core-routes/farming-codex-full
```

The one full-suite error is `TestConfig.test_farming_assistant_is_registered_only_as_a_web_custom_tab` at its import of `WebCustomTab` from `ok`. The installed `ok-script==3.0.4` metadata lists `default`, `qt`, `adb`, `ocr`, and `dev` extras; its installed source has no web tab implementation. The repository declares `ok-script[web]==3.0.4`, but that extra is not provided by the pinned distribution. A downloaded 3.0.5b4 wheel was inspected, not installed; it also did not contain the needed web module. The package's published extra list confirms the mismatch ([PyPI package metadata](https://pypi.org/project/ok-script/)). This needs a framework version/API decision before a safe web registration repair can be made.

Six full-suite skips were recorded: four symlink/reparse-oriented tests could
not create symlinks in the current process; two live/private-capture tests had
no private captures available. The four Farming-suite skips are among those
symlink cases. These are skips, not passes. The production code's behavior for
Windows junctions/reparse points and the host's filesystem permissions was
therefore not qualified here.

## Defect register

| ID | Severity | Defect / evidence | Status |
| --- | --- | --- | --- |
| FQ-01 | P1 | Pinned OK Script 3.0.4 lacks `WebCustomTab`; `FarmingAssistantTask.py` import fails and `TestConfig` errors. The declared `web` extra is absent. | **Open blocker.** Needs compatible framework/API resolution. No local compatibility shim or weakened test was added. |
| FQ-02 | P2 | `test_autopick_abyss.py` allocated BaseTask instances with `__new__`, bypassing `_app` initialization. Under the real dependency, translation calls then failed. | **Fixed** by supplying the minimal mocked translation app in both affected fixtures; targeted and full verification rerun. |
| FQ-03 | P2 | Symlink / private capture tests cannot fully execute in this Windows session. | **Environment-limited.** Four symlink tests and two private capture tests skipped in full discovery. |
| FQ-04 | P1 | FF Mech Core has no authentic source/drop receipt, observed in-game numeric enemy ID, or independently qualified current-runtime route. | **Open live blocker.** Execution controls remain disabled. |

## UI verification

### Native Qt — partial pass

`main.py` opened the actual desktop app. At 1920×1080, the Farming Assistant
rendered as a two-pane screen with Materials/Mobs controls, search, documented
sources, optional goal, current-inventory label, calibration checklist, and
disabled Start/Pause/Stop controls. It explicitly showed “Current inventory:
not measured” and described the five enemy sources as documented only.

On-screen checks: uppercase `MECH` found FF Mech Core; switching to Mobs with
no search listed Geospider S4, Sabercat Reaver, Spacetrek Explorer, Twin Nova:
Collapsar Blade, and Twin Nova: Nebulous Cannon; selecting a source displayed
“Route not calibrated”; an optional mob goal of `2` was accepted; Start remained
disabled. The selection was returned to Materials with a blank search and
blank goal. No link was opened and no automation was started.

Evidence: a legible CUA screenshot was captured and displayed in this Codex
thread during review. It was not exported to a persistent image file. An
offscreen Qt capture was rejected as evidence because the headless platform
reported no usable font families and rendered tofu glyphs. Keyboard traversal,
tab close/reopen, 1280×720 actual-window layout and screen-reader checks remain
unqualified.

### WebCustomTab — blocked

JavaScript syntax passes. The runtime registration/backend contract cannot
start because the pinned OK Script package has neither `WebCustomTab` nor its
web-tab loader. No WebCustomTab page, browser console, or web action/query
contract was verified. Do not report web UI acceptance.

## Capture and evidence integration

The Farming regression suite exercised synthetic positive and negative paths
against the repository implementations and production dependencies, including
hash/type mismatch, changed bytes, duplicate or shared frame identities,
chronology/timestamp errors, expired packets, path traversal, duplicate JSON
keys, missing frames, and source/route mismatches. These synthetic cases
preserve fail-closed behavior and do not constitute authentic live capture.

Not qualified on this host: symlink/junction/reparse defenses in the skipped
cases, actual ACL/permission boundaries, real private screenshot retention,
current game/runtime version binding, current source identity, or a reviewed
route preflight using live evidence. Synthetic/historical evidence did not
enable execution.

## FF Mech Core source/route matrix

All five names below are community-documented candidates only. UI names/slugs
are not verified game database IDs. No candidate has an observed ID, verified
drop, actual inventory delta, calibrated route, or independent live review.

| Candidate | Source status | Numeric ID | Drop / inventory | Route |
| --- | --- | --- | --- | --- |
| Geospider S4 | DOCUMENTED_SOURCE; LIVE_VERIFICATION_PENDING | Not observed | Not observed | ROUTE_UNQUALIFIED |
| Sabercat Reaver | DOCUMENTED_SOURCE; LIVE_VERIFICATION_PENDING | Not observed | Not observed | ROUTE_UNQUALIFIED |
| Spacetrek Explorer | DOCUMENTED_SOURCE; LIVE_VERIFICATION_PENDING | Not observed | Not observed | ROUTE_UNQUALIFIED |
| Twin Nova: Collapsar Blade | DOCUMENTED_SOURCE; LIVE_VERIFICATION_PENDING | Not observed | Not observed | ROUTE_UNQUALIFIED |
| Twin Nova: Nebulous Cannon | DOCUMENTED_SOURCE; LIVE_VERIFICATION_PENDING | Not observed | Not observed | ROUTE_UNQUALIFIED |

Game version, map layer, spawn geometry, receipt screenshots and inventory
increase were not observed. No route is ROUTE_QUALIFIED.

## Independent review and worker status

- Independent reviewer: **GPT-6.1 Terra Medium**, invoked for source and
  regression review at base SHA `dae99e4ee5f77a2884605f1f9d8f92d8561cbc66`
  with the `_app` fixture correction present. It confirmed the fixture repair
  and identified the missing framework web API as a blocking integration
  finding. Disposition: **NOT CLEAR**; web blocker remains open.
- Terra independently reviewed qualification commit
  `1fae0d7d2448bb77c9a984a3367c6896c0553ca9`. It found the fixture correction
  sound, confirmed the report's counts against the verifier artifacts, and
  reported no new blocking defect in that commit. Integration disposition
  remains **NOT CLEAR** because the WebCustomTab mismatch and live gates remain.
- The full-run results were captured before committing, at the base SHA with
  the exact fixture correction present (`dirty_at_start=true`). They are not a
  separate execution of commit `1fae0d7`. Terra also notes that the UI screenshot
  and no-game-action claims came from the coordinator's CUA observation, not
  from persistent review artifacts.
- Antigravity CLI `agy` was installed and listed Gemini 3.8 Flash models, but
  the native CLI invocation timed out with `DEADLINE_EXCEEDED` and returned no
  model output. Authentication/callability was not established; no Gemini
  implementation work is claimed.
- `agent-desktop` CLI was unavailable (`agent-desktop` command not found).
  Native interaction used Codex CUA as the available fallback; no game
  interaction occurred.

## Remaining blockers and next action

1. Resolve the framework integration contract: identify an official OK Script
   release that supplies the required web API, or revise the registration
   design and tests to the supported framework API. Re-run `TestConfig` and
   the actual web frontend before marking offline qualification complete.
2. Re-run symlink/reparse and private-capture tests in a Windows environment
   where those test prerequisites are available.
3. Obtain authentic, current-version FF Mech Core evidence: exact numeric IDs,
   observed drop and inventory delta, map layer/spawns, current runtime
   bindings, and independent route review. Until then status remains
   **LIVE_VERIFICATION_PENDING** and no farming may start.

No live stage was entered. No Waveplates, premium resources, refills or
valuable materials were spent. Story Watch protections were not changed.
