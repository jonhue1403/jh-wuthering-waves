# JH Wuthering Waves — Farming Assistant implementation status

Last manual checkpoint: 2026-11-13 (Asia/Kuala_Lumpur)
Working branch: `agent/material-first-farming`
Base: draft PR #4, `codex/core-and-routes-20261108` at `e06a9fb7b066e74c988e066154198fe89124173e`
Integration status: **IN PROGRESS — NOT LIVE QUALIFIED**. Preserve existing draft PR #4, master and user settings.

## 2026-11-13 11:02 MYT — local capture artifact SHA256 verification (read-only)

**Committed independent implementation increment: verifies original local bytes
against the immutable observation claim; still NOT trusted game evidence.**

- Added `src/automation/farming_capture_verify.py`: a frozen
  `LocalCaptureAudit` and `verify_local_capture_claim` that hash *actual*
  source, profile/reference/database binding and private screenshot files.
  Required source names are taken from the existing immutable handoff; frame
  and binding paths are internal maps only, never exposed through the Qt/Web
  operator UI.
- Rejects unsafe/absolute/traversal paths, symlinks, missing files, incomplete
  or duplicate file maps, source/binding/frame SHA256 mismatches, oversized
  reads and expired 15-minute capture claims. A single invalid artifact rejects
  the whole packet; partial hash matches are never reported as success.
- Added `tests/TestFarmingCaptureVerify.py` with 10 synthetic offline cases
  for successful integrity-only verification, tampered original source/frame/
  binding bytes, missing files, traversal paths, map ambiguity, symlinks,
  stale claims and invalid clock. A positive local hash check is explicitly
  unauthenticated and has `can_start=false`.
- Updated `docs/FARMING_ASSISTANT_LIVE_HANDOFF.md` with local operator
  boundaries, limitations and validation commands.
- GitHub commits in order: `621fb0b2c0fbcce695c84ebbca57c8270e751696`,
  `48ae9b47299ca5679f76f48f50f154baa414ded7`,
  `9b50a6dc813a4d86ab81e8787bd668d18005a859`.
- **Tests NOT RUN:** local project checkout and Windows Python/OK Script runtime
  unavailable; GitHub file commits are not test evidence. Devspace access to
  the previously cited Windows checkout returned an internal error; HTTPS
  GitHub clone from this container failed DNS resolution. No Antigravity CLI,
  Terra review, screenshot capture, game input or live FF Mech Core receipt.
- **Blockers:** no authenticated running game/version/frame producer, no
  independent current-game review, no qualified route/real inventory delta.
  Execution remains disabled; no PRs or master changed.

Codex Windows offline checks:

```powershell
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\\.venv\\Scripts\\python.exe -m py_compile src/automation/farming_capture_verify.py
```

**Next increment:** implement an internal opt-in, read-only capture *producer*
from real OK Script frame/focus/runtime abstractions when local Codex access
is available; keep any executor disconnected pending Terra qualification.

## 2026-11-13 10:02 MYT — immutable current-runtime observation handoff contract

**New independently reviewable implementation increment: structurally verified review
packet only, NOT a game observation or execution authority.**

- Added `src/automation/farming_live_handoff.py` with a frozen `FarmingObservationHandoff`
  and exact 19-field, versioned `build_observation_handoff` intake.
  Each packet has exact ASCII-decimal game enemy ID, observed game/OK Script
  version claims, private capture/session identity, fresh timestamp, stage,
  map layer, bounded frame tokens, declared SHA256 bindings/evidence/source hashes,
  optional observed inventory deltas and deterministic canonical packet digest.
- Enforces mandatory `RuntimeQualification.REQUIRED_SOURCES` coverage and
  stage-specific route sources, strict SHA256 formatting, 15-minute freshness,
  distinct before/after frame IDs **and image digests**, positive inventory
  delta for receipt purposes, and no inventory claim from route-only captures.
  Rejects extra approval/status fields. `public_summary()` is path-free and
  explicitly returns `can_start=False`, unauthenticated status and no session
  IDs, local paths or screenshot bytes.
