# Farming Assistant QA and acceptance — 2026-11-14

## Outcome

- **Offline:** `OFFLINE_TESTS_PASS` on implementation commit `86ad99d2c129a0ad671902d2df45fcd61c37b0b1`; branch `agent/material-first-farming`; verifier started clean.
- **Qt:** `QT_BLOCKED` for full acceptance. The registered app and preview rendered; all 27 material searches/previews and the five mob candidates worked, mode/goal semantics were correct, and Start/Pause/Stop stayed disabled. Requested resize/focus/close-reopen checks were not completed.
- **Web:** `WEB_BLOCKED` for full acceptance. The standalone local app rendered and passed its 19 HTTP tests; all 27 material searches/previews and mob mode/goal checks worked. Browser console and responsive viewport checks were unavailable.
- **Live:** `LIVE_VERIFICATION_PENDING` for all 27 materials. No game input, combat, claim, synthesis, Waveplate use or inventory mutation was performed.
- **Material qualification:** `PER_MATERIAL_QUALIFIED` — none. Current-game acquisition/source IDs, authenticated inventory receipts and routes remain unverified.
- **Production:** not ready.

## Environment and exact test history

- Repository: `Z:\Game\jh-ww-farming-qualification`, canonical branch `agent/material-first-farming`.
- Starting branch commit was `f8a94eb4904b3ae73d643835afb43ea15a96002b`, clean. `git fetch origin` found `e89cba1fba424ceac0f1309a9a413603eacb23ea`; the existing farming worktree was fast-forwarded. The separate primary checkout on `qa/android-gt30pro-validation` and other worktrees were left untouched.
- No active farming writer process or matching hourly farming automation was found. The only persisted active automation was unrelated JH TCG work.
- Python `3.13.15`; `ok-script 3.0.4`; `ok-pyside-minimal 6.12.0.post2`; Node `v22.23.1`. The repository `.venv` was used.
- Initial run at `e89cba1f` (`logs/farming-one-shot/20261114T153912Z-e89cba1fb/qualification.json`) returned `OFFLINE_FAIL`: the runner could not import `src` from a direct script invocation; a completed journal identity was blocked behind an unrelated pending attempt; stale test fixtures assumed mutable `Mock.side_effect` and an outdated Tacet selector bound; one Qt test used a nonmatching hyphenated search query. Full baseline: 1,111 tests / 103 modules, two skips, four failing modules.
- Fixes were committed as `86ad99d2`: restore project root on direct-run `sys.path`; allow a completed journal identity to return before the cross-source pending gate; permit only cross-site top-level GET navigation of the static web shell while continuing to reject cross-site APIs; correct the affected regression fixtures and selector query.
- Targeted retests on the fixed tree: `TestFarmingOneShot` 11/11; `TestResourceGoals` 38/38; `TestResourceRoutineTask` 28/28; `TestFarmingAssistantQt` 9/9; `TestDeathReentry` 12/12; `TestFarmingStandaloneWeb` 19/19. Python compilation, JavaScript syntax checks and `git diff --check` passed.
- Final full command on clean `86ad99d2`: `\.venv\Scripts\python.exe scripts\qualify_farming_one_shot.py`. Result: `OFFLINE_TESTS_PASS_LIVE_PENDING`; 1,112 tests across 103 isolated modules, 1,110 passed, two existing private-capture skips, zero failed modules. All 21 runner phases passed. The exact report is `logs/farming-one-shot/20261114T155152Z-86ad99d2c/qualification.json`; full module logs are alongside it.
- GUI launch: `\.venv\Scripts\python.exe main.py` opened the actual OK-WW app. It reported a Wuthering Waves connection profile at 1920×1080. The app’s Start control was not pressed.
- Web launch: `\.venv\Scripts\python.exe main_farming_web.py --no-browser` bound to `127.0.0.1` on an ephemeral port. Browser search found and fixed a real launch issue: a cross-site top-level navigation was rejected. The updated server permits only a document navigation to `/` without an Origin header; cross-site API calls remain rejected. The server was stopped; no listener remained.

## Native and browser UI results

