# Material goals and bounded routines

Status: offline implementation; `LIVE_VERIFICATION_PENDING` for resource spending,
native goal UI, account/reset identity profiles and current Weekly Activity UI.
No qualified source/identity/weekly profile is bundled or automatically enabled.

`CultivationTask` adapts EEEEEEEdison's upstream [PR #1837](https://github.com/ok-oldking/ok-wuthering-waves/pull/1837),
head `61464cb8c78a4d9ac6a5a98ecd5cafa5ab58e939`. The original license and
attribution remain. Author-reported two claims and 27 tests are upstream evidence;
they are not JH live results. JH's modified task regressions are measured separately.

## Registered tasks

- **Cultivation Resource Farm**: read the selected Guidebook ascension row and
  cross-check item-detail inventory; Simplified Chinese, 16:9. Preview defaults
  true, optional Echo collection defaults false. Explicit spend, claim, time and
  minimum-balance limits plus a fresh identity profile are required to execute.
- **Resource Goal and Routine Queue**: preview labelled native/user goals and
  exact source mappings; at most three inherited-task dispatches per invocation.
  Its preview performs no capture, navigation, combat or spending. It uses the
  existing scheduler and `run_task_by_class`, not another execution thread.

The queue supports the inherited Daily, Tacet, Forgery, Simulation, Farm Echo,
Nightmare Nest and Garden task identities. Garden weekly progress requires a
current calibrated Weekly Activity profile. Weekly boss material claim eligibility
is separate from boss Echo farming and remains unresolved without a qualified
reward/eligibility adapter. Current Fantasies reward claiming is not enabled.
Historical fixed-position Remnant Crystal claim clicks were removed from Garden.

## Local plan format

Save under ignored `configs/`. This example intentionally has no source mapping:
it can be previewed, but cannot execute until genuine profiles and evidence exist.
The target is explicitly user supplied, not presented as a native requirement.

```json
{
  "schema_version": 1,
  "budget": {"max_spend": 60, "max_runs": 1, "max_seconds": 600, "minimum_balance": 0},
  "budget_identity_profile": "identity-budget.json",
  "journal_path": "automation-actions.json",
  "goals": [{"name": "EXACT OBSERVED MATERIAL NAME", "owned": 4, "required": 28,
             "origin": "user_supplied", "evidence": "user target; refresh owned from actual item detail"}],
  "sources": [],
  "activities": [],
  "executor_config": {}
}
```

A source entry has `material`, `kind` (`boss`, `domain`, `overworld`), `executor`,
`profile` (routine observation profile), `evidence`, `runtime` (exact ok-script
version), `qualified`, `evidence_path` and `evidence_sha256`. Missing, stale,
ambiguous, unqualified or unknown mappings stay `UNRESOLVED`. Allowed executors
are the registered inherited classes, `CultivationTask` and `BoundedRouteTask`.
`executor_config` holds explicit config overrides keyed by class name. Overrides
are type-checked and restored after success, cancellation or failure. The Daily
Echo destruction option is prohibited in this coordinator.

Source-kind and provider identity are enforced before the resource-goal queue
can choose any source. A `boss` source must use `CultivationTask`, an
`overworld` source must use `BoundedRouteTask`, and a `domain` source
must use an inherited `ForgeryTask`, `SimulationTask`, or `TacetTask`.
Wrong-category classes and synthesized/quest/event/weekly Echo sources cannot
be used as an overworld material route by renaming a JSON entry. An exact,
uniquely matched mapping is still **only a dispatch candidate**: it does not
substitute for current-runtime identity, task-specific SHA-bound qualification,
session ownership, resource ledger approvals or an observed inventory receipt.
The queue preview reports unresolved/ambiguous candidates and makes this
remaining preflight boundary explicit.

An activity entry has `activity` (`daily`, `tacet`, `forgery`, `simulation`,
`boss_echo`, `nightmare_nest`, `garden`), `observation_profile`, and optional
`task_config`. Before dispatch, it must have observed eligibility and a fresh
account/server/reset identity. After dispatch, it must have observed completion
and an actual target inventory increase. A returned Python task is insufficient.
Completed work is skipped by observed account/server/activity/cycle identity.

Native targets must include their observation evidence. The Cultivation adapter
rechecks the required quantity against the native Guidebook before execution.
Other producers accept labelled user targets until a native target reader is
qualified. The Cultivation adapter supports the selected row, not cross-boss
planning. Queue batches may use different separately qualified source profiles.

### Qualified bounded-route material dispatch (implementation, not live approval)

For a `BoundedRouteTask` material-goal candidate, the internal
`executor_config.BoundedRouteTask` must explicitly supply a
`Route Manifest`, `Runtime Qualification`, and `Observed Game Version`.
The queue never falls back to the reused child's previously selected route.
It reads the reviewed surface manifest and associated profile, and checks
the `MATERIAL_ROUTE` stage against the exact current source hashes, runtime
version and supplied observed game version **before actual inventory observation
or durable attempt creation**. Missing, stale, mismatched or unreviewed local
evidence fails closed without creating a new material attempt.

