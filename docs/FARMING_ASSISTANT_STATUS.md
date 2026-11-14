# JH Wuthering Waves — Farming Assistant implementation status

## 2026-11-14 — cultivation Guidebook side-item reconciliation (GitHub-only)

- **Follow-up correctness fix:** The earlier deficit-only dispatch change revealed an interaction with `CultivationTask`: its Guidebook row matcher expected every displayed material, including already-satisfied side items, to be queued. `src/task/CultivationTask.py` now permits omitted **observed and fully satisfied** side items while rejecting a missing active material, unknown name, duplicate requested name, stale quantity or mismatched native requirement. It does not weaken fresh Guidebook item-detail checks.
- **Receipt boundary:** Before confirming a prepared Waveplate claim, the actual post-claim inventory must increase for at least one **previously unmet** cultivation material. A gain in a satisfied side item alone leaves the claim `UNCERTAIN` rather than reporting a confirmed target receipt.
- **Commits:** code `d086caf327915dfce8840978e856415f728e4ed6`; tests `87f084d1f0cc0c3c092115936592e59424a996e5`, precise-exception refinement `bb48789ad53a6c069d1461a0cf1d0d3085ff91bf`; deferred one-shot runner `425cb9419de8f667bc5059dcaa285a290d43f813`. Canonical branch `agent/material-first-farming`.
- **Focused offline contracts added:** `tests/TestCultivationTask.py` covers satisfied Guidebook side items, unrequested missing items, stale inventory, and target-only receipt confirmation. `tests.TestCultivationTask` and both changed Python files are now included in the existing single-run Codex acceptance workflow.
- **Verification:** GitHub source updates/readback only; Python/Windows/Qt/browser/live game and independent Terra **NOT RUN**. Codex later runs `.\\.venv\\Scripts\\python.exe -m unittest tests.TestResourceRoutineTask tests.TestCultivationTask -v`, then the consolidated `run-farming-one-shot.cmd`.
- **Status:** `BLOCKED_FOR_LIVE_QUALIFICATION`; all 27 materials remain reference-only or read-only where not independently qualified. Domain provider adapters, current-game challenge observations, source/route authorization and per-claim spending approval remain blocked. No live input or resource spending occurred.
- **Next:** exact current-game challenge identity and selector binding for Forgery/Simulation/Tacet, followed by receipt-aware resource-ledger adapters; do not enable inherited generic spending loops on static selector evidence.

---

## 2026-11-14 — exclude completed materials from dispatch receipts (GitHub-only)

- **Starting HEAD:** `f41d97317a89ebcdac3437687257f83a1d09e148`; code commit `59d951246dd82550443079035a54cae459a528ca`; focused contracts `18fb8e63ae57cf1f5519ed3d5a190c47de6a0554`, all on `agent/material-first-farming`.
- **Fixed:** The material-goal loop previously included already-satisfied goals in same-provider receipt batches. An unrelated inventory increase for a satisfied material could satisfy the generic *any increase* check even though an unmet goal had not progressed, and change the attempt fingerprint for another retry. Only goals with a current deficit are now included. The selected goal must be part of that unique qualified binding.
- **Preflight:** A `BoundedRouteTask` provider shared by multiple **unmet** materials now rejects before target inventory observation and attempt-journal creation, rather than recording an `UNCERTAIN` attempt after a dispatch-shape error. This does not authorize or calibrate any route.
- **Contracts added:** `tests/TestResourceRoutineTask.py` covers exclusion of completed goals, rejection of incidental completed-goal receipts, and early multi-material route rejection. Existing one-shot runner already includes `tests.TestResourceRoutineTask`; no extra runner or evidence wrapper created.
- **Verification:** GitHub file commits/readback only; Python unit tests, Windows/Qt/browser/game and independent Terra review **NOT RUN**. No live game, navigation, resource spend or new material source authorization.
- **Release gate:** `BLOCKED_FOR_LIVE_QUALIFICATION`. Community acquisition links and 27 catalog materials remain informational, domain provider adapters remain blocked, independent route and spending gates unchanged.
- **Next increment:** audit current-game challenge identity-to-selector binding and per-claim ledger/actual inventory receipt adapters for Forgery, Simulation and Tacet without enabling execution on static selector shape alone. Later Codex runs `.\\.venv\\Scripts\\python.exe -m unittest tests.TestResourceRoutineTask -v` and one consolidated `run-farming-one-shot.cmd`.

---


## 2026-11-14 — reject invalid F2 challenge selectors before any inherited navigation (GitHub-only)

- **Starting SHA:** `604a4c88391925dcbd45052c95a6a2256783d946` on `agent/material-first-farming`; see latest live branch HEAD for this increment's commit.
- **Code:** New `src/automation/domain_selection.py` performs strict Forgery (1..20), Tacet (1..21) and Simulation (three declared choices) selector-shape validation, with layout-drift checks on the numbered tasks. The inherited `run`, `farm_*` and F2 navigation entry points now reject malformed values, booleans, zero, out-of-range and unknown Simulation selections **before their initial game input**. Previously an invalid Simulation value could silently select Shell Credit, and nonpositive Forgery/Tacet indices could reach F2 navigation.
- **Diagnostics:** `ResourceRoutineTask` preview additionally labels missing, malformed, or structurally valid local domain selectors; even a valid selector is marked `CURRENT_GAME_CHALLENGE_UNOBSERVED`. `PROVIDER_ADAPTER_PENDING` remains a hard execution block for all domain material goals. No gameplay or spending has been enabled; no static option identifies a current-game source.
- **Focused contracts:** Added `tests/TestDomainSelection.py` for selection bounds, shape-only diagnostics and no-input rejection at native navigation entry points, and included it and changed Python files in the deferred one-shot Codex runner. **Tests NOT RUN** in GitHub-only environment; no Windows/Qt/game validation or independent Terra review.
- **Status:** `BLOCKED_FOR_LIVE_QUALIFICATION`. The next meaningful work is fresh challenge identity/selector evidence and per-claim debit + actual inventory receipt adapters, with independent spending gates; do not bypass the existing domain adapter block. Codex later runs `.\\.venv\\Scripts\\python.exe -m unittest tests.TestDomainSelection tests.TestResourceRoutineTask -v` before the consolidated `run-farming-one-shot.cmd`.

