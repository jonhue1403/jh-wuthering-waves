# Codex one-shot handoff — JH Wuthering Waves Farming Assistant

## Objective and ownership

Perform ONE consolidated Windows testing, debugging and acceptance campaign on
`agent/material-first-farming` once implementation updates are complete.

Do **not** assume a material is executable just because it appears in the
catalog. The branch supports 27 screenshot material choices, the native Qt
preview, standalone read-only browser preview, community acquisition-method
references, legacy hunt/route executors, and substantial safety contracts.
It does **not** yet provide an independently qualified route for FF Mech Core
or confirmed playable acquisition workflows for all 27 materials.

Repository: `jonhue1403/jh-wuthering-waves`.
Preserve `master`, draft PR #4, unrelated worktrees and user settings.
Take ownership of the canonical branch only after checking there is no other
active writer. Never force-push, automatically merge, bypass safety controls,
modify game memory or packets, or turn on spending without independent approval.

Preferred roles if actually accessible in the Codex environment:
GPT-6 Luna High coordinator; Gemini 3.8 Flash through native Antigravity CLI
worker (not Gemini Bridge); GPT-6.1 Terra Medium independent reviewer and
screen observer. Do not invent invocation or review if any model is unavailable.
Use Codex itself to execute the local test runner and repair reproducible
issues, while preserving actual reviewer independence.

## Phase 0 — establish an exact, uncontested tree

1. Open the real Windows checkout/worktree. Read `AGENTS.md`, nested
   instructions, `.agents/skills/ok-script-develop/SKILL.md`, and the current
   `docs/FARMING_ASSISTANT_STATUS.md` and qualification documents.
2. `git fetch origin`; confirm `agent/material-first-farming` and actual
   current HEAD. **Do not reset to an earlier SHA.**
3. Check `git status --short`, other active worktrees, running game/OK
   Script processes and interpreter environment. Preserve all user changes.
4. Keep the ChatGPT hourly development task paused during this Codex campaign;
   coordinate before writes if it has been re-enabled.

## Phase 1 — run the one-shot offline qualifier once

