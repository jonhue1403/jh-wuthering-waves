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

## Next independently reviewable increments (in order)

1. **Local qualification of preview UI**: verify OK Script `WebCustomTab` discovery and asset loading, review keyboard/navigation and run the new contract tests. If auto-discovery does not find `FarmingAssistantTask`, add the smallest supported registration. Keep the old `HuntMobTask` until a safe replacement mechanism is verified.
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