- Added `tests/TestFarmingLiveHandoff.py` with synthetic regression cases for
  immutability, canonical digest stability, attempted self-approval, key
  injection, stale/future/naive timestamps, malformed IDs, missing/wrong
  bindings and duplicate/identical frames. This is *not* an independently
  reviewed/live current-game observation.
- Added `docs/FARMING_ASSISTANT_LIVE_HANDOFF.md` documenting the schema,
  capture/review separation, Codex+Terra responsibilities and commands.
- Source/test/documentation commits (in order):
  `61d42b1e317b7d667e4b0e6c9c609c9e2e0f6b24`,
  `e4f2edc131738003a3eec9b00bbfd799d38fddc1`,
  `b54700ef939432cdb822ed70f96490208653bdb0`,
  `759a4fd105697bc8fd95cd125772883cc3ec031a`,
  `126c19bc745f9f956174749d23c2ee84309ee39e`.
- **Tests NOT RUN**: checkout unavailable to local Python/Qt/OK Script
  execution; this is GitHub connector source editing only. No Gemini 3.8 Flash
  Antigravity CLI, Terra Medium, live game, screen control, CI, route execution,
  resource spending or merge was invoked.
- **Next**: implement a *read-only* trusted runtime capture adapter for actual
  version/frame/binding observations in a locally accessible game/runtime,
  while keeping any executor adapter disconnected until Codex local tests,
  current-game evidence and independent Terra qualification.

Codex Windows test handoff:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCalibrationGuide.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingPreflight.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_live_handoff.py
```

## 2026-11-13 09:03 MYT — guided read-only calibration checklist

**New source/UI increment: operator guidance, not a playable route or a live qualification.**

- Added `src/automation/farming_calibration_guide.py`: deterministic, path-free material/mob calibration sequence from the existing blocked preflight. Material flow shows source receipt, numeric enemy identity, installed version, bounded route, independent SHA-bound runtime review, live inventory delta and input-safety checks. Mob flow omits material receipt prerequisite.
- Every step is explicitly `NEEDS_LIVE_VERIFICATION` or `HISTORICAL_REFERENCE_ONLY`; `verified_step_count=0` and `can_start=false` are invariant. A local `REVIEWED` flag, static hash, historical ID overlap or game-version hint cannot complete steps.
- `farming_view.py` now exposes `calibration_guide` beside the previous preflight. Both the Web custom tab and native Qt panel display the guided checklist, highlight the next action and keep Start/Pause/Stop disabled. The UI has no operator path fields or arbitrary "mark done" actions.
- New `tests/TestFarmingCalibrationGuide.py` plus expanded `tests/TestFarmingAssistantQt.py` cover deterministic next-step selection, stale/historical-only status, immutable safety boundary, empty selection, native material/mob guidance and path-free output.
- **Tests NOT RUN:** GitHub connector edits cannot execute the local Python/Qt/OK Script runtime. Local Codex must run:
```powershell
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingCalibrationGuide.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\\.venv\\Scripts\\python.exe -m py_compile src/automation/farming_calibration_guide.py src/automation/farming_view.py src/gui/FarmingAssistantTab.py
node --check src/web/farming_assistant/index.js
```
- Next: define an immutable current-runtime observation handoff contract for Codex/Terra verification. Only then consider an internal executor adapter; do not let this checklist directly dispatch existing hunt tasks.

## 2026-11-13 08:02 MYT — version-aware read-only calibration preflight

**New independently reviewable increment: version diagnostics and next-step guidance, not game input or route authorization.**

- Added `src/automation/farming_preflight.py`: a pure Python checklist that separately reports historical source evidence, static route candidates, exact numeric enemy-ID overlap, optional historical-vs-supplied-version diagnostic, independent runtime qualification, fresh inventory and input-safety checks. `can_start` is unconditionally **false**; no runtime/game/input/sidecar modules are imported.
- A supplied `game_version_hint` is explicitly unauthenticated and **never accepted from the user-facing UI**. A historical text match is labeled `HISTORICAL_EQUAL_UNVERIFIED`, a mismatch is `HISTORICAL_VERSION_MISMATCH`, and missing current-game observation is `VERSION_NOT_OBSERVED`. The route audit still lacks independently checked, current-game version binding; even matching hints cannot qualify execution.
- `farming_view.py` exposes the path-free `preflight` object and target-specific `next_step`. Native Qt and Web UI display the calibration status without any file-path entry or change to disabled Start/Pause/Stop. Developer-oriented HuntMobTask and its task registration remain untouched.
- Added `tests/TestFarmingPreflight.py` with synthetic contracts for version match/mismatch/conflict, no hint, missing/invalid receipts/routes, exact ID mismatch, rejection of malformed/bool status metadata, path-free diagnostics, mob-specific block and both view kinds. Extended `TestFarmingAssistantView.py` and offscreen `TestFarmingAssistantQt.py`.
- Source/test commits: `cee4ee4c17694d3a3dfccf2c5aeb0d8ef2696fd4`, `7c8ab27d7eb377fbe260a96703486c55f82ac43d`, `9393da64724fa86d03e00806dd261d602917e7c4`, `51166b1a3c52a0030125210a5cd43e3c1eac699e`, `ed41b3fb4c8c3bca6233c60de4510895f2d4f573`, `e3d66b4c68eafa0b45dbdde0b484caa55577b607`, `181b207931614bdb55f9e9bd626be2648e8d856d`, `f8b1ee25dac6bec69bc68ce41cd9ee4f4bf286df`, `1a99cd13898681c164ec4e990fd86a91fc7df554`, `1516a5e29bdd0af6ac943c45c4745b4241d7b84d`.
- **Tests NOT RUN**: GitHub connector edits do not execute Python, Node or Qt; local Windows/Antigravity/Terra/game runtime was not accessible. No game inputs, spending, navigation, sidecar promotion or merge occurred.

Targeted local Codex qualification (Windows PowerShell):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingPreflight.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingReconciliation.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_preflight.py src/automation/farming_view.py src/gui/FarmingAssistantTab.py
node --check src/web/farming_assistant/index.js
```

