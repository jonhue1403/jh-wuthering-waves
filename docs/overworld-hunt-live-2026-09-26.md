# September 26 live surface validation

The controlled single-camp workflow passed live at the Startorch Academy exterior:
localization, short walking, cancellation, combat handoff, post-combat localization,
spawn approach, clear checks, and input cleanup. A second return/clear run also
passed at the already-cleared camp. It was **not** a second combat trial or proof
of reliable unattended farming across other areas.

## Evidence

The compact run records and timestamped hunt events are in
`assets/overworld/calibration/live-verification-20260926/`. Original full-resolution
screenshots remain local; their hashes are recorded in `runs.json`.

| Check | Capture/run suffix | Result |
| --- | --- | --- |
| Initial live localization | `T051508703588Z` | Ten accepted samples; 0.044 reference-pixel spread |
| Dense-feature localization | `T052222063685Z` | Passed before the first successful short walk |
| Short walk | `T052254595683Z` | ARRIVED; cleanup succeeded |
| Cancellation during movement | `T052334426767Z` | CANCELLED; cleanup succeeded |
| Native-reference localization | `T053553186616Z` | Ten fresh readings passed the one-pixel stationary limit |
| Native-reference short walk | `T053633053681Z` | ARRIVED; no recovery |
| Camp run with combat | `T053719064346Z` | COMPLETE; one cleared, zero failed |
| Move away for return check | `T053847429175Z` | ARRIVED |
| Return/clear check | `T054012228378Z` | COMPLETE; one cleared, zero failed; camp already empty |

The target is the exact Kuro database mob `噼啪啪`, spawn
`1453530316921958400`, state `906`, empty floor, at `[-103400, -542000]`.
Surface status was reviewed from exterior screenshots and map landmarks; an
empty database floor alone does not establish surface status. Combat recognized
Chisa, Hiyuki, and Lucilla. No teleport or motorcycle was used.

## Fixes exposed by gameplay

- Bright POI icons overwhelmed raw gradient correlation. The opt-in `bounded64`
  representation caps edge magnitude identically in query and reference.
- Standard SIFT supplied too few matches after moving. Opt-in `dense` SIFT uses
  five octave layers and contrast threshold 0.02. Distinct source/target keypoints
  are still counted once, and the coverage floor was strengthened to 0.1.
- Arrow appearance varies with its white highlight. Hunt heading now matches the
  centered yellow-and-white silhouette, normalized by area, with explicit shape
  confidence and angular-ambiguity checks. Pure white icons are rejected.
- Short sideways recovery could not escape a large tree. Hunt detours now back
  away for 0.5 seconds, then sidestep for 1.5 seconds, with `finally` key release.
  Existing FarmMap defaults remain unchanged; short-walk validation has no recovery.
- Exhausted camp failures were overwritten with COMPLETE. A session containing
  failed camps now ends FAILED with explicit failed/cleared counts, while still
  allowing other camps in the session to be attempted.

Historical calibration files retain their original representation and feature
settings. The 0.700 localization score threshold, independent geometry, distinct
peak margin, reference hashes, movement preflight, and input cleanup gates remain.

## Reference construction

`scripts/register_surface_capture.py` transfers the previously checked surface
map geometry using terrain matches split before fitting. The map registration
had 142 training inliers and 69 held-out supporting matches; the largest supported
held-out error was 0.636 full-map pixels. Minimap scale fitting used nine training
inliers and seven held-out supporting matches, with maximum error 1.665 pixels.
Descriptor outliers are retained in the report rather than concealed.

The nearby ground beacon provides another check: its visible cyan top matches the
earlier beacon icon shape. Transferring the icon's full height places its center
at approximately `[1282.5, 707]`, within three full-map pixels of the database
projection. The earlier indoor-beacon fit failed and was not used.

`scripts/build_minimap_reference.py` then places native minimap terrain tiles into
that coordinate system. Each tile registers independently to the original full-map
reference, preventing chained registration drift. Player arrows and circular rims
are masked out. It refuses to overwrite an existing calibration and resets the
localization/navigation review flags in its output profile.

The final reference at `assets/overworld/calibration/academy-native-reference-01/`
accepted 30 saved samples across three poses and rejected 270 negative controls,
including rotated, absent, blank, duplicated, and forced strong-feature duplicate
cases. No distant location exceeded the score threshold on those positives.
Frame 1 of each pose contributes a tile; subsequent stationary frames are
correlated. These replay counts are not independent live success rates. Fresh
localization and walking were therefore run after reference construction.

## Runtime and remaining limits

The gameplay above ran with the previously installed `ok-script` 2.0.5 runtime.
The runtime has now been upgraded to upstream's required 2.0.7b1, and `pip check`
passes. **255 regression tests passed on the upgraded runtime**: 159 hunt,
navigation, calibration, heading, and integration tests; 71 character tests;
and 25 map, configuration, combat, loader, and wide-dialog tests, with Qt suites
run in separate processes. Logs and counts are listed in `verification.json`.
Its clean restart verification against the running game is still outstanding.
Background-task preferences were restored after requesting framework exit, and
both old project Python processes and the old local web server were verified shut
down before beginning the upgrade. Temporary custom tasks were removed.

The built-in Hunt task is configured with the reviewed local profile and defaults
back to **Localization Only=true**. The reference covers a local exterior area;
it is not a world-wide map, obstacle planner, dynamic layer detector, or assurance
that an enemy has respawned. Repeat combat after respawn and broader route trials
remain necessary before unattended use is justified.
