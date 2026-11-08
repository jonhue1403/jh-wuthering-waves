# Live qualification: LIVE_VERIFICATION_PENDING

8 November 2026, Asia/Kuala_Lumpur. The candidate is source/offline verified;
resource consumption, story completion and route/combat qualification remain
pending. All new resource/route tasks default to preview, and hunt defaults to
localization only. No paid API is required or enabled.

## Observed local conditions

- Read-only desktop inspection showed the English quest menu, “Shades of
  Battle”, “Talk to Ceshi”, 1329 m. No input was issued by that inspection.
- The existing privilege checker, with game HWND 17045030, reported that the
  game is elevated and this Python process is not. Movement/claims were not
  attempted; no elevation, backend bypass or anti-cheat workaround was used.
- Candidate 3.0.4 MCP initialized, exposed task/skill discovery and captured a
  fresh 2560×1440 WGC frame (`cached=false`). That frame showed an Echo Erase
  event board. The candidate issued no gameplay input; no score/action/quest
  outcome is attributed to it. This is capture evidence, not a farming result.
- Runtime/capture observations do not establish installed game version, account
  reset identity, compatible Chinese Guidebook UI, Semi-Auto controls, camp
  respawn, material drops, or recording continuity. No recorder was modified.

## Precise local progression

1. Keep only one game controller running. Preserve any existing recording and
   verify its output grows and its actual time/storage limits when recording is
   required. Start this candidate with matching game/runtime privileges through
   the normal trusted launcher. Do not elevate or replace another user's runtime
   silently. For foreground capture, manually focus the verified game window.
2. From this worktree run `.\.venv\Scripts\python.exe -m ok mcp --config config:config --port 0`.
   Discover `logs/mcp/connections/*.json`, validate live PID/listener/project,
   and keep bearer tokens private. Read server develop skills/list_tasks. Capture
   read-only; confirm timestamp, `cached`, HWND/region and installed game version.
3. Activate Story Watch before entering narrative content. Confirm the durable
   guard and that an old enabled Skip Dialog preference cannot send input after
   pause, cancel, exception, takeover or restart. Explicit NORMAL selection must
   require a fresh safe world frame; it is the only skip-policy opt-in.
4. Review profile/reference/database/source hashes for the original surface camp.
   Run localization only first, then short test-walk with cancellation/takeover.
   Write a reviewed Runtime Qualification sidecar for the **next** permitted
   stage; it records permission, not a completed trial. Run one complete
   combat-clear loop, reread inventory and relocalize. Repeat only in independent
   eligible respawn sessions. Empty camp returns do not count as combat trials.
5. Capture real identity/reset and claim screens in the supported locale; author
   named templates through the OK COCO/export pipeline. Configure explicit
   account/server/observed budget-cycle profiles and spend/run/time/minimum
   limits. Inspect the preview. First validate a zero-spend cancellation, then
   one bounded claim and actual inventory receipt. Exercise single/double/plain
   dialogs, insufficient current/positive reserve, changed observations, delayed
   result and interruption after Claim. Never repeat a pending/uncertain spend.
6. Reconcile through Resource Goal and Routine Queue's read-only “Reconcile
   Pending Only” mode using the exact observed account/server/activity/cycle,
   fresh balance and item inventory. Unreconcilable or wrong-cycle records stay
   UNCERTAIN. Inspect journal locks only after verifying no controller is alive;
   do not delete journals to make a retry pass.
7. Calibrate current routine completion/reward profiles and repeat after completed
   work to verify skip behavior. Weekly boss material eligibility is separate
   from Echo farming. Capture current Fantasies Weekly Activity; the legacy
   Remnant Crystal claim path is disabled. Material Locator/Blitz stays disabled
   until its actual installed-version UI is captured.
8. Capture one story segment with travel, dialogue and combat. Follow
   [Story profile requirements](STORY-WATCH-PROFILE.md), preserve all narrative
   playback, and pause on unknown puzzles/QTEs/choices. Verify existing-engine
   combat returns to playback and useful paused objective text on unknown states.
9. Only after core/single-camp evidence review, qualify one known material/pickup
   route using [the route procedure](overworld-routes.md). Prove the material to
   mob/source mapping from real game/project data, actual item-detail increments,
   every connecting segment and post-combat localization. Add second/third camps
   only with their own observations. Known-beacon loading/destination checks
   require separate qualification. No arbitrary floors/cliffs/motorcycle routes.

Retain raw screenshots/logs privately and record hashes and exact source/runtime
revisions. Do not convert offline fixtures or author-reported results into live
PASS entries. GUI Start behavior and recorder continuity need their own evidence.