**Next increment:** build a guided read-only calibration checklist that captures NO unreviewed user paths, then design the internal current-runtime observation/qualification boundary for later Codex+Terra verification. Do not auto-enable execution from this preflight module.


## 2026-11-13 07:02 MYT — exact game-mob-ID reconciliation (read-only)

**New independently reviewable implementation increment; no live authorization.**

- Added `src/automation/farming_reconciliation.py` to compare material-scoped historical inventory receipt candidates with static route candidates by **exact ASCII-decimal numeric game mob ID** only. Leading zeros remain significant; display/wiki slugs are not converted to numeric IDs. A local ID overlap can never qualify execution.
- `farming_evidence.py` and `farming_route_audit.py` now emit the material scope in each summary, preventing accidental cross-target joins. The reducer blocks incomplete/rejected audits, count/status inconsistencies, unknown and non-mapped material mobs, ambiguous catalog-to-game-ID or game-version claims, duplicate route IDs and malformed payloads. No local filenames or evidence paths are included in the cross-check output.
- `farming_view.py`, `FarmingAssistantTab.py` (Qt) and `src/web/farming_assistant/index.js` show a concise historical ID-overlap / mismatch / calibration-warning diagnostic. Existing `owned_quantity: null`, `verified_mob_ids: []`, `qualified_route_ids: []`, `run_state: PREVIEW_ONLY` and disabled Start/Pause/Stop are unchanged.
- Added `tests/TestFarmingReconciliation.py` with synthetic contracts for exact/leading-zero ID joins, no-match, mismatch, ambiguous sources and versions, unknown/unmapped source, rejected/incomplete scans, duplicate routes, path-free status, and UI-model refusal to start. Extended `tests/TestFarmingAssistantQt.py` for visible diagnostics.
- Updated `docs/FARMING_ASSISTANT_ROUTES.md` with the audit contract and local commands.
- **Source and test commits (in order):**
  `b16e55dd42665c3116a057a1ecdb6df3dbe06290`,
  `e637e3bda10424a47e88c38fb87d9cba7f30a7b2`,
  `1d5b82960f30668df2947f00b022482c91663343`,
  `b6c8fd32326042321fb42a0c7923fb608b47d489`,
  `54c2b9da51bfe3b5ce5120ae89f7bf0eedae14af`,
  `5c7ad0950a12c2cdcb7e38c2b4ecb9f804e4ed14`,
  `f617e157d9ad0d780106c46a689f062e475b14d0`,
  `067d8a14eca529da54f69505fad8a7d4f10bcc74`,
  `dd53eb26c30acd916d740e31e5ac61eb1af29e9c`,
  `f3f75f8ed0f2d5f265806204e0af74444607c50a`,
  `908657717e6b5cfa122e0f91977ec068fa36d79c`,
  `22f3b350ab8b5363cb965a90729020916068f745`,
  `fdda60810dacedbb23b36c8abdf760c26e2cf4ac`,
  `00000a51827c53cae35bfa0cdf38ede2a81370a1`.
