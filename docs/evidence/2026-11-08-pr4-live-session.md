# PR4 live qualification continuation

Base: `8f4d505c4876ecf8f4ffdff8cca29086538b56b9`, Python 3.12.14,
ok-script 3.0.4. Spending remains disabled: persistent resource profile `{}`;
no resource-consuming action was attempted.

## Measured observations

- Launched the candidate through Windows RunAs. Serving process 55092 reported
  elevated=True, UIAccess=False and passed the existing access checker against
  game HWND 17045030. This resolves the original privilege mismatch for that
  serving process, rather than assuming the client and server have equal rights.
- Registered StoryWatchTask guard harness run
  `8de469c62c174666bf7fddd07d8eb2d0` succeeded. It verified persistent no-skip,
  suppression of the inherited dialog trigger, cancellation protection and
  restoration of the lock from disk. No played dialogue/quest segment is claimed.
- Fresh MCP captures showed event menus, not a camp or active story segment.
  Terra medium inspected the screen read-only. Its initial CUA capture preceded
  reading the installed restriction; subsequent captures used official MCP.
- Bounded Esc attempts `6c4898d4f0484030a77518d0f321e0c3` and
  `4ddafbc907c94c97b551b7e8d49c3799` stopped before key delivery with
  `Target game window unavailable`. No successful menu-close action is claimed.
- Read-only window probe `3a70165b9c414a79afb81748bc87661c` found matching
  capture/input HWND, exists=True, OS-visible=True, non-iconic, but framework
  `visible=False`. Installed `hwnd_window.py:283` assigns that field from
  `is_foreground()`. Thus our guard incorrectly excluded covered windows.

## Corrective work

The guard now checks OS visibility/non-minimized state when the framework
foreground flag is false. Capture identity, fresh-frame, input-privilege and
foreground-backend delivery checks remain in force. Nineteen adapter tests pass,
including a new covered/hidden/minimized regression. Terra's independent narrow
source review found no blocking defect; mocks do not establish live delivery.

The owned process 55092 was exited through MCP before restarting changed helper
code. An intervening restart was cancelled without a visible UAC prompt. The
next RunAs launch succeeded: serving process 45940 independently reported
elevated=True, UIAccess=False and passed the access checker against the game.
No UAC controls were automated.

## Actual input and replacement-runtime checks

Run `22374898644d4eadb80724e7c9f8f473` issued one map key. Fresh capture
`42f49158940341c380c54b465238c5e3.png` showed the map. Run
`d76a69720811466ab2f57c7dadc09b75` returned to a verified world state. These
observed transitions establish bounded live input delivery after the fix.

Registered Story Watch guard harness `5383ba99be5b41be9b1944f03b0368ce`
passed on the replacement runtime: no-skip, AutoDialogTask suppression,
cancellation protection and restoration from disk. It did not play a segment.
The observed objective was Shades of Battle / Talk to Ceshi / 1329m, in
Xuanfang Hold. No reviewed travel/dialogue/combat profile was available there.
No choice, native Semi-Auto, story combat or quest completion is claimed.
The installed game version was not found in inspected Sounds/Other settings or
executable version metadata; it remains unobserved. No setting was changed.

## Single-camp localization rejected

An exact-type localization-only HuntMobTask may now run while the story lock
stays active. Its entire activity forbids game input even if config changes
mid-run. Lookalikes and movement-enabled Hunt remain refused. This fixes the
class-name/config-mutation gaps identified in Terra's initial review.

Run `273aec4d6cf54c668a321248f3775f59` returned without samples because the
MCP task lifecycle was disabled/paused; it is not a localization pass. The next
harness restored lifecycle flags in finally and required ten actual samples.
Run `6ea0534f4a3849c5bc1c2f2e463524c6` failed on stationary sample 1 against
`academy-native-reference-01/profile.json`: no candidate and no feature support.
No movement or combat began.

Run `1b8cf30e84f043f3a58343e553eaf767` collected ten stationary frames and a
current full-map screenshot, then verified return to world. Offline
`scripts/register_surface_capture.py logs/live-pr4/calibration-current`
rejected all 10 positives and accepted 0 of 90 negatives. First positive:
score 0.144670 (<0.7), margin 0.055583 (<0.363403), coverage 0.009706 (<0.1),
gradient/SIFT disagreement 6.046244 pixels (>1.481737). No matcher sidecar was
produced. Acceptance thresholds and qualification flags were not relaxed.

Terra medium independently inspected the captures/report. Matches clustered
around prominent overlays rather than distributed terrain. Overlay contamination
is a plausible cause, not a proven diagnosis. World registration also needs
distributed independent validation. The next gate needs a clean same-layer
reference, distributed static landmarks, independent positions and negative
controls before a bounded walk/combat/clear trial. The historical empty-camp
return remains excluded from combat trials.

## Verification and final persisted state

`scripts/verify_core_routes.py --all --output logs/live-pr4/regression` passed:
799 tests, 76 modules, zero failures, using separate Qt processes and repository
Python. See `2026-11-08-pr4-live-regression.json`. This working-tree run includes
19 adapter tests for covered/hidden/minimized windows, exact-type read-only Hunt
admission and mid-run config mutation. The preceding baseline had 797 tests.
Terra's final independent source review found no additional blocking defect.
Simulated tests do not establish live localization or farming.

Run `2d7049946ae646d08ef6ac9deb0b665e` verified the final world state after
closing settings/Terminal. After the guard recheck,
`04ce4a5db78f4065a248130c142cfde7` verified world and persisted PAUSED,
STORY_WATCH, story_locked=True, skip_approved=False and resource_profile={}.
Only the primary agent issued input. No queued farming/spending was enabled.
Raw screenshots contain account identifiers and remain local; the companion
JSON retains numerical replay, source hashes and compact verification results.

## Still pending

Observed Story Watch dialogue and a complete
travel/dialogue/combat segment, single-camp localization/walk/combat-clear loop,
eligible repeated sessions, and material inventory receipts. No claim, kill,
quest completion, reserve use, purchase, or live qualification PASS was invented.
Raw capture/log evidence remains local under `logs/live-pr4` and `logs/mcp`.