- Native Qt rendered in the registered OK-WW application. Actual Qt search returned exactly one matching material and updated its preview for every catalog material. The five possible FF Mech Core candidates were present and marked informational only. Switching to Mobs cleared the material search, showed the five mob candidates, changed the goal to “Maximum mob encounters,” and kept observed encounter progress unknown. Start/Pause/Stop were disabled in both modes.
- The standalone browser rendered after the landing-navigation fix. All 27 material searches returned one selected preview; the five mob candidates rendered; the goal changed to encounter limit; action buttons stayed disabled. HTTP regression coverage checked loopback binding, Host and Origin rejection, cross-site API rejection, safe document landing, unsupported methods, arbitrary parameters, traversal/private paths, and absent gameplay endpoints.
- `agent-desktop` and `agent-browser` CLIs were not installed, so native/browser interaction used the available CUA surface. The game window is elevated above the helper’s integrity level: only its window shell could be read, not its rendered game screen. No elevation or workaround was attempted.
- Qt and web screenshots were visually inspected inline during the session, but the available CUA screenshot interface did not expose a local save path. No live-game screenshot exists. Browser console logs and viewport resizing to 1280×720 / 1920×1080 were not completed. The Qt capture was a 1200×930 app window; the connection label reported a 1920×1080 game profile, which does not substitute for resized UI coverage.

## 27-material acceptance matrix

“UI” records local selector/preview checks in native Qt and the browser. Every potential provider below remains a reference-only candidate; `selected_provider` is null for each preview. “Current-game source” and “inventory receipt” mean independently observed in the running game, not a guide claim or synthetic test fixture.

| # | Material | UI | Reference source categories | Potential provider (not qualified) | Current-game source / item ID | Inventory evidence | Route | Remaining blocker |
|---:|---|---|---|---|---|---|---|---|
| 1 | Premium Tuner | Pass, both | Tacet Field; synthesis; exploration/quest | TacetTask candidate; manual conversion/reward | Not observed / unknown | None | Not qualified | Game screen inaccessible; exact source, ID and receipt missing |
| 2 | Premium Sealed Tube | Pass, both | Tacet Field; exploration/quest | TacetTask candidate; manual reward | Not observed / unknown | None | Not qualified | Game screen inaccessible; exact source, ID and receipt missing |
| 3 | Premium Resonance Potion | Pass, both | Simulation Training; exploration/quest | SimulationTask candidate; manual reward | Not observed / unknown | None | Not qualified | Game screen inaccessible; current challenge and receipt missing |
| 4 | Heterized Metallic Drip | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 5 | Mysterious Code | Pass, both | Casket Delivery / quest | No automatic provider | Not observed / unknown | None | Not qualified | Current availability and repeatability unknown |
| 6 | FF Whisperin Core | Pass, both | Whisperin mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 7 | FF Howler Core | Pass, both | Howler mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 8 | Tailored Ring | Pass, both | Exile mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 9 | Mask of Insanity | Pass, both | Fractsidus mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 10 | Flawless Phlogiston | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 11 | Presto Helix | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 12 | Waveworn Residue 239 | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 13 | Cadence Blossom | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 14 | Premium Energy Core | Pass, both | Simulation Training; exploration/quest | SimulationTask candidate; manual reward | Not observed / unknown | None | Not qualified | Game screen inaccessible; current challenge and receipt missing |
| 15 | FF Tidal Residuum | Pass, both | Dark Tide mob; synthesis; Forgery Challenge | BoundedRouteTask / ForgeryTask candidates | Not observed / unknown | None | Not qualified | Enemy/challenge identity, receipt and route missing |
| 16 | FF Polygon Core | Pass, both | Clamoring/Tranquilite mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 17 | Echo Modifier | Pass, both | Event/exchange; exact item label uncertain | No automatic provider | Not observed / unknown | None | Not qualified | Exact item identity and current availability unknown |
| 18 | FF Exoswarm Core | Pass, both | Exoswarm mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 19 | Reverb Combustor | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 20 | FF Mech Core | Pass, both | Clamorling mob; synthesis; Forgery Challenge | BoundedRouteTask / ForgeryTask candidates | Not observed / unknown | None | Not qualified | Five names remain community candidates; numeric IDs, drop receipt and route missing |
| 21 | Intact Exoswarm Pendant | Pass, both | Roya Outcast mob; synthesis | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |
| 22 | Layered Wing Polarizer | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 23 | Melodic String | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 24 | FF Carved Crystal | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 25 | FF Waveworn Shard | Pass, both | Forgery Challenge; synthesis | ForgeryTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Game screen inaccessible; challenge, debit policy and receipt missing |
| 26 | Transducer | Pass, both | Historical limited subscription | No automatic provider | Not observed / unknown | None | Not qualified | Current availability and item identity unknown |
| 27 | FF Autopuppet Kernel | Pass, both | Autopuppet mob; synthesis/conversion | BoundedRouteTask candidate; manual conversion | Not observed / unknown | None | Not qualified | Enemy ID, actual drop, inventory receipt and route missing |

