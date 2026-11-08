# Upstream integration

Refreshed 8 November 2026 with Git fetch and GitHub PR metadata.

| Source | Exact revision/state |
| --- | --- |
| Fork master | d13798d2e46dbb913f0c167e664d29cba6d1174b |
| Incorporated ancestor | 61bfa64 (merge-base) |
| Upstream master selected | f497bd8400372ac514b810700241a663ff53b79f |
| Stable comparison | v3.7.19, ad251fbdd25a4908dbf72dea3d8d34a15efc661e; ok-script 3.0.3 |
| Local upstream integration | 0bf94854; upstream master uses ok-script 3.0.4 |
| PR 1837 | Open, unmerged, 61464cb8c78a4d9ac6a5a98ecd5cafa5ab58e939 |

The primary checkout stayed on `qa/android-gt30pro-validation` at b3dc536f with
its three local QA commits preserved. Work uses the isolated
`codex/core-and-routes-20261108` branch/worktree. No remote merge or release is
authorized/performed. Android remains outside this scope.

The local upstream integration retains JH overworld assets, calibration hashes,
controller/planner/localizer/route follower, custom-character support and task
registrations. Configuration conflicts were resolved by retaining both HuntMob
and upstream Tacet Elimination entries. FarmMap retains JH's shared navigator
and adds upstream icon/logger changes. Translation catalogs retain upstream
entries and missing JH entries, then are compiled. Upstream split templates,
Qt GUI configuration, task grouping/icons and account config migration are
incorporated with their owning source changes.

## Framework and dependency contract

The primary `.venv` contains ok-script 2.0.7b1. It was not upgraded. The candidate
has its own `.venv`, created through the primary repository interpreter, with
the exact upstream `requirements.txt` pins installed: ok-script 3.0.4,
ok-pyside-minimal 6.12.0.post2, onnxocr-ppocrv5 0.0.23 and the remaining lockfile
dependencies. `pip check` passes. Python is 3.13 on this machine; the upstream
lockfile's generated-header Python 3.12 label is provenance, not a claim that
this verification ran on 3.12.

Actual installed API inspection matters: TaskExecutor.interaction is read-only
and selects device-manager or executor-thread job overrides. The guard wraps
those owning objects, handles backend rebind, preserves `_wait_for_activity`
arguments, and hooks framework pause/stop before task input. Tests use the
actual installed TaskExecutor property/lifecycle signatures with fake effects.
Queued callbacks are epoch-bound; cleanup tries all tracked adapters. Foreground
Pynput gestures require the verified game foreground at every delivery, release
tracked inputs after focus loss and fail early if foreground capture cannot
start. Automatic pre-run focus is suppressed; manually focus the correct game
before using a foreground backend. Live Pynput compatibility is unqualified.

## PR 1837 adaptation

The complete diff, task, 27 author tests and shared BaseWWTask changes were read.
The task/parser is adapted with attribution to EEEEEEEdison; the upstream
license and project attribution remain in place. PR translations/README were
reviewed as part of the diff; the JH metadata/docs describe the modified policy.
`task_icons`, `reset_combat_state`, framework APIs and `force_single` come from
the integrated revision, rather than copying CultivationTask alone.

Adaptation adds explicit spend/run/time/minimum-current-balance bounds, durable
pending/confirmed/uncertain records, immediate no-refill guards, both-sided
observed debit verification and actual item-detail inventory receipts. No
startup allowance based on all available Waveplates remains. Confirmation is
issued once, then only results are observed. Unknown costs stop. Challenge
start/restart has an observed semantic helper independent of narrative skipping.

Author-reported 129→69→9 Waveplates and 4→8→13 inventory, and author test counts,
are **upstream reports**, not JH live evidence. JH offline results and local
runtime observations are recorded separately in [status](AUTOMATION-STATUS.md).
No TH.GL code/DLL, PR1324 wholesale adoption, game-memory access, game-file
changes, injection or packet manipulation was introduced.
