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
