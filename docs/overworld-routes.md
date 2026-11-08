# Bounded material routes

Status: **LIVE_VERIFICATION_PENDING** on the 3.0.4 candidate. The original
`HuntMobTask` retains exactly one camp, mandatory safe surface mode, no teleport
or motorcycle, and localization-only default. `BoundedRouteTask` is a separate
task with preview and localization-only defaults. It supports one to three
explicitly reviewed camp segments; a fourth camp is rejected.

The current project evidence has one combat-and-clear trial on ok-script 2.0.5.
The later 2.0.7b1 return was to an empty camp. Neither is a combat qualification
of 3.0.4. No material drop, new camp, route, or beacon transition is certified
by these new offline tests.

## One-camp runtime gate

`Runtime Qualification` is a separate reviewed JSON sidecar. Missing or stale
sidecars stop movement before task startup. Read-only localization can run
without one. `Observed Game Version` must match a version actually observed in
the target game; it is not inferred from the PC date, launcher, or dependency
version. Existing `localization_verified`/`navigation_verified` profile flags
are retained as historical evidence and do not silently qualify a new runtime.

Sidecar fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `status` | `1`, `REVIEWED`; not a live PASS flag |
| `ok_script_version`, `game_version` | Exact tested runtime and observed game version |
| `state_id`, `floor_id` | Exact profile map/layer |
| `permitted_stages` | Reviewed progression permission: `WALK`, `SINGLE_CAMP`, `MATERIAL_ROUTE`, or `BEACON` |
| `bindings` | SHA256 of `profile`, `reference`, `database`, plus `matcher_calibration` when used |
| `source_sha256` | Hashes of the files in `qualification.REQUIRED_SOURCES`; route/beacon stages also bind `material_route.py` and `BoundedRouteTask.py` |
| `evidence_sha256` | Relative evidence file paths and SHA256 digests; files must exist and match |
| `independent_review` | `true` only after independent review of the actual evidence |

Permitted stages describe the next bounded test reviewed from its prerequisite
evidence; they are not completed-stage results. For example, a current-runtime
read-only localization and landmark review can permit `WALK`; its successful
observed walk and cancellation evidence can permit `SINGLE_CAMP`. Record each
actual attempt's result separately. Do not fill sidecars from unit tests or
mark historical evidence as a new qualification. Source/profile/reference/DB
changes invalidate the binding and need renewed review.

## Route manifest and material receipts

A route JSON is loaded only when `schema_version=1`, `status=REVIEWED` and
`surface_only=true`. It contains a `route_id`, exact `profile` path and its
`profile_sha256`, `state_id`/`floor_id`, one to three ordered `segments`, a finite
positive `rejoin_radius`, and `max_seconds` between 1 and 1800. Each segment has
the generated `camp_id`, exact `spawn_ids`, two to 32 observed world-coordinate
`waypoints`, and an `evidence` key present in `evidence_sha256`. All profile
spawns must match exactly, never a silently selected subset.

The route uses the existing `DryRunRoutePlanner`, `HuntController`,
`WorldRouteNavigator`, `WWTaskNavigationBackend`, locator and bounded recovery.
Reviewed waypoint order replaces direct centroid shortcuts. After a combat
interruption it stops, relocalizes and may rejoin only within the configured
radius of an observed waypoint. Leaving the reviewed area pauses/fails with
manual relocalization required. The route budget includes inventory reading
and pickup; cancellation/cleanup failures propagate through the controller.

`material_source` requires `kind=observed_mob_drop`, `material_id`, `target_mob`,
`item_text`, and a hashed `evidence` file. Unknown mappings are unresolved. The
existing Kuro project DB currently proves the camp's mob ID `310000820`
(`噼啪啪`) and spawn coordinates, but its `item` table has only id, name and icon;
its state/country/item/location tables do not establish a material drop table.
Consequently, **no real material route manifest is supplied or enabled**.

The route's `inventory_reader` requires a reviewed screenshot evidence key,
an actual existing item-detail `screen_feature`, exact `item_text`, normalized
`label_box` and `quantity_box` rectangles, and bounded `open_steps`/`close_steps`.
Each step requires an observed `screen_feature` and exactly one existing
`click_feature` or a qualified `b`/`m`/`esc` key. It is issued once, followed by
fresh-screen verification; no unknown screen causes an input retry. Named
features must be authored/exported with ok-script's existing COCO pipeline.
No synthetic screenshots or new invented game features are installed here.

The reader accepts two consecutive matching item/count observations in at most
three fresh frames, using strict normalized integer parsing. Its `pickup`
requires hashed evidence and the exact observed `prompt_text`; at most one
recognized F interaction is issued per cleared camp. Inventory is reread even
if no pickup prompt or enemy is present. Received quantity is the actual
nonnegative inventory delta. Decreases, stale/duplicate frames, wrong items or
unknown screens stop with uncertainty. Combat return, camp-clear and issued
pickup remain distinct from material receipt and goal completion.

`User Material Target` is explicitly labelled user supplied. It must be positive
for execution. Observed inventory already at target skips navigation/pickup;
observed target completion stops before the next camp. Exhausting the camp or
time bound with a deficit does not report the material goal as complete.

## Known-beacon transition primitive

Beacon travel remains separate from the walking route task. The
`known_beacon_transition` primitive requires a `BEACON` runtime permission and a
`known_beacons` sidecar entry keyed by the explicit beacon ID. The entry binds
`destination: [state_id, floor_id, x, y]`, a measured `destination_radius`, and a hashed transition evidence key.
The supplied recognizer must return fresh, distinct `TransitionObservation`
frames. It requires `BEACON_READY`, issues the qualified action exactly once,
observes `LOADING`, then requires `WORLD` and fresh localization within the
reviewed destination radius. Unknown/stale screens, missing loading, timeout,
wrong layer or cancellation fail without repeating the transition.

No target-specific beacon screen adapter is enabled: compatible screenshots
and a complete observed transition are missing. This primitive does not enable
arbitrary teleport selection, map routing, floors, cliffs or motorcycle use.

## Exact next local qualification steps

1. Close other automation input owners. Preserve any recorder. Start the
   candidate runtime through the project's ok-script MCP launcher with matching
   game input privileges; verify its project/version/PID and exclusive ownership.
2. Observe and record the actual game version and safe surface/layer. Use the
   existing academy reference and one-camp spawn only if fresh landmarks,
   reference hashes, capture dimensions and the actual visible area agree.
3. Run localization-only, review confidence/spread and independent absolute
   landmarks. Record fresh artifacts; authorize only the short observed walk
   stage in a reviewed runtime sidecar. Check cancellation, held input release
   and manual takeover during that walk.
4. After observed walk success, permit one single-camp attempt. Record actual
   combat, clear, pickup state, post-combat localization and cleanup. Repeat in
   independent eligible respawn sessions; an empty return is not combat.
5. Identify one actual desired material from a visible mob/drop/item-detail
   chain; preserve source/item identity and before/after inventory screenshots.
   Author/export the real item-detail features and review the inventory steps.
6. Observe/calibrate a second surface camp and the entire connecting waypoint
   segment. Bind the expanded profile, DB, source code and evidence hashes.
   Preview the two-camp manifest first; qualify localization, then one bounded
   route including inventory verification and interruption/cancellation checks.
7. Add a third camp only after its segment has separate observed calibration
   evidence. Keep total maximum three. Separately capture a known-beacon ready,
   loading and destination chain before supplying its adapter/permission.

Offline test fixtures deliberately use synthetic names and temporary files.
Their passing results establish policy and orchestration behavior, not in-game
recognition, inventory changes, kills, navigation or live PASS results.
