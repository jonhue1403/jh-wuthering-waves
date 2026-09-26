# September 26 integration and validation record

Branch: `codex/finish-overworld-hunt`.
Upstream: `61bfa64`, integrated by merge commit `a6d59d1`.
Template submodule: `d3c70f3c1a941abe99dec2d6921c79c8810ab832`.

## Implemented

- Merged all six upstream commits, retained the fork's hunt translations, and
  recompiled all five translation catalogs.
- Retained the existing subpixel matcher work and its offline regression replay.
- Added an executable short-walk stage with a profile target, 1–30 second limit,
  no recovery maneuvers, no combat handoff, and cleanup on every navigation exit.
- Added explicit localization/navigation review fields to profiles and a fresh
  stationary preflight before either movement mode. Old profiles still support
  localization; they require review fields before movement.
- Enabled reviewed hybrid profiles for controlled movement. The matcher gates,
  score floor, one-camp limit, and surface/no-teleport constraints remain enforced.
- Kept navigation/preflight enemy detection read-only. General combat detection
  can retarget or press Escape, so it is invoked only while combat owns the task.
  Non-combat sleeps bypass monthly-card dialog handling.
- Made navigation cleanup failures fail the result and prevent stuck recovery.
  Reset reused task state before read-only localization and check cancellation
  during short-walk sleeps.
- Added a profile-draft helper that fits measured landmarks and checks independent
  error, database selection, layer, camp count, and reference bounds. It does not
  invent calibration evidence or automatically enable any review flag.
- Corrected a flaky character test whose equal buff timers made its result depend
  on successive wall-clock reads. Character rotation behavior was not changed.

## Verification

All commands used the repository `.venv` interpreter, with `QT_QPA_PLATFORM=offscreen`
and `PYTHONUTF8=1` for Qt tests. The selected regression modules passed **243 tests**:

| Group | Tests | Local log |
| --- | ---: | --- |
| Hunt, setup, navigation, saved-image replay, upstream integration | 147 | `logs/hunt-final-regression.log` |
| Character behavior and recognition | 71 | `logs/regression-TestChar.log` |
| Map matching and direction | 2 | `logs/regression-TestMap.log` |
| Configuration | 5 | `logs/regression-TestConfig.log` |
| Base combat | 2 | `logs/regression-TestBaseCombatTask.log` |
| Custom character loader | 8 | `logs/regression-TestCustomCharLoader.log` |
| Wide dialog recognition | 2 | `logs/hunt-dialog-regression.log` |
| Combat recognition | 6 | `logs/regression-TestCombatCheck.log` |

The 147-test group comprises `TestHuntController`, `TestHuntPlayerLocator`,
`TestHuntMobTask`, `TestHuntValidation`, `TestHuntProfileSetup`, `TestRouteFollower`,
`TestOverworldMobHunt`, `TestHuntDiagnostics`, `TestHybridMapMatcher`,
`TestSubpixelMapMatcher`, `TestCalibrationCapture`, `TestMultiAccountDailyTask`,
`TestMergeEchoTask`, `TestCharacterCodeTab`, `TestWaitLogin`, and `TestSkipDialogConfirm`.
Run other Qt screenshot modules in separate processes. Combining the GUI editor
test and screenshot framework in one process produced a QApplication singleton
error; the affected dialog module passed separately.

The subpixel replay reproduced 20/20 accepted positives and 0/210 accepted
negative controls. These are saved samples, not independent live trials.
`python -m pip check` reports no broken requirements. Translation syntax and
duplicate-msgid checks pass for all five catalogs.

## Early live attempts (superseded by subsequent validation)

The later [live validation report](overworld-hunt-live-2026-09-26.md) records the
successful controlled camp run. The following is the earlier blocker history.

The installed game was launched and its `Wuthering Waves` window was enumerated.
Capture failed with `FrameArrived timed out`; the recovery attempt returned
`GetCursorPos failed: Access is denied. (0x80070005)` during window activation.
No game movement, combat, or profile verification was performed by this task.

On resuming with the desktop available, WGC successfully captured ten fresh
2560×1440 frames at approximately 500 ms intervals. Metadata and an unchanged
historical-reference replay are in
`assets/overworld/calibration/surface-test-03-20260926/`. All ten frames were
rejected by the old reference/calibration. This confirms that the historical
profile cannot be reused at the current location; it does not identify the new
map layer. The original PNGs remain local.

The user closed the separate installed OK-WW v3.6.7 application, and window
enumeration confirmed its absence. The user manually opened the map, identifying
Startorch Academy. Ten full-map frames were saved in `academy-map-20260926`.
The four visible Academy beacon correspondences (database state 906, floor 30)
failed the preselected three-full-map-pixel accuracy limit: the held-out error
was 16.25 pixels. No profile was created from this fit; the player's floor is
still unverified. See that capture directory's `calibration-check.json`.

Desktop-control M/Escape and map-close inputs produced no visible response.
Read-only Windows token queries confirmed that the game process is elevated,
while the repository Python process is not. This privilege mismatch explains
the input blocker; desktop control needs a compatible privilege level before
movement can be tested. The user must handle application elevation themselves.
No movement test or hunt has run, and no review flags have been enabled.
The separately installed application is not this checkout; use the repository's
`main.py` for this feature.

After two user-requested restart/retry checks, the new Codex desktop, task, and
computer-control helper processes remained unelevated while the game stayed
elevated. Escape still did not close the map. Added a read-only process-token
check before movement preflight to report this mismatch explicitly. It also
stops when the target process cannot be checked, closes query handles, and leaves
localization-only mode available. It does not launch elevated processes or
interact with permission prompts. The actual game window reproduced the new
diagnostic. The 26 focused input-access, task-validation, and task-wiring tests
pass (`logs/hunt-input-access-tests.log`); these include four newly added tests.

The user's subsequent normal game launch created a new process, but it remained
elevated and did not respond to the desktop-control M input. Read-only resource
inspection found `requestedExecutionLevel level="requireAdministrator"` in both
`Client-Win64-Shipping.exe` and `Wuthering Waves.exe`; the launcher itself uses
`asInvoker`. No compatibility elevation override was found for these paths in
the queried user/machine AppCompat Layers keys. Normal launch therefore does
not remove the game's elevation requirement. Added `run-local.cmd` so the user
can start this checkout as administrator through the normal Windows action.
This does not elevate Codex or prove that live tests have passed.

At that stage, the outstanding validation steps were:

1. Fresh stationary captures and same-position full-map/layer evidence.
2. Review reference scale and independent landmarks; select a real mob and camp.
3. Configure the actual profile and verify live Test A.
4. Observe short-walk arrival/cancellation, then the one-camp combat/clear sequence.
5. Repeat the live sequence and record outcomes before claiming reliable operation.

Follow [the current guide](overworld-hunt.md) and later live report for current status.
No review flags had been enabled at that stage. Existing captures remain local; the
original dirty work is also retained in the named pre-integration Git stash.