- **Tests NOT RUN**: local repository/Qt/ok-script runtime is not attached. The connected GitHub tool confirmed commits, not Python execution. No Antigravity CLI, independent Terra review, native screenshot, actual game drop or input has been performed.
- **Next**: local Codex should execute the new reconciliation tests plus existing evidence, route, view, Qt and Web checks, validate actual Qt/Web rendering, and independently verify original FF Mech Core source receipt and current game-version routing. After those tests, implement a version-bound read-only preflight adapter and calibration workflow before any executor wiring.

Run on Windows PowerShell from the exact checked-out branch:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingReconciliation.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingEvidence.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRouteAudit.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_reconciliation.py src/automation/farming_view.py src/automation/farming_evidence.py src/automation/farming_route_audit.py
node --check src/web/farming_assistant/index.js
```

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

## 2026-11-13 05:xx MYT — offline route/profile candidate audit

**Source branch HEAD immediately before this documentation update: `687d9f2b82cb2021c9727c3fa6709173748289f9`.**
This is the next bounded implementation increment, not a live-game qualification.

- `src/automation/farming_route_audit.py` (new): implemented a bounded, read-only local candidate scanner with exact profile SHA256 matching; private direct-child path constraints; 8 manifest / 8 evidence per-manifest / 64 MiB total hash limits; no symlinks or traversal; exact source, profile, map layer and spawn coverage; 1–3 finite-waypoint camp segments; bounded inventory UI and pickup evidence claims. It produces **path-free static candidate counts only**, never READY.
- `tests/TestFarmingRouteAudit.py` (new): synthetic fixture and negative regressions for changed profile/evidence, wrong material or numeric mob ID, map layer/spawn mismatch, stale hashes, malformed paths, timestamp-independent cache expiry, over-limit manifests and the strict non-execution boundary.
- `src/automation/farming_view.py`: added independent `route_calibration` summary to material previews without exposing file paths, current-inventory values or enabled execution flags. Mob previews do not infer numeric IDs from wiki slugs.
- `src/gui/FarmingAssistantTab.py`, `src/web/farming_assistant/index.js`: show route candidate count and invalid/incomplete-audit status; all gameplay buttons stay disabled.
- `tests/TestFarmingAssistantView.py` and `tests/TestFarmingAssistantQt.py`: assert default and mob-route previews remain unqualified.
- `docs/FARMING_ASSISTANT_ROUTES.md` (new): describes the private operator-only intake folder, bounded read-only validation, and the missing live qualification contract. No local screenshots, secrets or manifest paths are exposed through the UI.
- Commits: `c7684067f0d13c6ba6c584cc2ba4e4fa81511373`, `80fa1cb85f9b0330d2f536d7692b9ce2d345df30`, `b9d83f65b3088033c46c5397148ec654ade64b68`, `47d56e86ec012aeee6bccfe669a1d88376eb5517`, `058100ea3ced06513fe72aee9583c66b5dbf5e89`, `c5f758ef1a606059dee9b0b88df2846404aaa056`, `00523dbb36421ff262f2b4e1983ebb3df7beedc6`, `687d9f2b82cb2021c9727c3fa6709173748289f9`, `f6e35fd77dbb74b802d4aae225a50837a6ce0451` (hermetic view test fixture tolerance).
- **Tests NOT RUN:** GitHub write/read succeeded, but no local Windows/Python/PySide6/Node/game environment is attached here. This run did **not** invoke Antigravity CLI, Terra Medium, a live game, or Codex. Do not treat source commits as test evidence.
- **Current blockers:** No authentic FF Mech Core inventory receipt, current-game numeric mob mapping, matching source/image/spawn evidence, reviewed sidecar or qualified local routes. No live control or merge was attempted.
- **Next increment:** Review and harden the static intake contract (especially path/error cases), then Codex should run all new and existing offline suites + both UI startup checks before any execution wiring. A separate local live review is needed for actual source/route calibration.

Offline Codex commands (Windows PowerShell; use local `.venv`):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRouteAudit.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingEvidence.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_route_audit.py src/automation/farming_view.py src/gui/FarmingAssistantTab.py
node --check src/web/farming_assistant/index.js
```