From a clean, current worktree with its supported local virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/qualify_farming_one_shot.py
```

Equivalent double-click shortcut: `run-farming-one-shot.cmd`.

The runner performs, in sequence:

- Exact SHA and working-tree cleanliness capture;
- all 27 material selection/preview/readiness inspections;
- acquisition-reference consistency without enabling controls;
- Python compilation and both ES-module syntax checks;
- independent focused Qt, browser API, selection, acquisition, config and
  launcher test modules in isolated interpreter processes;
- full separate-process repository verification using
  `scripts/verify_core_routes.py --all` and a complete module coverage check;
- an exact-commit JSON report, per-phase logs and per-material readiness rows
  under the ignored `logs/farming-one-shot/` directory.

Read the final `qualification.json` and every failed phase log. A status
`OFFLINE_TESTS_PASS_LIVE_PENDING` is a successful **offline** test result
only. `SMOKE_PASS_NOT_ACCEPTANCE` and `OFFLINE_INCONCLUSIVE_DIRTY_SOURCE`
are not release approvals. Two earlier test skips requiring private game
captured assets may remain and must be explicitly accounted for.

If anything fails, diagnose the actual module and local dependency, fix the
root cause on `agent/material-first-farming`, add regression coverage and
rerun the one-shot full qualification against the corrected clean SHA. Do not
replace tests with mocks of the functionality under qualification.

## Additional source-strategy/stop acceptance (new implementation)

The source planner now returns per-material workflow candidates for
overworld, Forgery, Simulation, Tacet, synthesis and manual/event sources.
Verify in Qt, Web API and Python tests that the user sees correct
**potential** source families and relevant Waveplate/material-consumption
warnings. The planner must never select a provider, request a route file,
issue input or mark a reference-only material executable.

Validate `farming_stop_policy.evaluate_stop_criterion` for material inventory
totals versus mob encounter caps, unknown/stale observations, invalid
quantities, max three bounded attempts and explicit conservative stop
decisions. An unverified number below target must not trigger automatic
continuation. Check that mode changes in BOTH UIs clear an old search filter.

The one-shot runner includes `TestFarmingStrategy.py` and
`TestFarmingStopPolicy.py`, along with Qt/API integration regressions.
Repair real failures and rerun the complete exact-SHA suite before reporting
offline acceptance.

## Phase 2 — GUI and HTTP acceptance

Launch native Qt with `main.py` and standalone read-only browser with
`run-farming-web.cmd`. Note that `main_web.py` is only a Qt compatibility
alias under pinned OK Script 3.0.4, **not** a browser frontend.

In the real Windows desktop and browser:

- Check selection/filter/search of every one of the 27 screenshot materials.
- Verify the five FF Mech Core potential enemy names and their documentation
  links are separate from executable routes.
- Verify externally documented acquisition methods appear for materials that
  may come from Tacet Fields, Simulation, Forgery, synthesis, quest rewards or
  events. Their status is `REFERENCE_ONLY`; they must never be promoted to
  executable permission.
- Check goal semantics: material inventory total versus mob encounter cap.
- Verify unknown inventory is not fabricated, lack of numeric IDs is explicit,
  and Start/Pause/Stop remain blocked without current evidence.
- Test 1280×720 and actual native resolution, keyboard/focus accessibility,
  refreshing and closing/reopening tabs, missing targets, invalid inputs and
  no developer file-path leakage.
- Verify localhost HTTP rejects foreign Host and Origin values, CORS,
  non-GET methods, game-control endpoints and arbitrary file access.
- Check server shutdown/port cleanup; do not expose it through port forwarding.

Capture sanitized screenshots and application console logs in private, ignored
test storage; never commit account identifiers or private evidence.

## Phase 3 — all 27 material-source acceptance matrix

Read `docs/FARMING_MATERIAL_CATALOG.md` and compare with the current game's
inventory/material-source screen. For **each material**, record:

- Exact in-game name, language, observed numeric item identifier if available;
- observed current game version and inventory owned/target quantity;
- current game-provided source type: overworld enemy, Forgery, Tacet Field,
  Simulation, synthesis, quest/event/shop reward, or truly unresolved;
- actual enemy numeric ID and map layer if it is a mob drop;
- current available source/eligibility/cycle if it is a domain or event;
- before/after screenshots and independent OCR/readback of the SAME item;
- source evidence file hashes and review status;
- whether a safe, bounded executor already exists and what code is missing;
- `DOCUMENTED_ONLY`, `OBSERVED_SOURCE`, `ROUTE_UNQUALIFIED`,
  `LIVE_VERIFICATION_PENDING`, or `QUALIFIED` as supported by evidence.

Do not treat every item as a mob drop. Some may be non-repeatable quest rewards,
time-limited items or resources requiring spending. Never automatically use
real money, premium currency, reserve Waveplates, refill items or valuable
materials. Consult the current game UI over stale wiki descriptions.

Only after a real observed source and independent reviewed runtime permit,
test stages in order: read-only recognition, short bounded localization/walk,
one eligible combat/claim, actual inventory receipt, stop/cancellation/
input cleanup, then at most a reviewed bounded route. If the existing
`BoundedRouteTask` cannot support a confirmed material, record the gap rather
than bypassing its limits.

The fact that a material can be produced by synthesis or Forgery does **not**
mean its route should be enabled or an automatic claim should be made. Reuse
the inherited resource-policy ledger and exact budget/identity observations
for any separately approved spending test.

## Phase 4 — review, final report and release gate

Have Terra Medium independently review the final diff, module coverage,
input-ownership safeguards, privacy boundary, exact runtime evidence and
each material's actual route/source acceptance. Fix blocking defects, then
rerun affected and full tests.

Update `docs/CODEX-FARMING-QUALIFICATION-20261113.md` (append a new dated
section) and `docs/FARMING_ASSISTANT_STATUS.md`. Report:

1. Exact HEAD, clean/dirty result, Python/OK Script/Qt/Node versions;
2. exact tests passed, skipped, failed, module counts and original logs;
3. native Qt and standalone Web visual/browser findings;
4. 27-row source, route and inventory receipt matrix with explicit blockers;
5. all fixes with commits, regression evidence, and independent review;
6. per-material runnable state versus pending evidence;
7. next steps for any unresolved live gate.

**Do not claim FULLY READY or merge** if gameplay qualification is incomplete.
A successful offline test suite cannot turn reference-only wiki links or
historic screenshots into confirmed game drops. No automatic live farming should
occur without an independently approved current-runtime executor.
