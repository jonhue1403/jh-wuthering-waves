# JH Wuthering Waves — Farming Assistant implementation status

Last manual checkpoint: 2026-11-13 (Asia/Kuala_Lumpur)
Working branch: `agent/material-first-farming`
Base: draft PR #4, `codex/core-and-routes-20261108` at `e06a9fb7b066e74c988e066154198fe89124173e`
Integration status: **IN PROGRESS — NOT LIVE QUALIFIED**. Preserve existing draft PR #4, master and user settings.

## Required product contract

- Primary task is a user-friendly **Farming Assistant**: search/select a **material** or **mob**, choose an optional user goal quantity, click **Start**. No end-user entry of `Hunt Profile`, `Plan Path`, `Route Manifest`, `Runtime Qualification` or developer filenames.
- The pictured first example is **FF Mech Core**. Community-documented possible enemy sources are now listed for discovery (Geospider S4, Sabercat Reaver, Spacetrek Explorer, Twin Nova: Collapsar Blade, Twin Nova: Nebulous Cannon), from https://wutheringwaves.fandom.com/wiki/FF_Mech_Core . **These are not game-observed inventory receipts or executable routes**. Actual FF Mech Core material-to-enemy mapping and live route qualification are still missing. The app must show this distinction without starting movement.
- Material lookup should distinguish documented possible drop sources, usable verified map spawns, eligible current-runtime reviewed routes, and actual inventory-confirmed rewards.
- Keep existing session ownership, fresh game frame and focus rules, no-skip story policy, no spending/refill, bounded route/camp limits, cancellation, input cleanup and all current live qualification requirements. Do not automate unsafe actions.

## Completed — first foundation increment

- `src/automation/farming_selection.py`: immutable target/search/catalog models and a fail-closed resolution interface. Handles material/mob selection, aliases, exact source evidence references, unique source and route IDs, and optional qualified-route predicate. **No predicate means no route READY**, even if a route candidate is listed. Seeded visible FF Mech Core item only, intentionally without fabricated enemy sources.
- `tests/TestFarmingSelection.py`: offline-only tests for search, missing sources, no automatic route qualification, explicit verifier, unknown/duplicate mappings, and suppression of developer path details.
- No existing task registration, runtime, live input, user settings or gameplay behavior has been changed.

Code commits:
- `ced11f81106ea522c334b84f6fec417c286b72b5` — initial catalog
- `1a054372b72a4ea97f07710648c87e36de3f5049` — unit tests

**Verification:** Files were committed through the GitHub connector. Tests **NOT RUN**: no local game/Python repository runtime is attached to this chat. Never report these as passed before executing them.

## 2026-11-13 immediate implementation increment — committed, not runtime-tested

- `src/automation/farming_selection.py`: added immutable `DocumentedMobDrop` with HTTPS citation checking, `SOURCE_DOCUMENTED` status, `documented_sources` lookup and five FF Mech Core candidate enemies as informational records only. UI slugs are **not** in-game numeric mob identifiers, drop likelihoods or permitted routes.
- Material resolutions now require a caller-supplied `source_is_qualified` predicate for observed-drop evidence **and** a separate `route_is_qualified` predicate for executable routes. A nonempty evidence label, wiki citation or route candidate alone cannot return `READY`. Existing direct-mob route verification remains separate.
- `tests/TestFarmingSelection.py`: expanded regression coverage for five FF Mech Core candidates, source provenance, external data remaining non-executable, unverified evidence labels, invalid citation URLs, duplicate/missing source references, and both qualification gates.
- GitHub commits: `a63e76c255d451f4d3935e7af4b2df58548daea2`, `b49316ede918a3fd80ef4717d0ca712bd5934ba4`, `7c03147207688bc6ab0a39816f8fb56a090ba1e7`.
- **Tests NOT RUN:** GitHub connector file edits do not execute Python; no local project execution runtime is attached. Next local Codex pass must run the exact unit tests and report their result. No game input, Antigravity CLI, Terra review or Codex session is claimed.

## 2026-11-13 scheduled implementation increment — preview UI added