## Independent review and outstanding acceptance

- The exact source/test diff is committed at `86ad99d2`. Independent Terra review has not yet been recorded in this report; do not treat the available test results or this coordinator’s review as an independent approval.
- Do not spend Waveplates, claim rewards, synthesize, consume items, or issue gameplay inputs until exact current-game source identity, budget and independent runtime gates are satisfied.
- To progress live acceptance, run the game UI through a same-integrity approved desktop helper, observe current client/runtime versions and material item pages, collect distinct pre/post inventory evidence, and have Terra review the exact sources and evidence before any bounded interaction.

## 2026-11-15 continuation — pushed branch and live UI acceptance

### Exact Git state

- Reviewed and pushed the three previously unpushed commits on
  `agent/material-first-farming`: `86ad99d2`, `d616b70b`, and `10939cb0`.
- Push was a normal fast-forward from `e89cba1f` to
  `10939cb018d979405d5c488d6cded1ae78a2a131`. `git ls-remote` confirmed the
  origin branch at that exact SHA. No other branch, worktree, or pull request
  ref was changed; no force push was used.
- Unrelated PR #4 remains open and draft at its existing head
  `e06a9fb7`; it was read for state confirmation only.
- The full offline suite was not repeated. The prior qualification at
  `86ad99d2` remains the evidence for 1,110 passed, two skipped, and 21/21
  phases; it predates the new CSS fix. The post-fix candidate received the
  focused Web regression (19/19) and JavaScript syntax check only.
- Local versions observed during this continuation: Python 3.13.15,
  `ok-script` 3.0.4, `ok-pyside-minimal` 6.12.0.post2, and Node v22.23.1.

### Native Qt and standalone Web

- **Qt per-material search/selection/guard-state: PASS (27/27).** In the
  registered OK-WW Qt app, each catalog material was searched individually.
  Each exact query produced its matching preview heading and one matching
  filtered list item. A second focused pass verified unmeasured inventory, no
  local receipt/route, and disabled Start/Pause/Stop controls for all 27
  previews. The OK-WW app was already running and was not restarted; the UI
  source itself did not change in the three pushed commits, so its loaded SHA
  was not separately pinned.
- **Standalone Web per-material search/selection/guard-state: PASS (27/27).**
  The real page was served from `127.0.0.1:51332`. Each exact query produced a
  selected list row and matching preview heading; all three execution controls
  remained disabled and the preview continued to state that no provider was
  selected.
- **Representative visual checks: PASS.** Qt screenshots sampled FF Mech Core
  and its read-only preview; Web screenshots sampled FF Mech Core and the
  narrow layout. The full 27-by-2 per-material screenshot review remains
  **BLOCKED / incomplete**; the 27-row UI matrix records functional state, not
  a separately inspected screenshot for every row.
- **Mode semantics: PASS (both UIs).** Switching to Mobs cleared the material
  search. Qt and Web showed the five documented FF Mech Core candidate names
  as informational/unqualified, used the maximum-encounter goal, and reported
  encounter progress as unobserved. Returning to Materials restored the
  FF Mech Core reference-only preview.
- **Web reload/reopen and server cleanup: PASS.** The page survived reload and
  a close/reopen cycle. After stopping the preview server, no listener remained
  on port 51332.
- **Observed layouts:** Qt was inspected windowed at 1200x930 and maximized at
  1920x1080; the latter matched the visible desktop resolution. The initial Web
  capture at 306x858 exposed a real row-height defect: the selected row's
  source-status subtext extended below its button border. The rule was fixed to
  prevent flex shrinking, and a fresh 1265x858 Web capture showed the full row
  inside its border. A same-size post-fix 306x858 capture and exact 1280x720
  test remain **BLOCKED** because the available CUA surface exposes no viewport
  override, the browser CLI is not installed, and the native window screenshot
  surface refused a resize endpoint outside its 1200-pixel capture bounds.
  Browser console logs, keyboard-only focus, and native Qt close/reopen were not
  completed. The existing OK-WW runner was left open to avoid interrupting its
  live session.
