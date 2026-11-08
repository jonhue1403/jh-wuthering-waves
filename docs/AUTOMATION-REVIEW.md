# Independent CORE_AND_ROUTES review

Reviewed on 8 November 2026 by a separate reviewer agent. Scope: the actual
working changes on `codex/core-and-routes-20261108`, based on integration commit
`0bf94854` (JH `d13798d2` plus upstream `f497bd84`). The final candidate SHA and
the root agent's exact-commit verification belong in `AUTOMATION-STATUS.md`.

## Outcome

No remaining material source defect was established in the reviewed changes
after the fixes below. This is a source/offline review outcome, **not live
qualification, release approval, or proof that CORE_AND_ROUTES live acceptance
is complete**. Spending and movement remain gated by real current-game profiles;
the Story Watch no-skip latch is useful even when no segment is qualified.

The review read the supplied execution contract, actual task callers and diffs,
new session/input/resource/goal/routine/story/route modules, registrations,
qualification gates, tests, and the installed ok-script **3.0.4** executor and
input backends. It checked integration against those APIs rather than relying
only on the implementers' reports. No game input, account mutation or remote
communication was performed by this reviewer.

## Findings and dispositions

| ID | Established risk | Final disposition and check |
|---|---|---|
| R1 | Framework pause could retain held keys; session limits were checked only at input/exit. A subsequent wait wrapper also lost the framework's `wake_version` argument. | Fixed: framework pause/stop/check/wait hooks release/revoke and preserve signatures. Real installed executor methods exercised by `TestAutomationAdapter`. All registered input adapters are attempted even if one cleanup fails. |
| R2 | NORMAL/Resume could use a cached safe screen after failed capture and unlock an old skip preference. | Fixed: successful capture, frame age/sequence and window binding precede safe-state verification. Adapter regression verifies failed capture/wrong window leave the story latch intact. |
| R3 | Alternate Pynput event gestures, native cursor movement and delayed MouseReset callbacks bypassed shared delivery checks. | Fixed: alternate backends use the shared guard, native cursor calls checkpoint first, and queued MouseReset actions carry cancellation epochs. Source and adapter checks; actual event gestures remain live pending. |
| R4 | Inherited Echo merge/enhance/reconstruction could consume or destroy items despite disabled dangerous-resource policy. | Fixed: those task entries are ineligible under the shared policy, including ChangeEcho reconstruction. Queue rejects the Daily destruction option. Source inspection and routine dispatch regression. |
| R5 | Route inventory and identity observations could relabel a cached screenshot with a new timestamp/frame ID. | Fixed: successful captures, actual capture timestamp/sequence, distinct stable observations and correct-window checks. Route/identity regressions reject missing, repeated, stale and wrong-window frames. |
| R6 | Interrupted-claim reconciliation accepted numeric observations without a matching account/server/activity/cycle identity. | Fixed: exact observed identity required. Debit-only reconciliation remains separate from inventory receipts; mismatch preserves uncertainty. Journal regressions pass. |
| R7 | Legacy stamina OCR used loose searches and last-match-wins/default-zero behavior. | Fixed: normalized strict unique current/reserve readings; ambiguous/conflicting values fail closed. Claim regressions cover missing, excessive and ambiguous debits. |
| R8 | A blanket narrative-skip guard also blocked qualified challenge-restart confirmations. | Fixed: observed challenge start/restart semantics use a separate helper; it neither clicks the narrative skip checkbox nor enables skipping. Claim regression tests both farming confirmation and Story Watch refusal. |
| R9 | Pynput key/button release refused after foreground loss, silently stranding tracked presses during takeover. | Fixed: only tracked releases bypass the backend's foreground refusal. Adapter test models the real backend refusal and verifies release after takeover. |
| R10 | Framework pre-run focus ran outside a lease and before mode eligibility. | Fixed: initialization installs hooks before normal task execution; unowned pre-run focus is suppressed. Adapter regression verifies no focus effect. |
| R11 | Assigning `TaskExecutor.interaction` would raise because 3.0.4 exposes a read-only property. | Fixed: guard updates the actual device-manager or current-job owner, including rebinding. Adapter tests use the installed class's real read-only property. |
| R12 | Suppressing focus could leave an unfocused Pynput task waiting for capture indefinitely. | Resolved with an explicit safe limitation: foreground pre-run fails promptly and asks the operator to focus the verified game window manually. No automatic focus or live compatibility is claimed. Adapter regression verifies failure before capture/input. |
| R13 | Raw foreground swipe/scroll could affect another app after focus changed, and raw gesture exceptions could leave transient presses untracked. | Fixed: foreground validation at delivery, tracked bounded click/swipe primitives, takeover on focus loss, and unconditional tracked cleanup. Adapter tests verify mid-swipe focus loss and blocked scroll. |

