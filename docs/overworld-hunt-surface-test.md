# Phase 4 surface test

**Phase 4.5 update:** use [the controlled live-validation procedure](overworld-hunt-live-validation.md).
Localization Only now defaults to true; execution is restricted to exactly
one generated camp and Max Camps 1 until the live validation is reviewed.

`HuntMobTask` is registered as **Overworld Mob Hunt (Surface Test)**. It uses
the existing `DryRunRoutePlanner`, `WorldRouteNavigator`, `HuntSession`, and
`BaseCombatTask.combat_once()`. No network fetch occurs during a hunt.

## Prepare a local area

The Phase 1–3 locator returned pixels in a remembered map image; those are
not Kuro coordinates. This MVP requires a manually calibrated local image.
There is no bundled, verified live profile yet.

1. Pick one small, open surface area with one known mob and 1–3 camps. Verify
   the actual routes and every spawn against the local Kuro `map_items.db`.
   Record the exact item id/name, state id, floor id, and location ids.
   A blank floor id alone does **not** prove a point is on the surface.
2. Prepare a north-up map image at the same scale as the live minimap,
   following the image-matching principle used by `FarmMapTask`. Keep all
   selected camps and travel between them inside this image. No cave,
   elevation transition, water crossing, or unverified obstacle route.
3. Calibrate at least two separated known landmarks. For image pixel `(u,v)`,
   Kuro coordinates must be `x = origin.x + u * units_per_pixel` and
   `y = origin.y + v * units_per_pixel`. Verify a third landmark independently.
   Scale must be uniform and positive; screen/Kuro units are not meters.
   Record the capture resolution. Do not use uncalibrated world-unit guesses.
4. Save a JSON profile alongside the image (paths are relative to this JSON):

```json
{
  "surface_verified": false,
  "map_image": "local-area.png",
  "kuro_database": "../../wuwa-map/map_items.db",
  "target_mob": "EXACT_KURO_ITEM_ID_OR_NAME",
  "state_id": 8,
  "floor_id": "",
  "origin": [0, 0],
  "units_per_pixel": 1,
  "frame_size": [1920, 1080],
  "match_threshold": 0.7,
  "spawn_ids": ["VERIFIED_LOCATION_ID"]
}
```

These are placeholders, not a usable calibration. Set `surface_verified` to
true only after validating the area, coordinates, and selected location ids.
Keep the same north-up minimap mode and resolution throughout the run.
Start already standing in this surface area with the world HUD visible.

## First run

Set **Target Mob** to the profile's exact target, **Hunt Profile** to its JSON
path, **Safe Test Mode** true, and **Max Camps** 1. Teleport and motorcycle
must be false; Surface Only must be true. Unsafe values are rejected before
input. Do not increase camp count during Phase 4.5. Start with Localization
Only true; turning it off enables live movement and requires prior A/B review.
Safe mode alone is not a dry run.

Max Camps counts distinct camps admitted to the run, including failed camps.
Max Camp Retries allows 0–3 additional attempts. Each navigation/approach
has a 60-second timeout. Four recovery stages allow camera centering,
jump/forward, right detour, and left detour; utility/grapple is disabled.
The existing bearing helper may sprint. No automatic teleport, including
death recovery, is permitted. Death stops the run for manual recovery.

Tuning is deliberately restricted: merge radius is 20 calibrated pixels,
arrival radius 8 pixels, and the initial cost model assumes 10 pixels/second.
Distances are converted to Kuro units with the profile's scale. These are
pilot defaults requiring live calibration, not measured game speeds.
If the planner proposes TELEPORT as its next step, the local hunt finishes.

## Execution and ownership

```text
INITIALIZE → LOCALIZE actual position → PLAN → TRAVELLING
  ARRIVED → APPROACH all known spawn points → CLEAR_CHECK
    quiet for 3 seconds + no health/target evidence + still at camp → CLEARED
    enemy evidence/local check failure → RETRY → FAILED after retry limit
  COMBAT → release navigation inputs → existing combat_once()
  every combat / clear / failed attempt → LOCALIZE actual position → PLAN
  exhausted local camps / Max Camps → COMPLETE
  cancellation → CANCELLED → release inputs
```

Only the first step of each plan is used. Combat en route never clears the
destination camp. Even combat during approach or clear verification discards
the previous approach and replans. Six combat interruptions without clearing
a camp consume one failed attempt, preventing an endless reacquisition loop.

Navigation releases WASD, jump/tool recovery keys, and right/middle mouse in
cleanup. If release fails, combat handoff is refused. Cancellation raised by
OK-Script is kept distinct from a failed camp. `hunt_run` retains session
cleared/failed sets, retry counts, state, and completion reason for this run;
starting again creates a fresh session, with no cross-day completion cache.

## Verification and limits

Run with the repository's Python:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.TestHuntController tests.TestHuntPlayerLocator tests.TestHuntMobTask tests.TestRouteFollower tests.TestOverworldMobHunt tests.TestMap
```

Fakes cover state transitions and ownership; they do not establish live
recognition quality. Verify map calibration, minimap scale, facing detection,
matching confidence, obstacle recovery, cancellation while keys are held,
combat handoff, and enemy reacquisition in the live game before increasing
the run size. The task checks resolution, HUD, image confidence, map bounds,
and the curated spawn list. It cannot independently identify the current
state/floor from the HUD; those are supplied by the verified surface profile.
Repeated terrain can yield false image matches. A failed or ambiguous
localization stops the run rather than inventing the player's position.

Clear verification is a bounded visual heuristic, not a target kill counter.
Already empty camps can pass; hidden enemies or incomplete source data can
still evade detection. No target species recognition, material resolution,
loot accounting, or exhaustive visual scanning has been added.
