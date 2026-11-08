# Automation candidate status

Branch: `codex/core-and-routes-20261108`.
Worktree: `Z:\Game\jh-ww-core-routes-20261108`.
Overall: **LIVE_VERIFICATION_PENDING**; no release or merge.

Offline implementation covers A–C, single-camp runtime gates and the separate
bounded route extension. Reachable registered tasks provide session controls,
goal/routine preview, Chinese Guidebook cultivation, Story Watch, one-camp hunt
and reviewed material-route preview. New resource/route execution is disabled by
safe defaults and absent genuine qualification profiles. Story skipping defaults
off even with an older enabled trigger preference; explicit compatible NORMAL
mode and fresh safe-state verification are required to enable it.

The independent reviewer inspected actual diffs, task callers and installed
3.0.4 executor/backend source. Findings were corrected and affected checks rerun;
the final record is [AUTOMATION-REVIEW.md](AUTOMATION-REVIEW.md). Foreground input
requires manual game focus; automatic focus is not treated as qualified.

Verification uses `.\.venv\Scripts\python.exe scripts/verify_core_routes.py`
(add `--routes` for extension). It launches each module in a separate Qt process
and records exact SHA, dirty-at-start flag, process exit code, collected count
and log under `logs/core-routes/verification/results.json`. The committed evidence
summary records the measured candidate revision/results; imports/compile checks,
offline logic tests, saved-image tests and live observations remain distinct.

Primary checkout, user settings, local QA commits and Android work were preserved.
No live claims, inventory increase, combat clear, quest completion, recording
continuity or release outcome is claimed. Follow [LIVE-QUALIFICATION.md](LIVE-QUALIFICATION.md)
for the exact remaining steps, and [the capability matrix](AUTOMATION-CAPABILITY-MATRIX.md)
for supported profile/evidence boundaries.

## Initial measured delivery checkpoint (Python 3.13)

Implementation SHA: `241ea5d30a52532dfa1135ea17bb4157a9eeb2ab`.
Core commit: `354d4d7c`; separate route extension: `241ea5d3`.
The clean-SHA run passed **462 tests across 45 isolated processes**, with zero
failed/empty modules. `pip check`, compilation and catalog syntax checks passed.
See [the measured per-module record](evidence/2026-11-08-core-routes-verification.json).
Task names are translated in the five existing catalogs; new configuration/help
intentionally falls back to English/bilingual source pending locale review.

The exact committed source was restarted through local MCP and registered
ResourceRoutineTask preview run `04722c1b403843a09f144b331a6f81b5` reached
`succeeded`. Its assertions checked a labelled user target stays UNRESOLVED with
no source mapping, and restored task config. It issued no game input. This
validates registered preview execution, not GUI Start, resource spending or live
farming. The owned development runtime was shut down after verification.

Final handoff: activate the no-skip guard before narrative content; keep spending
and routes in preview until the profile/privilege/live gates are completed.
Use the local steps in LIVE-QUALIFICATION.md. No real known material/pickup route
or story segment is enabled; their complete bounded drivers await actual evidence.

## Supported Python 3.12 delivery checkpoint

Source SHA: `dc422e5276797448bbcdaf4c9506b44ef06a2fd9` (same implementation plus
preserved inherited CLI task order). Candidate `.venv`: **Python 3.12.14,
ok-script 3.0.4**, exact requirements pins. The clean-SHA run passed **463 tests
across 45 isolated processes**, including the new `-t 1` DailyTask compatibility
regression. `pip check` and compilation pass. See [the supported-runtime record](evidence/2026-11-08-python312-verification.json).

Registered ResourceRoutineTask read-only preview also reached `succeeded` through
MCP on Python 3.12, run `3ae70e3c92634b63a78e7052dfc2f950`; it verified the
labelled unmapped goal remains UNRESOLVED and restored configuration. No game
input was issued, and the owned runtime was shut down after its terminal result.
Independent source review found no additional material issues in the registration
change; the full 463-test run is root-measured evidence. All live gates remain.

After this documentation-only checkpoint, the final-head verification command is
`.\.venv\Scripts\python.exe scripts/verify_core_routes.py --routes --output logs/core-routes/delivery-head-verification`.
Its persisted results identify the final handoff SHA; it does not change source
or promote any live gate. The primary checkout remains clean at b3dc536f.