## 2026-11-13 06:xx MYT — strict local-audit decoding and duplicate-route defense

**Implementation: committed to `agent/material-first-farming`; static audit only,
not live farming, and no real FF Mech Core evidence is claimed.**

- New `src/automation/farming_static_json.py`: shared strict bounded JSON
  reader for offline calibration artifacts. Rejects duplicate object keys at
  every nesting depth, nonstandard `NaN`/`Infinity` tokens, non-object roots,
  and actual bytes over the cap even if a file grows after its initial stat.
- `src/automation/farming_route_audit.py`: reads both route and profile
  metadata through this parser and rejects a second manifest claiming an
  already encountered `route_id`. Distinct filenames cannot inflate
  route candidate counts.
- `src/automation/farming_evidence.py`: reads receipt manifests through
  the same strict parser; ambiguous data never yields a candidate.
- `tests/TestFarmingRouteAudit.py`: new synthetic regressions for duplicate
  route identity, duplicate nested route keys, duplicate profile keys despite
  refreshed SHA256, and non-finite route literals.
- `tests/TestFarmingEvidence.py`: new synthetic regressions for duplicate
  top-level and nested receipt keys and non-finite receipt literals.
- New `tests/TestFarmingStaticJSON.py`: bounded-decoder unit contract,
  including valid JSON, duplicate keys, nonstandard values, size and type gates.
- Updated `docs/FARMING_ASSISTANT_ROUTES.md` and
  `docs/FARMING_ASSISTANT_EVIDENCE.md` with the stricter intake rules.

**Code commits:**
`4b12969a7bdcccdbe9b43a1a2b5136b088fc94fc`,
`8723c2eb0b63bfaf40937a7cb68447108ae02569`,
`c0f3b2cacb8f2e18bdd0fbd62423e1c702eb5a46`,
`e056b54e1abf4f32dc1bef264776402c100f6b3d`,
`5bb4e7914f71050fa4ddefaf72b227a5dd934357`,
`02e88fa77042b09c4f1f215ebc695be4bebfb731`.

**Verification:** GitHub connector writes succeeded; test execution **NOT RUN**.
The tool runtime has Python 3.13 but could not fetch the repository
(`github.com` DNS resolution failed), so it cannot run the actual repo
suite, local PySide6/OK Script, Windows game, Antigravity CLI or Terra Medium.
Do not infer test success from new tests or commits. The existing
`can_start/can_pause/can_stop: false` boundary is unchanged; no input,
no source-to-route promotion, no merge.

**Next small increment:** read-only reconciliation between historical
receipt and route candidate records by exact observed numeric game mob ID,
with mismatch/ambiguity diagnostics and no automatic verification. Do
not derive numeric IDs from wiki slugs. Codex should first run
`TestFarmingStaticJSON.py`, `TestFarmingRouteAudit.py`,
`TestFarmingEvidence.py` and both UI checks on the real working tree.
No real FF Mech Core drop receipt, current-game qualification sidecar,
or runnable route is available yet.

Local Windows test commands:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingStaticJSON.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRouteAudit.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingEvidence.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_static_json.py src/automation/farming_route_audit.py src/automation/farming_evidence.py
node --check src/web/farming_assistant/index.js
```

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