---


## 2026-11-14 — prevent unadapted domain material-goal spending (GitHub-only)

- **Reviewed live baseline:** `1765fe01dcb9d71a7ca0470d9011058f1bb86840` on `agent/material-first-farming`. Code/test commits: [`6ff2b327`](https://github.com/jonhue1403/jh-wuthering-waves/commit/6ff2b327d9148858b71e37b14a996ded2ed576a6), [`e2b5dfbd`](https://github.com/jonhue1403/jh-wuthering-waves/commit/e2b5dfbd75c38e51f276f5d116c0104a7d1a1ade), [`94e3be79`](https://github.com/jonhue1403/jh-wuthering-waves/commit/94e3be797531fe573ef55262bf61c5c310fe2464), and allowlist hardening [`f57f439d`](https://github.com/jonhue1403/jh-wuthering-waves/commit/f57f439d74728faa5ef73039a2db75680466fd97). Always re-read live branch HEAD before writes.
- **Audit finding and code fix:** The inherited `ForgeryTask`, `SimulationTask` and `TacetTask` still call generic `use_stamina` and do **not** journal each debit and observed material receipt via the injected shared `ResourceLedger`; they also do not prove the selected native challenge ID matches the requested material. Previous plan/source flags could select them as if the attached ledger made them goal-safe. They now fail closed for **material-goal execution**, before framework session startup and journal attempt creation. Direct `_dispatch` calls with queued goals also reject before inherited task lookup, including unknown/non-goal executors such as `DailyTask`. Only `CultivationTask` and `BoundedRouteTask` are currently recognized as material-goal adapter *candidates*, never pre-authorized execution. This does **not** assert that ordinary inherited routine runs are safe; their spending boundary requires separate audit.
- **Preview clarity:** `ResourceRoutineTask` exposes `Material provider readiness`: `PROVIDER_ADAPTER_PENDING` for those three domain producer candidates, `CANDIDATE_ONLY` for existing adapted tasks and `UNRESOLVED` for ambiguous/unqualified source mappings. The existing structural source status `READY` is intentionally **not** live execution authorization. Read-only journal reconciliation remains available even when a domain material adapter is blocked.
- **Focused regression additions:** tests cover each of the three domain producers refusing before any child lookup/input, preview block diagnostics, pre-session fail-closed behavior (no identity observation, child task or journal), and reconciliation-only allowance. The consolidated later Codex runner now includes `tests.TestResourceRoutineTask` and compiles both modified task/test files.
- **Verification:** GitHub commits and source readback only. Python unit tests, Qt, Windows, browser, live gameplay and independent Terra review **NOT RUN**; no game launched, inputs sent, rewards claimed or Waveplates spent.
- **Status:** `BLOCKED_FOR_LIVE_QUALIFICATION`. The 27 references remain selection-only; no challenge identity, route, verified current-game material receipt or independent spending approval has been established.
- **Next scoped developer increment:** specify and validate exact **observed native challenge identity + selector value** for Forgery/Simulation/Tacet against the captured, current-runtime task config, then implement *per-claim* ledger preparation/confirmation and post-inventory observation before permitting domain goal execution. Never enable by merely flipping the adapter gate. Codex later runs `.\\.venv\\Scripts\\python.exe -m unittest tests.TestResourceRoutineTask -v` and ultimately the one-shot `run-farming-one-shot.cmd` on the real Windows checkout.

---

## 2026-11-14 — durable goal dispatch journal and pre/post-inventory gates (GitHub-only)

- **Code changes:** [`0d70a8ac82d3a46c71d030088e5e808d53809d81`](https://github.com/jonhue1403/jh-wuthering-waves/commit/0d70a8ac82d3a46c71d030088e5e808d53809d81), followed by a same-scope source-binding/test correction on `agent/material-first-farming` (read live HEAD before further work).
- `ResourceRoutineTask` records a durable **PENDING material-goal attempt before inherited dispatch**, keyed by observed account/server/cycle, exact provider kind/task/profile/evidence/runtime, all selected material names and actual pre-dispatch inventory counts. Interrupted, cancelled or unverified attempts become **UNCERTAIN** rather than silently reissuing combat or a claim. Only fresh same-identity post-observation with actual target inventory progress can mark the attempt COMPLETE. Changed verified inventory establishes a different attempt key if a deficit remains.
- Source batching now includes *only uniquely mapped goals sharing the exact producer binding*. An ambiguous mapping, mismatched source evidence, or missing/mismatched baseline for any batched material cannot authorize an inherited dispatch. Unresolved prior spending also blocks a new attempt.
- Added focused contract tests for fingerprint changes, uncertain replay, incomplete batch baseline and confirmed positive inventory receipt in `tests/TestResourceRoutineTask.py`. Synthetic observations in these tests **are not actual game evidence**.
- **Verification performed:** GitHub source commits and file readback only. **Tests NOT RUN** (Python/Qt/Windows/browser/game); no Antigravity CLI or independent Terra review invoked, no game launched, no claims or premium currency spent.
- **Status:** `BLOCKED_FOR_LIVE_QUALIFICATION`. Existing 27 read-only materials and disabled UI execution controls remain unchanged; current-game provider identities and executable route/spend permissions are still missing.
- **Next targeted increment:** audit and bind Forge/Simulation/Tacet challenge identity + selected task configuration to a fresh qualified provider observation before any planned source dispatch. Run `.\\.venv\\Scripts\\python.exe -m unittest tests.TestResourceRoutineTask -v` and later the consolidated `run-farming-one-shot.cmd` in the Codex Windows checkout.

---

## 2026-11-14 — enforce real resource-source/provider compatibility (GitHub-only)

- **Base:** `b8e9fa64ab3bb2551d3815ec90167c6f16c1534d`; **source + regression commit:** `0c44695d2d43c67d1c16591a266a30a1507acf3f` on `agent/material-first-farming`.
- `src/automation/goals.py` now accepts only the correct **source kind -> inherited executor** mapping: boss -> `CultivationTask`; overworld -> `BoundedRouteTask`; domain -> `ForgeryTask`, `SimulationTask`, or `TacetTask`. This closes a planning/dispatch mismatch where a wrong class could be selected from otherwise plausible local metadata. No synthesis, historical event/quest or boss-Echo task can masquerade as a repeatable mob route.
- Only a literal `qualified is True` can match, and runtime, evidence and profile fields must be meaningful strings. This is a **necessary matching filter, not an authorization**: local `qualified` flags and SHA checks do NOT independently qualify current-game routes, permit spending, or prove a receipt.
- Resource-goal preview now explains whether mappings are missing, ambiguous or merely candidates that still require inherited current-runtime identity, input, budget and receipt gates. It preserves the existing `READY` status for structurally matched candidates but explicitly says that this **does not mean live-ready**.
- Three focused regressions added to `tests/TestResourceGoals.py` for 12 compatible/incompatible pairs, truthy/missing qualification and preview gate clarity. The deferred one-shot Codex runner now runs that test module separately and compiles the modified code/tests.
- **Tests actually run:** NONE — GitHub source writes/readback only; Windows/Python/Qt/browser/full suite/game and independent Terra review **NOT RUN**. No input or spending was attempted; no master, PR #4, or unrelated worktree changed.
- **Status:** `BLOCKED_FOR_LIVE_QUALIFICATION`. The 27 screenshot materials and their informational source methods remain read-only. No source has an independently approved current-game provider/route or validated before/after receipt. UI Start/Pause/Stop remain disabled.
- **Next scoped change:** inspect the existing resource-policy and exact per-producer runtime preflight for any remaining source/route or budget cross-gate omissions. Do not invent source IDs or add more capture wrappers. Codex later runs `.\\.venv\\Scripts\\python.exe -m unittest tests.TestResourceGoals tests.TestResourceRoutineTask -v` and the existing `run-farming-one-shot.cmd` consolidated Windows acceptance.

---

## 2026-11-14 — receipt/cancellation race hardening (GitHub-only)

- **Base:** `f0f23e57f5393a73028ccd2b3d3c39ba81d80417` on
  `agent/material-first-farming`.
- **Implementation:** `135600c88ab7ea197982043d04499dd10f572ae1`
  changed `src/overworld/material_route.py` to honor boolean cancellation
  before issuing a pickup, after pickup and on both sides of inventory
  observation. Previously, ignoring a returned `True` could allow new
  UI input after Stop. The controller now owns the single CLEARED transition,
  rather than receiving an early duplicate from `camp_cleared`.
  A camp receipt requires an observed baseline; cancellation never adds a
  new receipt or treats an issued pickup/combat clear as a reward.
- **Synthetic contract tests:** `6535784d54070b8847e762a828f15ac97c2e1baa`
  added five tests to `tests/TestMaterialRoute.py`: cancellation before
  pickup; cancellation during pickup; cancellation during inventory read;
  missing baseline; and exactly one CLEARED transition per camp.
- **One-shot integration:** `f571cb95016501406bddb9c88ddf77c26a3c0173`
  added `tests.TestMaterialRoute` as a focused run and compiled both
  modified code/test files within `scripts/qualify_farming_one_shot.py`.
- **Execution:** NOT RUN. GitHub connector writes and static source inspection
  are not Windows/Python/Qt/game tests, live inventory or independent review.
  Do not spend Waveplates or launch the game in this automation.
- **Blocking state:** `BLOCKED_FOR_LIVE_QUALIFICATION`. Exact current-game
  item/enemy identities, available reward/source identity, native inventory
  receipts, source-specific runtime qualification and independent route/spend
  authority remain missing. No new material becomes executable; browser
  remains localhost-only and read-only; Qt Start/Pause/Stop stay disabled.
- **Next:** valuable targeted review of existing provider dispatch and
  resource ledger, without inventing any source approval. Codex later runs
  `run-farming-one-shot.cmd` once on a clean exact-SHA Windows checkout,
  verifies both UIs and investigates source-specific current-game gates.

---


## 2026-11-14 — immediate source-aware strategy / bounded stop implementation

User requested proceeding immediately instead of waiting for the hourly run.
Changes were committed directly on `agent/material-first-farming` after
reading the current remote head. The existing automation and PR #4/master
were not edited in this immediate implementation turn.

- Added `src/automation/farming_strategy.py`: explicit, typed provider
  candidate mapping (overworld `BoundedRouteTask`; Forgery, Simulation,
  Tacet inherited tasks; synthesis and manual/quest/exchange/event sources
  have **no** automatically supported executor). Every candidate remains
  `CURRENT_GAME_EVIDENCE_REQUIRED`, without any route selection,
  source spending authorization, game input or task dispatch.
- Added `src/automation/farming_stop_policy.py`: deterministic
  `INVENTORY_TOTAL` versus `ENCOUNTER_LIMIT` stop-first evaluation;
  missing observations, reaching the goal and hitting the maximum three
  bounded attempts are explicit outcomes. Neither a goal deficit nor a
  reference-only source permits auto-continue. UI previews remain
  `PLANNED_ONLY`, unobserved and non-executable.
- `FarmingAssistantView.preview` now exposes a path-free
  `acquisition_plan` and common stop-policy fields while preserving the
  previous response contract. Unknown/extension materials without a
  research record get a safe empty plan instead of causing source lookup
  errors; regular 27-item catalog remains unchanged.
- The native Qt and standalone browser views now show possible
  workflow families and warn about possible Waveplate costs. They
  NEVER enable Start/Pause/Stop or send game input. Switching target
  modes clears stale search text in both UIs, fixing an apparent-empty-list
  defect.
- Added `TestFarmingStrategy.py`, `TestFarmingStopPolicy.py` and
  focused Qt/view/HTTP regressions. The one-shot Codex runner now includes
  the strategy and stop tests and checks that all 27 material plans remain
  blocked. `docs/FARMING_MATERIAL_CATALOG.md` and
  `docs/CODEX_FARMING_ONE_SHOT_ACCEPTANCE.md` record new acceptance gates.
- **Tests actually executed in this GitHub connector environment: NONE.**
  No Windows checkout, OK Script runtime, real browser, Antigravity CLI
  or Terra Medium desktop session is attached. Successful GitHub
  commits and static readback are not test execution.
- **Critical remaining dependency:** authentic current-game source identity,
  item and enemy numeric IDs, relevant available challenge/route,
  independently reviewed current-version runtime qualification, real
  same-item before/after inventory receipt, and bounded live execution
  acceptance. `LIVE_VERIFICATION_PENDING` remains the accurate status.

**Next:** implement internal, safe provider selection under real current-runtime
qualification in the existing executor, not the read-only browser; do not
convert documentary links or caller-supplied flags into authorization.
Then run `scripts/qualify_farming_one_shot.py` once from the Codex Windows
checkout after final implementation and independently review live evidence.

---


## 2026-11-14 — source-category research, acquisition guidance and one-shot Codex QA

- Added `src/automation/farming_acquisition_reference.py` with community/guide
  reference URLs and possible acquisition methods for **all 27 screenshot
  materials**, differentiated into MOB_DROP, FORGERY_CHALLENGE,
  SIMULATION_TRAINING, TACET_FIELD, SYNTHESIS, EXPLORATION_OR_QUEST,
  EVENT_OR_EXCHANGE and HISTORICAL_SUBSCRIPTION. All are strictly
  `REFERENCE_ONLY` and `NOT_OBSERVED_CURRENT_GAME`. The special historical
  Transducer subscription is not presumed currently available; "Echo Modifier"
  identity versus the community "Modifier" entry needs in-game confirmation.
- The view, native Qt and standalone Web now show possible acquisition methods
  and their documentation references. This prevents a quest/Simulation/Forgery
  item from being treated as a mob drop just because it appears on the farming
  screen. The 27 existing catalog targets, FF Mech Core five possible named
  enemies, source/route qualification and all disabled gameplay buttons remain
  unchanged.
- Added regressions `TestFarmingAcquisitionReference.py` plus new view,
  Qt and HTTP API coverage. The real game has **not** been observed or
  controlled by this GitHub-only implementation session.
- Added `scripts/qualify_farming_one_shot.py`, `run-farming-one-shot.cmd`,
  and `tests/TestFarmingOneShot.py` for a single Codex-run offline
  qualification campaign. The runner records exact Git SHA/cleanliness,
  27 material previews and reference kinds, Python/Node checks, isolated
  focused suites, complete separate-process full suite, per-module counts,
  logs and separate unqualified live gates. It refuses to label a dirty
  incomplete run as offline acceptance.
- Added `docs/CODEX_FARMING_ONE_SHOT_ACCEPTANCE.md`, and updated the
  27-row `docs/FARMING_MATERIAL_CATALOG.md` with URL-backed possible
  acquisition methods. They are documentary hints, not executable providers.
- **Tests not executed in this connector-only implementation session**:
  Windows/Python/Qt/Node/browser/live game, individual 27 material
  receipts, route permissions and independent Terra review are still
  pending. The previous measured full run from Codex remains the most
  recent verified run until the new one-shot suite is actually executed.
- The existing hourly JH Wuthering development automation was explicitly
  resumed on the owner's renewed instruction to continue implementation,
  not duplicated. It is to focus on real code/UX readiness; Codex will
  own a consolidated local acceptance run later.

**Next:** finish internal verified-source/producer dispatch integration
without enabling unreviewed gameplay; then Codex executes the one-shot
offline suite, both actual UIs, independent Terra review and material-specific
current-game evidence. Full live farming remains
`LIVE_VERIFICATION_PENDING`.

---


## 2026-11-14 — 27 screenshot materials added to the Farming Assistant catalog

- Transcribed the user's 9×3 in-game material grid into 27 explicit material
  names and stable UI slugs in `src/automation/farming_selection.py`.
  This adds 26 material entries beyond the existing FF Mech Core.
- All items are searchable/selectable through shared `FarmingAssistantView`
  on both the native Qt tab and standalone localhost browser. FF Mech Core
  remains featured first in the unfiltered list to preserve the prior default
  preview. Material goal semantics remain `INVENTORY_TOTAL`.
- Preserved FF Mech Core's five **documented-only** enemy candidates. No drop
  sources, item IDs, acquisition methods, map positions or routes were invented
  for the other 26 materials. Their status is `SOURCE_UNRESOLVED`.
- Added/updated regressions in `TestFarmingSelection.py`,
  `TestFarmingAssistantView.py`, `TestFarmingAssistantQt.py` and
  `TestFarmingStandaloneWeb.py` for all 27 entries, spelling, uniqueness,
  read-only API/search, stop-target semantics and disabled controls.
- Recorded every material and the exact individual Codex qualification gates
  in `docs/FARMING_MATERIAL_CATALOG.md`. Do not equate showing a material
  in the list with possessing a runnable farm route. Some items may not be
  enemy drops; classify only from real current-game evidence.
- **Verification in this connector-only run:** GitHub commits/readback and
  static consistency checks; actual Python, Qt, browser, Windows and game tests
  **NOT RUN**. Container `git ls-remote` could not resolve github.com. The user
  intends Codex to perform the local qualification later.
- No gameplay input, spending, merge, master update or independent Terra review.
  The previous hourly development automation remains paused.

**Next:** Codex runs all new target-list tests and both UI smoke tests; then
verifies each material's genuine in-game source type, numeric ID, actual
inventory receipts and applicable current-runtime routes individually.
See `docs/FARMING_MATERIAL_CATALOG.md` for the exact list and commands.

---


## 2026-11-14 — standalone read-only web server implementation (FQ-01)

- Removed unsupported OK Script 3 `web_tabs` registration from `config.py`. The previously failing `TestConfig` case now checks the actual standalone server and confirms the old web task is not registered. Preserved Qt `custom_tabs`, `main.py` and the legacy `main_web.py` Qt compatibility alias.
- Added `main_farming_web.py`, `run-farming-web.cmd`, `src/automation/farming_web_server.py` and the minimal standalone HTML/CSS/JS adapter around the existing ES-module `index.js`. Uses only the shared path-free `FarmingAssistantView`, two read-only GET endpoints and an ephemeral 127.0.0.1 port.
- Added `tests/TestFarmingStandaloneWeb.py` for real loopback HTTP, search and preview contracts, documented FF Mech Core sources, mob/material stop rules, headers, Host and Origin checks, disallowed methods/paths, duplicate query keys and source isolation.
- Browser has no gameplay control endpoints. Every operational control remains disabled; source names and historical audit data never establish a live route. No Waveplate spending, memory access, game input or automated movement.
- **Test execution: NOT RUN in this GitHub connector session.** The actual Windows repository, Python virtual environment and browser are not attached. Source commits/readback are not a test pass. Earlier 1,001 passed / 2 skipped / 1 error remain the most recent measured full repository run, before this remediation.
- **Next:** Codex must run TestFarmingStandaloneWeb, TestConfig, all Farming tests, exact-SHA full verifier, Qt and actual browser smoke; Terra Medium must independently review security and compatibility. FQ-01 is an implemented remediation candidate, not yet qualified. FQ-04 remains LIVE_VERIFICATION_PENDING.
- Full instructions: `docs/FARMING_STANDALONE_WEB.md`. Existing hourly coding automation stays paused by the owner's prior request.

---

## 2026-11-13 — explicit stop-criterion units in operator preview

- Separate **inventory-total** (material) from **encounter-limit** (mob) input semantics in the path-free Farming Assistant view contract. The existing `desired_total` request remains compatible, while the new `stop_criterion` explicitly carries a mode, requested quantity, unknown observed progress, `PLANNED_ONLY` state and `enforced=false`. No fake inventory count, observed kills or active timer is displayed.
- Update both the WebCustomTab and native Qt surfaces to change the operator label and progress explanation when switching Material/Mob. This prevents a mob encounter cap from being mislabeled as inventory ownership.
- Add pure view contract and offscreen Qt regression assertions for both modes, optional goals, and the disabled execution boundary. **Tests/compilation: NOT RUN** here because the full checkout and Windows Qt/OK Script runtime remain inaccessible. GitHub writes/readback do not qualify gameplay.
- Still blocked: actual current-game ID/drop mapping, approved route and runtime preflight, fresh inventory OCR receipts, independent Terra review, cancellation/input qualification. Start/Pause/Stop remain disabled; no spending/navigation/combat; no PR/master changes.
- **Next:** Codex on the authorized Windows checkout should run `TestFarmingAssistantView.py`, `TestFarmingAssistantQt.py`, `TestFarmingSelection.py`, and WebCustomTab smoke checks against the real UI/runtime, then verify the stop rule never bypasses bounded executor limits.

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingSelection.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_view.py src/gui/FarmingAssistantTab.py
```

---


## 2026-11-13 — private capture -> offline review manifest integration

**Source commit:** `b1945ba4dde5dd4f9526cb6c42390ed8802eb918`.
**Fixture correction:** `e440d3e856c86561e4a6ee95c06e1fbbb986ece6`.
**Handoff documentation:** `4e52c4e50245848a700dba930f677b47244a2f4f`.
Canonical branch: `agent/material-first-farming`, fast-forwarded from
`24b74de0115f1d57d37b3485eb0cac109b8b3c5b`. No other branch changed.

- Added `src/automation/farming_private_review.py`, an internal function
  `review_private_captures` to accept an already-constructed immutable handoff
  and an exact frame-ID map of actual `PrivateReadOnlyCapture` objects. It
  rejects missing, extra, invalid or duplicated private capture pairs and
  calls existing review-manifest validation to recheck in-memory consistency
  and **original retained/source/binding file bytes**. No user-supplied
  hunt/route profile path, runtime capture, input or executor authorization.
- Added `tests/TestFarmingPrivateReview.py` with **12 synthetic regression
  methods**: coherent original bytes (still `can_start=false`), stable manifest
  identity, wrong IDs/types, duplicate capture, changed in-memory PNG, forged
  retention digest, modified disk frame/source, expiry, unsafe binding paths
  and invalid packet. Synthetic FF Mech Core identifiers and positive deltas
  are **fixtures**, not an authentic drop receipt.
- **Actually verified:** GitHub branch fast-forward/commits and added source,
  test and documentation content. **NOT RUN:** these 12 tests, Python
  compilation, full project imports, Qt/Web GUI, native Windows/NTFS,
  installed OK Script game frames, real game/version, Antigravity CLI,
  independent Terra review or any live FF Mech Core drop/route.
  The allowed local checkout remains unavailable through Devspace, and
  container GitHub HTTPS cloning fails DNS resolution.
- **Still blocked:** proven current-runtime frame freshness and provenance,
  current-game numeric enemy/drop mapping, approved source/profile/database
  evidence, actual inventory-before/after receipts, bounded route calibration
  and independent Terra qualification. Private file consistency is **not**
  a live execution gate. No game input, navigation, combat, spending or
  premium refill; no PR or master mutation.

**Next meaningful increment:** Codex on Windows must run the private review,
private capture and original-byte tests with the original dependencies, inspect
actual NTFS ACL/junction and frame-freshness behavior, and have Terra review
those results before considering UI/internal preflight integration. Avoid
adding further evidence wrappers until real integration tests are available.

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingPrivateReview.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingPrivateCapture.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingReviewManifest.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_private_review.py tests/TestFarmingPrivateReview.py
```

---

## 2026-11-13 19:07 MYT — integrated opt-in read-only capture + private retention

**Source/tests commit:** `6e3ef2d613205e762cea7fd176579ae81d180773`
on canonical branch `agent/material-first-farming`, based on
`1b95bc1be41a31385879780ae01522ea5bb9b1f1`.

- New `src/automation/farming_private_capture.py` composes existing
  foreground/focus/cancellation-guarded `capture_readonly_frame` with
  `retain_readonly_snapshot` in the pre-existing trusted private evidence
  directory. Capture and retention both require explicit opt-in; opaque,
  random capture filenames are generated internally rather than supplied
  through the material/mob selector. The adapter returns an immutable
  in-memory snapshot + private retention reference for later handoff review.
  Errors fail closed; mismatched retention receipts never become evidence.
- New `tests/TestFarmingPrivateCapture.py` contains 10 synthetic scenarios:
  opt-in before capture, actual local file retention when run with the
  original dependency, collision resistance, missing private folder,
  capture failure, malformed payload, corrupt SHA, forged retention receipt,
  invalid clock and boolean/type rejection.
- **Actually run in isolated Linux harness:** source+tests `py_compile`
  PASSED; **10/10 synthetic tests PASSED using stand-in runtime and retention
  dependencies**. This checks the new production adapter with mocked
  dependencies. It is NOT the complete repository and does NOT validate
  the actual production retention module.
- **NOT RUN:** full repository test imports, Windows/NTFS ACL/junction behavior,
  actual OK Script frame capture/freshness, game version, GUI startup,
  Antigravity CLI, Terra review, FF Mech Core drop and executable route.
  Container GitHub HTTPS DNS still fails and Devspace could not open the
  owner's local checkout. GitHub connector commits/readback are available.
- There is **no** public path field, no task registration, no live game
  invocation or developer profile selection. All `can_start`/qualifications
  remain false. Neither `master` nor draft PR #4 was changed.

**Codex Windows regression handoff:**

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingPrivateCapture.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRuntimeCapture.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureRetention.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingReviewManifest.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_private_capture.py
```

**Next independent increment:** run the above against original dependencies,
qualify actual Win32 foreground/frame freshness and NTFS ACL/reparse behavior,
then connect **trusted opt-in** local retained-frame references to the private
review manifest. Do not expose this function in operator UI or enable
combat/navigation before independent current-game and Terra qualification.

---


Last manual checkpoint: 2026-11-13 (Asia/Kuala_Lumpur)
Working branch: `agent/material-first-farming`
Base: draft PR #4, `codex/core-and-routes-20261108` at `e06a9fb7b066e74c988e066154198fe89124173e`
Integration status: **IN PROGRESS — NOT LIVE QUALIFIED**. Preserve existing draft PR #4, master and user settings.

## 2026-11-13 18:xx MYT — opt-in read-only review manifest from original bytes

**Code/tests/handoff documentation commit:** `899aadc5370f5ec1fb6540a2da889228c53e6147` on
`agent/material-first-farming`, based on `6ae7cbc69cc13a8cc970a419801d8f4daed274c8`.
This is an independently reviewable, **non-executable** local capture-review
increment. No other branch, draft PR #4 or `master` was modified.

- Added `src/automation/farming_review_manifest.py`. The internal-only
  `prepare_readonly_review_manifest` joins a canonical short-lived handoff,
  coherent original in-memory snapshots, retained frame references and **actual
  locally hashed** source/profile/frame bytes. Missing or stale sessions,
  modified disk evidence and ambiguous bindings fail closed. No user-facing
  file paths, task dispatch, game input, live capture or spending were added.
- The frozen `ReadOnlyReviewManifest` emits a deterministic *path-free* digest
  for later manual correlation. This is **NOT** an attested origin, signed
  reviewer certificate, authenticated inventory receipt, runtime qualification,
  validated FF Mech Core enemy mapping, executable route or Start permission.
  All approval and `can_start` flags remain false.
- Added `tests/TestFarmingReviewManifest.py`: **13 synthetic regression test
  methods**, exercising correlation, canonical identity, original byte
  tampering, missing frames, invalid binding paths, expiry and invariant
  execution disablement. Synthetic `000123` and quantities are fixtures.
- Updated `docs/FARMING_ASSISTANT_LIVE_HANDOFF.md` with contract boundaries.
- **Tests: NOT RUN** in this automation runtime. GitHub write/read tooling
  works, but no actual Windows checkout/OK Script/PySide6 installation is
  available here, and container GitHub HTTPS cloning fails DNS resolution.
  No Antigravity CLI, Codex game control or Terra reviewer was invoked.
- **Outstanding blockers:** full project imports/Qt and Web startup, NTFS ACL/
  reparse/junction checks, actual current OK Script frame sequence and game
  version, verified FF Mech Core source and numeric mob ID, independent OCR
  before/after receipts, qualified bounded route and Terra review.
- **Next increment:** Codex should execute focused + full offline integration
  in the real Windows checkout and independently inspect the new manifest
  contract (including TOCTOU/ACL assumptions) before wiring any reader/UI.
  Do not enable combat/navigation/rewards without all independent live gates.

Exact local Windows Codex commands (using the existing virtualenv):

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingReviewManifest.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureSession.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureBinding.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_review_manifest.py
```

---

## 2026-11-13 — evidence root reparse/alias validation (current increment)

**Code/test/documentation commit:** `9482eee1a03d2fea1f036f9ee7e4903439203e36` on
`agent/material-first-farming` (based on `75b5bc43af55152c4c3e33f1f5bc29a945ffd2ab`).
Changes: `src/automation/farming_capture_verify.py`,
`tests/TestFarmingCaptureVerify.py`, and
`docs/FARMING_ASSISTANT_LIVE_HANDOFF.md`. No route or combat behavior changed.

- Tightened original-byte audit roots: absolute paths required; each root and
  every ancestor must be free of symlinks, junctions and Windows reparse-point
  metadata. Reject redirected components inside relative source/evidence paths.
  Preserve existing `LOCAL_ROOT_INVALID` and `UNSAFE_LOCAL_PATH` diagnostics.
- Added **3 new synthetic regression test methods**: relative checkout/evidence
  roots, symlinked source-root ancestor and symlinked evidence-root ancestor.
  Previous tests remain unchanged; **NOT RUN** in this session. Actual Windows
  NTFS junction/reparse handling, ACL inheritance and link races are NOT
  qualified by static source inspection.
- GitHub code commit and canonical branch HEAD checked; the authorized Windows
  checkout was not available via Devspace (internal error) and container HTTPS
  access to GitHub still failed DNS. Neither Gemini Antigravity CLI nor Terra
  was invoked. No source/tests were executed locally. Do not infer test PASS.
- **Still blocked:** full repo imports/Qt/Web startup, Windows private-root ACL
  verification, OK Script fresh-frame/foreground proof, installed game version,
  authentic FF Mech Core enemy/drop inventory receipts, reviewed bounded route
  and independent Terra qualification. No generated artifact may authorize
  Start, navigation, combat, paid refill or spending.
- **Next small increment:** run integration tests in the permitted Windows
  checkout and independently exercise actual junction/reparse/ACL cases;
  only then consider a trusted, read-only evidence-session manifest. This
  remains a non-executable preview.

Codex Windows checkout (use existing local virtualenv):

```powershell
git fetch origin
git switch agent/material-first-farming
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p TestFarmingHandoffIntegrity.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "TestFarmingCapture*.py" -v
.\\.venv\\Scripts\\python.exe -m py_compile src/automation/farming_capture_verify.py
```

---

## 2026-11-13 — immutable observation integrity revalidation (new increment)

**Two actual code commits on `agent/material-first-farming`:**
`9dad20adf97340a7614658559bf83e3df2a1e8c9` (implementation,
new tests and handoff specification) followed by
`4fcb5ae9c67453b1d7f30e5c453542100cf4dc2b`
(compatibility with existing explicit clock/expiry rejection reasons).
Additional code correction: `9e5f2e6386391f61dd39f14a8b1cb0d2d2f050d5`
moves integrity checking ahead of snapshot/retained-frame map access so a
forged packet cannot be masked by a missing/extra-frame error. This remains
unexecuted against the full repository; all tests below remain **NOT RUN**.

- `farming_live_handoff.validate_observation_handoff_integrity` reconstructs
  the canonical v1 observation and compares all frozen fields and SHA256
  packet identity. Rejects post-construction `dataclasses.replace` changes,
  forged packet fingerprints, repeated digest-map keys, noncanonical field
  ordering and invalid/stale claims. A frozen dataclass alone does **not**
  guarantee that its fields came from the validating constructor.
- The read-only session auditor, private-frame binder and original-byte
  verifier now revalidate packet integrity before accepting declared hashes
  or file mappings. Invalid verifications return
  `HANDOFF_INTEGRITY_INVALID` without exposing the unverified fingerprint.
  Previous explicit `CLOCK_INVALID`, `OBSERVATION_STALE`,
  `RETAINED_BINDING_INVALID` and `CAPTURE_CLAIM_STALE` behavior is preserved.
- Added `tests/TestFarmingHandoffIntegrity.py` (7 synthetic regression
  methods) covering a valid-but-unapproved packet, changed target/enemy/
  version/quantity, altered digest/maps, duplicate labels, timestamp,
  binding/session rejection and disk-free early verifier rejection.
  Synthetic IDs and quantities are test fixtures, **not in-game evidence**.
- **NOT RUN:** all 7 new regression tests, existing tests, full repository
  imports, py_compile, Qt/Web startup, Windows OK Script integration,
  Antigravity CLI, independent Terra review and live FF Mech Core evidence.
  This execution environment cannot clone GitHub over HTTPS (DNS failure)
  or access the authorized Windows checkout. GitHub connector commits and
  branch updates were successful; they are not test or live-game evidence.
- All execution controls remain fail-closed; no navigation, combat, spending,
  user-entered developer paths, changed task registration, PR mutation,
  force-push or merge.

**Run in the authorized Windows Codex checkout (using the venv):**

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingHandoffIntegrity.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureBinding.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureSession.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_live_handoff.py src/automation/farming_capture_binding.py src/automation/farming_capture_verify.py src/automation/farming_capture_session.py
```

**Next independent increment:** run complete repository integration and
qualify Windows evidence-folder reparse/ACL handling. Then inspect actual
OK Script frame freshness, installed-game version and independent inventory
receipts with Codex/Terra. Canonical SHA integrity is **not** evidence origin
authentication, OCR reliability, route calibration or farming authorization.

---



## 2026-11-13 — private snapshot-to-handoff in-memory coherence audit (new increment)

**Actual source and tests committed on canonical branch. No game input or route authorization.**

- Added `src/automation/farming_capture_session.py` with frozen, path-free
  `ReadOnlyCaptureSessionAudit` and `inspect_readonly_capture_session`.
  It checks that original in-memory PNG bytes, digest, size, frame token,
  captured instant, claimed OK Script version and dimensions agree exactly
  between `ReadOnlyFrameSnapshot`, `RetainedReadOnlySnapshot`, and
  `FarmingObservationHandoff`. It reuses the existing chronological
  retention-binding checks and rejects inconsistent or stale claims.
- Added `tests/TestFarmingCaptureSession.py` with ten synthetic contract
  tests: positive local coherence with `can_start=false`; mismatched runtime,
  tampered PNG, forged digest/size, clock disagreement, changed resolution,
  invalid PNG/type, missing/extra snapshots, reversed/unsafe retention and
  expired/naive clock. All enemy and material fixture values are synthetic.
- **Actually run:** container `py_compile` for new source/test **PASS**;
  ten tests **PASS (10/10)** in an isolated Linux harness with the actual
  new source/test and stubbed existing handoff/capture/binding dependencies.
  These are *not* full-repository or Windows game integration tests.
- **NOT RUN:** full repository imports/tests, local Qt/Web startup, actual
  Windows OK Script capture, native frame freshness, installed game version,
  independent Terra review, Antigravity CLI, FF Mech Core drop or route.
- Code commit SHA: `0a5783064d3bac707a09fb1852478af50043cf2f`;
  tests commit: `7560d67dba57685c3287ef418154550fb7eae672`;
  documentation commit: `9774336f9d3f4f2d8ff338c9188765ccf9830dc2`.
- Verified working branch remains `agent/material-first-farming`. No PR
  modification, force push, merge or master change.

Codex local Windows checkout qualification:

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureSession.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureBinding.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureRetention.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_session.py
```

**Next independent increment:** validate complete repository imports and
Windows private-directory ACL/reparse protections in the authorized Codex
checkout; then attach trusted, *read-only* frame sequence/freshness metadata
and game-version observation without accepting UI-supplied versions or paths.
Even matching in-memory bytes and local disk hashes cannot prove gameplay
origin or authorize a source, inventory receipt, route or executor. Require
separate reviewed current-game evidence and Terra qualification.

---
## 2026-11-13 — immutable retained-frame to handoff binding (new increment)

**Actual implementation and tests committed on the canonical branch. No game
input, route authorization, PR modification or merge.**

- New `src/automation/farming_capture_binding.py` joins private
  `RetainedReadOnlySnapshot` objects to v1 `FarmingObservationHandoff`
  frame IDs using exact mapping, matching frame SHA256s, bounded filename/
  size/time checks, distinct paths and strictly chronological captures.
  The observation must follow the frames and arrive within two minutes
  of the last capture; stale or ambiguous references reject.
- `verify_retained_capture_claim` now passes the internal frame mapping
  into the existing real-byte `verify_local_capture_claim`, which checks
  source/binding/screenshot digests on disk. Public summaries omit private
  filenames, cannot establish game origin or receipts and always report
  `can_start=false`. Start/Pause/Stop still remain disabled.
- New `tests/TestFarmingCaptureBinding.py`: 10 synthetic cases covering
  immutable path-free summary, matching local bytes, altered screenshot,
  missing/extra frame IDs, wrong hashes/types/sizes, path traversal,
  duplicated private filenames, reversed chronology, stale/future/naive
  times and expired handoffs.
- **Actually run:** `py_compile` for source/test PASS, **10/10 PASSED**
  in an isolated Linux synthetic-stub harness using the real new source/test
  and stand-in existing handoff/retention/audit classes. **NOT RUN:**
  full checkout tests against original existing dependencies, Windows/Qt/Web
  startup, real OK Script capture, in-game FF Mech Core drop,
  Antigravity CLI, independent Terra review or current-game route execution.
- GitHub commits: source `c939bf2d6b1621fb93aed025e3824a5ceec604e9`;
  tests `eb2789f2547f6a9983d9b0e786de29493b78194b`;
  handoff docs `cc79cbff91254cab9ce3d8bff9af87bdf94c8313`.
- **Exact blockers:** current installed game/version and WGC frame freshness;
  Windows private-folder ACL/reparse validation; current numeric enemy IDs,
  verified inventory delta, FF Mech Core source relationship, bounded
  executable route and independent source/runtime/route review.
  Container GitHub clone still fails DNS; GitHub connector writes are working.

Run on local Codex Windows checkout:

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureBinding.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureRetention.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_binding.py
```

**Next independent increment:** qualify the bridge against actual complete
repository imports/tests and Windows private-folder behavior, then build
an opt-in read-only trusted local evidence session/manifest which binds
runtime version, actual frame freshness and source SHA; do not enable
executor input pending separate Codex/Terra and live-game gates.

## 2026-11-13 — private read-only snapshot retention (new increment)

**Implementation committed to canonical branch; no game execution or live authorization.**

- Added `src/automation/farming_capture_retention.py`: opt-in local
  original-PNG retention from `ReadOnlyFrameSnapshot`, requiring an existing
  absolute trusted private directory, unique opaque token, bounded fresh
  content and matching SHA256. File creation is exclusive (never overwrites),
  readback is checked, and root symlink/junction/unsafe token paths reject.
  `public_summary()` never exposes local paths and always has `can_start=false`.
- Added `tests/TestFarmingCaptureRetention.py`: 9 synthetic cases covering
  success, opt-in, duplicate, traversal token, stale/future evidence,
  bad hash/PNG, invalid/symlink root and naive clock.
- **Tests actually run:** 9/9 PASSED in isolated Linux Python with a stub
  `ReadOnlyFrameSnapshot` class matching the existing frozen contract;
  source/test `py_compile` PASSED. **NOT RUN:** current full repository suite,
  Windows/OK Script integration, Qt/Web startup, Antigravity CLI, Terra review,
  actual frame acquisition, independent evidence review or live game.
- Commits: source `40b79c9d2a23a3ce5812501f7307d3260083029d`,
  tests `05faf1ed759e1bf14f3eee337b415c26deaa8c76`,
  documentation `710d5faa73e4ac2b6f458e2c3d89fbbe9eafdc2e`.
- **Blockers:** private Windows directory ACL and reparse-point verification,
  current-game version/frame freshness and capture provenance, numeric
  enemy identity, independent Terra review, real FF Mech Core receipt,
  bounded executable route and safety qualification. Existing
  Start/Pause/Stop remain disabled. No PR #4/master changes or merges.

Local Codex commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureRetention.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRuntimeCapture.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_retention.py
```

**Next independently reviewable increment:** bind retained private frame IDs
to an internal handoff evidence map without operator-supplied paths or
automatic authorization; validate actual Windows filesystem/OK Script
behavior and current-game frame freshness locally before gameplay work.
## 2026-11-13 — opt-in foreground snapshot producer (read-only)

**Actual source/tests committed on canonical branch; gameplay execution stays disabled.**

- New `src/automation/farming_runtime_capture.py` uses actual OK Script
  `next_frame()` / `frame` task patterns, the task's Windows game HWND,
  three foreground/cancellation guards and installed `ok-script` metadata to
  produce a bounded private PNG snapshot. It never issues input, OCR,
  navigation, route execution, spending or Story Watch changes.
- Caller must explicitly opt in; there is **no production foreground-guard
  override parameter**. Non-Windows focus checks fail closed. A snapshot
  public summary contains no image, HWND, paths, game version, or approval;
  `can_start=false` and freshness/route/receipt verification remain false.
- New `tests/TestFarmingRuntimeCapture.py`: **10/10 isolated synthetic
  contract tests PASSED** under container Python with synthetic task/window
  and mocked runtime/focus; `py_compile` of both source/test also passed.
  The container is not a local OK Script or Windows gaming runtime.
- Source/test commits in order: `09af79e923e3ce27a663608110a8072b2a435e08`,
  `8c0e131bad95a4e0f73e07cda01fa80f208c315d`,
  `85697f109ac99f55c95fb88a07bce1f3576c336a`,
  `3a72ac97d6e80852ed79173a29f99d82fd410beb`; handoff docs
  `bdd246bb93dc92b6ad00ca1f74ddc7fc750fbb47` (last checked before
  this status-file update).
- **NOT RUN:** Windows/real OK Script integration, WGC frame freshness and
  focus checks, native Qt/Web startup, full repository test suite, Antigravity
  CLI, independent Terra review and live FF Mech Core evidence. No game
  control, route authorization, merge, PR modification or master write.

Codex local follow-up:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRuntimeCapture.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_runtime_capture.py
```

**Next increment:** independent local review of actual Windows frame-source
freshness/focus/version metadata and safe private snapshot retention, then
bind separately observed game version, source/profile hashes and inventory
delta into the existing immutable handoff. Do not wire gameplay executor
before independent Terra/runtime qualification.
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