- **Screenshots:** Qt 1200x930 and 1920x1080 and post-fix Web 1265x858 captures
  are visible in this QA conversation. CUA did not provide a local export path,
  so there is no private screenshot bundle or file hash to cite. The initial
  306x858 Web capture shows the defect and is not post-fix evidence. A game
  capture included a visible account identifier and unrelated desktop content;
  it is excluded from evidence and was not persisted or linked.

### Integrity diagnosis and live-game gate

- **Privilege diagnosis: PASS; game observation/input: BLOCKED.** The existing
  read-only `src.overworld.input_access` token query reported the game process
  as `(elevated=True, UIAccess=False)`, the OK-WW process as
  `(False, False)`, and the observer as `(False, False)`. The existing
  `require_game_input_access` guard rejected the current game window before
  input with its administrator-integrity mismatch message. CUA likewise
  reported that the game window has higher integrity than its helper and
  exposed only the window shell. No elevation, UIAccess change, security
  workaround, gameplay input, or game-state modification was attempted.
- The installed game executable's Windows file-version metadata was blank,
  and the current in-game version, item details, and inventory pages could not
  be read. The connection pill's 1920x1080 profile is not a game-version
  observation.
- **FF Mech Core current source, inventory receipt, and route: BLOCKED.** Its
  five candidate names remain community/reference-only. No numeric item or
  enemy ID, current-client source page, distinct inventory delta, map layer,
  route, or independent runtime permit was obtained. No bounded live action
  was eligible to start.
- **The other 26 materials: BLOCKED for source-specific live acceptance.**
  Their UI previews passed, but their exact current-game identities, source
  availability/repeatability, inventory receipts, and routes were not
  observable. This leaves source families unresolved where the running game
  has not confirmed them; no material is assumed farmable or repeatable.
- No Waveplates, refill items, synthesis, claims, premium currency, or other
  resources were spent. No unsafe execution was enabled.
- **Terra Medium review: PASS for source/report review.** The independent
  reviewer confirmed the offline-run provenance and found no further blocking
  source defect after the CSS correction. It did not independently view the
  later sibling-session screenshot and did not approve any live source, receipt,
  route, or runtime permit.

### Updated 27-material acceptance matrix

`PASS` in the UI columns means selector/search/accessibility-preview state
acceptance only; screenshot inspection was representative, not a per-row visual
review.
`BLOCKED` in the live columns means current-game evidence could not be read;
it does not assert that the source is absent or non-repeatable.

| Material | Qt preview | Web preview | Current source / item ID | Inventory receipt | Calibrated route |
|---|---|---|---|---|---|
| Premium Tuner | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Premium Sealed Tube | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Premium Resonance Potion | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Heterized Metallic Drip | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Mysterious Code | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Whisperin Core | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Howler Core | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Tailored Ring | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Mask of Insanity | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Flawless Phlogiston | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Presto Helix | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Waveworn Residue 239 | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Cadence Blossom | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Premium Energy Core | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Tidal Residuum | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Polygon Core | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Echo Modifier | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Exoswarm Core | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Reverb Combustor | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Mech Core | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Intact Exoswarm Pendant | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Layered Wing Polarizer | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Melodic String | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Carved Crystal | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Waveworn Shard | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| Transducer | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |
| FF Autopuppet Kernel | PASS | PASS | BLOCKED | BLOCKED | BLOCKED |

### Final status

- Offline qualification: **PASS at baseline SHA `86ad99d2`** (1,110 passed,
  two skipped, 21/21 phases); full suite not rerun after the CSS fix.
- Three-commit push: **PASS**, origin SHA verified.
- Qt and standalone Web all-27 search/selection/guard-state: **PASS**;
  representative visual checks: **PASS**; full per-material visual review:
  **BLOCKED / incomplete**.
- 1280x720, browser console, Qt keyboard/focus, and Qt close/reopen gates:
  **BLOCKED / incomplete** as detailed above.
- Game integrity diagnosis: **PASS**; live observation, FF Mech Core source /
  receipt / route, and the other 26 materials' live source acceptance:
  **BLOCKED**.
- Terra Medium source/report review: **PASS**, with no further blocking finding;
  no live evidence was approved.
- One narrow-Web selector row defect was found and fixed in
  `src/web/farming_assistant/index.js` with `flex:0 0 auto`; the focused 19-test
  standalone Web regression module and JavaScript syntax check passed after
  the change. The post-fix real-browser screenshot at 1265x858 confirms the row
  text stays inside its border. Production readiness remains **NOT READY**; do
  not enable or claim live farming.
