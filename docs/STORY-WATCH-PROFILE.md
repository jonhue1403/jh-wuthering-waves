# Story Watch qualification contract

Status: **LIVE_VERIFICATION_PENDING**. The candidate includes a bounded segment
runner and persistent no-skip protection. No quest segment or native Semi-Auto
control is currently marked qualified by this work. Offline mock observations
are not screenshots or game completion evidence.

Starting **Story Watch** activates its durable no-skip guard before reading its
profile. A missing/unqualified profile produces a useful pause without input.
Pause, cancellation, exceptions, manual takeover and process restart leave the
guard active. Existing skip-trigger settings are never restored automatically.
To enable skipping later, explicitly select the compatible normal mode through
the session control and verify a fresh safe world screen. The new Skip Dialog
trigger defaults to disabled; old persisted settings remain subject to the guard.

## Capture one actual segment

1. Keep the existing recorder running. Record its output path, active status,
   enforced time/storage limits and remaining allowances if recording is required.
2. Observe the installed game version and a short eligible quest segment that
   contains surface travel, dialogue and combat. Do not advance an unapproved
   choice to manufacture a usable baseline.
3. Save full original screenshots for each precondition, postcondition,
   choice and native Semi-Auto control. Annotate/export named features through
   the installed ok-script `generate-templates` workflow. Do not invent controls
   from feature names. `btn_auto_play_dialog` alone does not qualify Semi-Auto.
4. Calibrate a short surface travel segment using ordinary WASD inputs. Each
   movement is at most 0.25 seconds, at most 20 movements per step. A step runs
   once and then requires a fresh observed postcondition; failure pauses rather
   than replaying the route.
5. Have another reviewer check the current game version, screenshot SHA256s,
   objective OCR region, feature meaning, surface route, combat precondition and
   visible postconditions. Only then create the reviewed profile.
6. Run read-only preflight, then the bounded segment. Include cancel/takeover
   during dialogue and process restart. Confirm no skip resumes. Reobserve the
   objective after combat. Keep observations and results distinct from unit tests.

## Profile fields

`Story Profile` points to a UTF-8 JSON file containing:

| Field | Contract |
| --- | --- |
| `profile_id` | Stable identity for the reviewed quest segment. |
| `game_version` | Exact version observed in the game at qualification. |
| `qualified`, `reviewed_by` | Explicit qualification decision and reviewer; never inferred from tests. |
| `evidence` | Nonempty list of `{ "path": "relative/full-capture.png", "sha256": "..." }`; files must exist and hashes match. |
| `objective_box` | `[x, y, to_x, to_y]` normalized OCR region from the actual captures. |
| `max_seconds` | Positive whole-segment bound, at most 1800 seconds. |
| `steps` | 1–20 ordered steps, including TRAVEL, DIALOGUE and COMBAT. |

Every step has `screen`, exact observed `objective`, an exported precondition
`marker`, a distinct `post_marker`, and positive `timeout` at most 600 seconds.
`screen` may be TRAVEL, DIALOGUE, CUTSCENE, CHOICE, COMBAT or COMPLETE. UNKNOWN,
PUZZLE and QTE are unsupported and pause without blind inputs.

TRAVEL has a nonempty `movement` list of `[key, seconds]` pairs calibrated for
this segment. COMBAT hands control to the existing `BaseCombatTask.combat_once`
engine under the segment deadline. DIALOGUE and CUTSCENE wait passively. An
optional DIALOGUE `autoplay_marker` must identify a separately observed **enable
Semi-Auto** control; it generates one click and never a skip/advance click.

CHOICE pauses unless both `Allow Reviewed Neutral Choice` is explicitly enabled
and the step supplies `neutral_choice`, the exported marker for the exact
reviewed neutral option. Unexpected choices always pause. Neither a named
feature nor the word “neutral” establishes the option's meaning without review.

`Observed Game Version` is an explicitly operator-observed runtime value. Its
comparison with the profile prevents a known mismatch; configuration alone is
not independent evidence that the installed game version was verified.

## Recording adapter

Story Watch never starts, stops, reconfigures or claims continuity of an existing
recording automatically. When `Recording Required` is enabled, the application's
existing recorder integration must supply `executor.recording_status()` returning
a fresh dictionary with `active`, `output_path`, monotonic `observed_at`,
`limits_enforced`, `max_seconds`, `max_bytes`, `remaining_seconds` and
`remaining_bytes`. The task checks freshness (at most two seconds), an actual
output file, positive consistent allowances and output growth on completion.
Missing status or enforcement evidence pauses the task. No recorder adapter is
invented or enabled by this candidate; recording continuity remains a live gate.

## Offline verification

Run from the candidate worktree:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestStoryWatch.py -v
```

The suite checks cancellation/restart no-skip behavior, inherited trigger entry
points, stale/wrong-window observations, mismatched version/objective, unknown
screens, postcondition freshness, bounded timeouts, choice policy, failure
propagation, evidence hash drift and recording status/output/limit checks. These
tests use simulated observations and do not qualify any quest route.