New source files:
- `src/automation/farming_view.py`: pure Python, path-free JSON view model; strict material/mob and target-total validation; documented source names/URLs; `owned_quantity: null` instead of invented inventory; `can_start/can_pause/can_stop: false` regardless of source metadata.
- `src/task/FarmingAssistantTask.py`: read-only OK Script `WebCustomTab` with `targets` and `preview` queries, and a fail-closed `start` action which rejects execution from either the UI or a direct caller.
- `src/web/farming_assistant/index.js`: compact native custom-tab material/mob selector, searchable results, possible enemy-source references, optional desired total, readiness diagnostics, and visible but disabled Start/Pause/Stop. Uses DOM `textContent`, not interpolated untrusted HTML.
- `tests/TestFarmingAssistantView.py`: offline contract tests for FF Mech Core, filters, mob selection, all-five documented sources, path suppression, unmeasured inventory, goal validation, and refusal to mark synthetic sources as executable.

Commits:
- `bc09a88f6f2235b39f44877188fe79233f02802f` — view model
- `717683b09adb339e41f0a090ce17b0a83c0300ca` — view contract tests
- `3e7052b514133efb1c145fd59bb57673b1f384a6` — OK Script WebCustomTab task API
- `9d856a3a6d842dd21705254134480e24306627de` — web tab asset/UI

**Verification:** GitHub files and branch updates confirmed. Python tests, JS parsing, local runtime registration and visual UI verification **NOT RUN**: connected GitHub can edit code, but cannot run the owner's local `ok-script`, game, Python virtual environment, Antigravity CLI or independent Terra session. This is an **unqualified preview prototype**, not a verified production screen or functioning farming executor. New WebCustomTab follows the existing CharacterCodeTask integration pattern but has not yet been launched through the actual app. The legacy HuntMobTask developer form is unchanged for compatibility, so the end-user UI replacement is **not complete**.

Commands for local validation (Windows PowerShell):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingSelection.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_view.py src/task/FarmingAssistantTask.py
node --check src/web/farming_assistant/index.js
```

Confirm custom-task discovery exposes the new Farming Assistant WebCustomTab. If unavailable, correct registration by following the installed `ok-script` discovery contract, without modifying unrelated task registrations. This increment does not authorize any route executor.

## 2026-11-13 02:04 MYT — web-tab registration increment

- **Root cause discovered:** `FarmingAssistantTask` inherited from `WebCustomTab` but had no `config['web_tabs']` entry, so the existing Web UI had no supported way to discover this tab. Verified the official OK Script contract: https://ok-script.com/en/docs/task_web_tabs/ (Web-only `web_tabs`; Qt `custom_tabs`; `WebCustomTab` does not belong in `onetime_tasks`).
- `config.py`: registered `["src.task.FarmingAssistantTask", "FarmingAssistantTask"]` under `web_tabs` only. Existing task registration/order and Qt task behavior remain unchanged; preview still cannot control the game.
- `tests/TestConfig.py`: added a contract test asserting web-only registration, `WebCustomTab` inheritance, the stable tab ID, no runnable task entry, `task_controls=False`, and an existing `index.js`.
- Commits: `33f92463601e4c21dbf1e04f68473006dc8c51e6` (config), `68f3fbf94ac45b4d302088bc3c0e7ef470543abd` (test).
- **Verification status:** code committed and read-back confirmed; **Python tests, web server startup, frontend mount and actual Qt UI not run**. No authenticated local game or ok-script MCP runtime is accessible to this scheduled run.
- **Important scope:** This makes the tab discoverable by the **Web UI** in `main_web.py`; it does **not** make a new tab appear in classic **Qt** UI and does not hide the legacy `HuntMobTask` developer form. The Qt UX replacement remains pending.
- Local Codex acceptance commands (Windows, from repo root after switching to this branch):
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -s tests -p TestConfig.py -v
  .\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
  .\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingSelection.py -v
  .\.venv\Scripts\python.exe -m py_compile config.py src/task/FarmingAssistantTask.py
  node --check src/web/farming_assistant/index.js
  .\.venv\Scripts\python.exe main_web.py --browser
  ```
  Check Farming Assistant navigation is visible and read-only; Start, Pause and Stop disabled. Record screenshot and inspect backend logs; do not start game execution.