The material worker also corrected shared-budget interoperability identified
during follow-up: a standalone claim and a queue claim on the same observed
budget cycle now use the same persisted scope. Editing a plan does not create a
fresh allowance. Pending/uncertain claims block the account/server across reset
changes instead of disappearing from accounting.

## Independently executed offline checks

Using the candidate worktree's `.venv\Scripts\python.exe`, the reviewer ran:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.TestResourceGoals tests.TestResourceRoutineTask tests.TestCultivationTask tests.TestBoundedRouteTask tests.TestResourceClaims tests.TestAutomationSession tests.TestStoryWatch -q
.\.venv\Scripts\python.exe -m unittest tests.TestAutomationAdapter -v
```

Results: **107 passed** in the first run, then **14 passed** in the adapter run.
These are 121 tests in eight modules at the reviewed working state. The adapter
run uses real installed executor properties and lifecycle/wait methods with fake
capture/input; it sends no actual OS/game input. An earlier 84-test review run
also passed but is not added to this total because it overlaps these modules.
`git diff --check` passed at the review snapshot.

These measurements are distinct from upstream PR #1837's author-reported tests,
historical JH tests, source-image fixture tests, the root agent's broader final
regression run, and any actual live qualification. See the final verification
record for checks against the committed candidate.

## Remaining acceptance gates

`LIVE_VERIFICATION_PENDING`: matching input privileges; installed game-version
and locale/aspect evidence; current identity/reset/Guidebook/claim/result
profiles; one real Story Watch travel/dialogue/combat segment and separately
qualified native playback; single-camp combat requalification followed by
independent eligible sessions; observed multi-camp segments and material/drop
inventory evidence; known-beacon loading/destination evidence; current Fantasies
Weekly Activity/reward and weekly boss claim eligibility; actual GUI Start and
recording continuity if configured.

The route database supplies mob/spawn locations, not a verified drop table. No
material mapping or current UI was invented to satisfy these gates. An empty
camp remains distinct from a combat trial. Source hashes and historical
calibration are retained but do not promote historical runs to 3.0.4 live PASS.

## Final committed-source addendum

The reviewer subsequently inspected the final source at
`241ea5d30a52532dfa1135ea17bb4157a9eeb2ab`. The reviewable boundaries are:

- Core commit `354d4d7c`: shared session/input/resource controls, material goals,
  daily/weekly coordination, Story Watch and single-camp runtime qualification.
- Separate route commit `241ea5d30a52532dfa1135ea17bb4157a9eeb2ab`: bounded
  material-route/beacon implementation, route registration and queue integration,
  route tests and profile documentation.

The final small deltas preserve an explicit PAUSED/TAKEOVER state when an
activity unwinds, leave the session stopped after incomplete input cleanup, and
refuse failed captures before claims, pre-confirmation/result observations or
semantic challenge confirmations. Source inspection found no new material
defect in these deltas. The reviewer reran `TestAutomationSession` and
`TestResourceClaims` against this committed source: **20 tests passed**.

The reviewer also read and checked the root agent's persisted verification
record at `logs/core-routes/verification/results.json`: exact source SHA
`241ea5d30a52532dfa1135ea17bb4157a9eeb2ab`, `dirty_at_start: false`, **45 modules,
462 tests, zero failed module exit codes**. This is the root agent's broader
measured run, not a second independent execution of all 462 tests. It includes
the final 9 session tests, 11 claim tests and 14 installed-executor adapter tests.
The review addendum changes documentation only. All live acceptance boundaries
above remain pending.

## Supported-runtime and registration addendum

The subsequent registration-only compatibility change at
`dc422e5276797448bbcdaf4c9506b44ef06a2fd9` appends the five new tasks after the
inherited entries. The reviewer inspected this diff and its added regression:
the documented CLI `-t 1` continues to select DailyTask, and inherited JH task
order is preserved. No new material finding was established.

The repository's development guidance specifies Python 3.12; its broader
`pyproject.toml` minimum does not replace that documented runtime. The root
preserved the primary checkout/environment and rebuilt only the candidate's
standard `.venv` on Python **3.12.14**, retaining the same exact dependency pins.
Earlier review measurements above used Python 3.13 and remain separately
identified evidence.

The reviewer read and checked
`logs/core-routes/python312-verification/results.json`: exact source SHA
`dc422e5276797448bbcdaf4c9506b44ef06a2fd9`, `dirty_at_start: false`, **45 modules,
463 collected tests, zero failed module exit codes**. This supported-runtime run
was executed by the root agent, not independently rerun in full by the reviewer.
The extra test checks DailyTask's documented CLI index. The root also reports a
successful registered queue preview on Python 3.12; that read-only preview is
separate from game/input/live acceptance and is documented in its runtime
evidence. No new live gates or live PASS claims follow from this addendum.