The approved route determines the internal `Target Mob`, `Max Camps`, and
the queued material's `User Material Target`. A conflicting explicit override
is rejected instead of being silently redirected. Only a non-preview material
queue invocation can derive `Preview Only: false`,
`Localization Only: false` and `Test Walk Only: false`; the inherited
`HuntMobTask` still independently verifies the SHA-bound current-runtime
qualification, source profile, bounded map route and live input/session guards.
This does **not** permit arbitrary mob routes, spending or gameplay on
reference-only sources. There is no bundled qualified route for FF Mech Core,
and the native Qt/Web Farming Assistant remains read-only until genuine local
qualification and separate controlled acceptance.

## Calibration contracts

Profiles are local configuration, not instructions or arbitrary Python. The
readers use only existing named features and bounded OCR. Calibration screenshots
must be real captured files with matching SHA-256 values; an operator flag or
matching hash does not replace live qualification.

Identity profile fields:

- `schema_version: 1`, `qualified: true`, `framework_version`, `language`,
  `resolution: [width, height]`, `screen_feature`.
- `calibration_screenshot`, `calibration_sha256`.
- `cycle_kind: "immutable_observed_reset_id"`; countdowns and PC dates are
  rejected as reset identity sources.
- `fields`: exactly `account`, `server`, `cycle`; each has normalized `box`
  (`[left, top, right, bottom]`) and exact `expected_text`.

Two distinct fresh successful captures must agree. The public observation guard
checks frame age, advancing frame sequence and capture/input window identity.
Missing capture, stale frames, wrong windows and unexpected OCR fail closed.
No current game screen containing all required immutable identity fields has yet
been qualified in this candidate. Do not mark a profile qualified without that
evidence or substitute a changing countdown to make the gate pass.

Routine observation profile fields:

- Same schema/qualified/framework/language/resolution binding; `activity`,
  `qualification_evidence`, `screenshot`, `screenshot_sha256` and `page_feature`.
- `identity_profile` (relative path).
- `status`: normalized `box`, exact `eligible_text`, exact `completed_text`.
- `inventory`: map from exact material/item names to normalized quantity `box`,
  `label_box`, and exact `item_text`. Each observed quantity must be a single
  strict integer and its item-name cross-check must match on both fresh frames.
- Optional `waveplate_box` for read-only interrupted-claim reconciliation.

Profiles do not invent menu routes. The user must place the supported observer
view on screen; unavailable post-dispatch views pause with uncertainty rather
than assuming completion. New navigation would require real screenshots and
separate calibration.

Weekly Activity profile fields are implemented in `src/automation/weekly.py`:
same binding and screenshot proof, `ui: "fantasies_weekly_activity"`,
`qualification_evidence`, `weekly_tab_feature`, `garden_entry_feature`,
`page_feature`, `title_box`, and a strict owned/required `progress_box`.
The current Weekly Activity title and stable progress are required. No legacy
fixed 6000-point observation is treated as a current reward receipt.

## Claims, limits and interruption recovery

`PENDING` is fsynced and atomically replaced before the first possible claim
confirmation. After that click, only bounded result observation occurs. There is
no retry of the confirmation. Both sides of the resource debit must match:
`121 -> 1` cannot confirm a 60-point claim. Regeneration tolerance defaults to
zero; one point requires an independently observed regeneration tick.

The shared helper forbids reserve/refill confirmation, including changed or
conflicting observations and current 59/reserve 95. Dangerous resource flags are
disabled. Debit-only inherited receipts have `reward_received: false`; only
actual inventory observation can confirm a material reward. Combat success,
confirmation, actual receipt and target completion are separate states.

The queue derives one persisted budget scope from fresh observed
account/server/budget-cycle identity. Daily and weekly activities
may have different activity cycles while sharing this allowance. Retries do not
generate a fresh budget scope. All dispatches share the configured elapsed-time
bound. Pending/uncertain spending blocks the account/server even after a reset.

On interruption, inspect the journal and preserve the reward screen. Set the
queue's `Preview Only` false and `Reconcile Pending Only` true with genuine
matching observer profiles. This mode sends no claim input; it requires fresh
account/server/activity/cycle identity, actual inventory and current Waveplates.
If any observation or debit is ambiguous, the record remains `UNCERTAIN` and
spending stays blocked. It never assumes an unchanged balance means no click
landed. Corrupt journals or abandoned writer locks also block execution. Do not
delete the journal/lock merely to bypass uncertainty; first verify no controller
is active and reconcile the affected account manually.

## Remaining live gates

1. Capture and review the current locale/aspect/version Guidebook, item detail,
   single/double/plain claim dialogs, result state, and identity/reset views.
2. Qualify OCR/profile binding read-only, then one bounded nonspending input.
3. Configure one 60-point/one-claim/time/minimum-balance allowance, zero reserve,
   refill and premium use, and run one full inventory-verified loop.
4. Repeat in independently eligible sessions; include cancellation, delayed
   results, manual takeover and interruption/resume. Preserve separate evidence.
5. Capture current Fantasies Weekly Activity/reward and weekly boss eligibility
   before enabling those adapters. Do not reuse the historical claim coordinates.

Offline checks cannot establish kills, actual rewards, resource changes, game
version compatibility or any of these live passes.