## 2026-11-13 03:04 MYT — native Qt read-only preview increment

- `src/gui/FarmingAssistantTab.py`: added an independent native `CustomTab` that reuses `FarmingAssistantView` without importing the game executor or sending input. The compact two-pane interface includes a Material/Mob toggle, live search, target info, documented possible enemy list with explicit HTTPS reference opening, optional desired inventory total, current-inventory-unknown label, readiness diagnostics and disabled Start/Pause/Stop controls.
- `config.py`: added a separate `custom_tabs` Qt registration. Existing `web_tabs`, `onetime_tasks`, `trigger_tasks`, draft PR #4 and master remain untouched. The old developer-oriented HuntMobTask remains available to avoid breaking existing users, but is **not hidden** yet.
- `tests/TestFarmingAssistantQt.py`: offscreen Qt contract tests for default FF Mech Core, five informational candidate sources, target filtering, type switching, quantity handling, disabled gameplay controls, source-link safety and no exposed developer paths.
- `tests/TestConfig.py`: updated Qt-only registration and inheritance contract, keeping web registration independently checked.
- Code commits: `c44055fb84b5b1bdee74c17f3dc8df18114ff698`, `4bd0fea29fc38852002c0ad44de36a6a74a595b1`, `8e1c9e908ea7691cc41b030b0d5c71e89dd3ce3f`, `c226b546c78c1c9b9ad5c8e496fe7948b2ed3e8e`.
- **Verification: NOT RUN.** GitHub changes are committed, but this runtime cannot reach the owner's local Python/PySide6/ok-script or game. A separate container cannot fetch this repository by HTTPS (DNS unavailable), so it cannot honestly substitute for a test run. Qt class creation and tab mounting remain unverified. No live route/combat/spend claims, CLI invocation, Terra review, or Codex execution.
- Before any UI release, Codex should run the offscreen tests and instantiate Qt main navigation to verify the exact installed OK Script version and tab lifecycle, then inspect screenshots in the actual desktop UI. The tab is informational only, **not** a functioning farming executor.

Local Codex verification from the branch (PowerShell):

```powershell
git fetch origin
git switch agent/material-first-farming
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestConfig.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingSelection.py -v
.\.venv\Scripts\python.exe -m py_compile src/gui/FarmingAssistantTab.py config.py
```

Next small increment: evidence-backed, read-only source/profile adapter and explicit calibration guide, still no route dispatch. Then qualify UI startup in both frontends and test current-game evidence before enabling anything.

## 2026-11-13 04:04 MYT — bounded offline receipt evidence intake

**Implemented and committed on `agent/material-first-farming`; last audited source HEAD:
`854d4a61bbb6a3a00bf8ab212b4e7146d84694ef`.**

- `src/automation/farming_evidence.py`: added an internal-only, read-only evidence scanner for `configs/farming-assistant/evidence/`. It accepts bounded reviewed metadata *claims*, distinct before/after inventory screenshots with exact SHA256 hashes, explicit current-version metadata, numeric game mob ID, timezone-aware observation timestamp, positive inventory delta and distinct frame IDs. Rejects missing/changed files, wrong IDs, stale/future timestamps, insufficient quantities, duplicate frames, unreviewed metadata, path traversal/symlinks, excessive file sizes, and incomplete manifest scans. Local audit data are cached at most 10 seconds. No task/executor/input imports.
- `src/automation/farming_view.py`: now exposes only a path-free `calibration` summary (count, audit status, candidate source IDs/quantities) for a selected material. **It does not promote any historical candidate to `verified_mob_ids`, `qualified_route_ids` or `can_start`.**
- `src/gui/FarmingAssistantTab.py` and `src/web/farming_assistant/index.js`: show candidate receipt counts and invalid/incomplete audit warnings, while Start/Pause/Stop stay disabled.
- `tests/TestFarmingEvidence.py` (new), `tests/TestFarmingAssistantView.py`, `tests/TestFarmingAssistantQt.py`: regression coverage for synthetic hash-bound receipts, mutation, age/expiry, invalid identities, unsupported evidence paths, scan limits, 10-second cache expiration, path-free UI contracts and disabled execution.
- `docs/FARMING_ASSISTANT_EVIDENCE.md` (new): real capture/review workflow, deliberate DRAFT-only example JSON, private evidence-storage rules, and Codex offline/UI test commands. The example contains placeholders and **cannot** be used as live evidence.
- Commits: `c8c3096f1e578721563c84b2b3354a81f8bf6b40`, `555c102dacb0853267e7acb79cadde51e3550b61`, `daeab67752ae2e905b011517679f89c843207ea2`, `27e841ca31cc7ad2b5cad73b3e8ae085211f9ecb`, `a7aa2ecdd7838919ca7255d7652607258590ed01`, `f4d402fb68ad553e5c8f97185ab77639c1ba14cf`, `136c5795290462a2cb8dca3fbb610d8096804589`, `18a1d567bba1bcd8dcd4dd961f183f3c2043b654`, `854d4a61bbb6a3a00bf8ab212b4e7146d84694ef`.
- **Verification: NOT RUN.** GitHub file write/read was confirmed. No Python virtual environment or native Web/Qt/game runtime exists in this task's connected workspace. Do not report passing unit tests, launch, actual material gain, calibrated routes, independent Terra review or Antigravity CLI invocation.
- **Blocking live execution**: FF Mech Core still has *no actual independently reviewed game-drop receipt and no current-game calibrated route*. A SHA-matched screenshot candidate is not OCR verification or a route permit. Current UI remains preview-only, as before.

Next work: Codex to run the documented offline/Qt/UI checks, inspect actual startup, then an independent reviewer must qualify source/profile/route evidence and current-game runtime. The next safe incremental feature is a read-only profile/route candidate audit, not auto-start.

## Next independently reviewable increments (in order)

1. **Qualify both read-only frontends locally**: WebCustomTab and native PySide6 Qt `custom_tabs` are registered and committed but have not been started or visually tested. Run TestConfig, selection/view and new Qt offscreen tests; launch `main_web.py --browser` and classic `main.py`, inspect accessibility, keyboard behavior, source links and tab cleanup. Preserve old HuntMobTask until the new replacement is qualified.
2. Build a read-only source catalog adapter using actual current-game source/profile evidence (the basic external-vs-observed distinction and five-source seed are now implemented). Verify exact game IDs, material receipt hashes, aliases/locale and stale profiles. Do not assign playable routes to FF Mech Core without independent real evidence.
3. Upgrade the read-only preview UI to fully operational task controls only once live gates pass. The compact native WebCustomTab preview is implemented but Start/Pause/Stop, current inventory and progress receipts are intentionally inactive. Hide legacy developer file paths from ordinary users only after compatibility qualification.
4. Bind selected targets to existing bounded route machinery through internal profile and runtime-qualification resolution. Fail closed when missing/stale/unverified; support safe read-only preview and guided calibration; never silently enable walking/teleport/claim/combats.
5. Connect receipt-based completion and bounded failure/retry recovery, preserving current resource/Story Watch safeguards.
6. Add focused UI and contract tests, then local integration/live qualification later via Codex and independent Terra review.

## Required future-run procedure

At each scheduled run inspect latest `agent/material-first-farming` SHA and this file; implement the next small item, commit only on this branch, update this checkpoint with exact SHA and tests actually executed. Avoid repeated unchanged documentation-only commits. If no write access or no concrete productive change, say so clearly. Do not claim the game, Antigravity CLI, Terra desktop control or Codex was invoked unless genuinely connected and executed.

## Codex handoff commands (Windows PowerShell; after fetching branch)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingSelection.py -v
.\.venv\Scripts\python.exe scripts/verify_core_routes.py --all --output logs/core-routes/farming-assistant-verification
```

Test local UI interaction and setup, then carry out separately authorized current-version live qualification with an independently verified reviewer. Full live farming is **NOT YET APPROVED OR CLAIMED**.
