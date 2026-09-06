# Phase 4.5: one-camp validation record and capture requirements

Status: **closed-dataset Phase 4.5A passes offline with an opt-in hybrid matcher; no live Test A, B, or C has been observed**.
The original color matcher still rejects all ten frames. A reference-bound
gradient/SIFT method accepts 10/10 saved frames and rejects 60/60 constructed
negative controls, including withheld controls, without reducing the 0.700 cutoff.
See `assets/overworld/calibration/surface-test-01/matcher_diagnosis/REPORT.md`.
The earlier failed report in `analysis/REPORT.md` remains intact as baseline evidence.
The character was subsequently knocked away: these files are a closed dataset,
not evidence of the current live position. A fresh safe-position capture set and
review are needed before live validation. Movement is not authorized. There is
still no selected mob, verified camp, or live profile in HuntMobTask configuration.

## Files/data to supply

Use a local folder such as `configs/hunt-validation/one-camp/`. Do not place
captures in `screenshots/`: the existing OK-Script test runner clears that folder.
Profile paths below are relative to the profile JSON; the task setting can use
an absolute JSON path. The surface-test-01 analysis provides a diagnostic candidate
reference and landmark CSV, not an accepted live calibration profile.

| File/data | What to capture or identify |
| --- | --- |
| `reference.png` | Original lossless local map image, north up, containing the player start, safe approach, and one camp. Terrain must be at the **same pixel scale as the minimap**, not merely the same screen resolution. Keep margins at least half a minimap around positions to be localized. No resizing by a chat app. |
| `stationary_001.png` through `stationary_010.png` | Full game-client frames, original resolution, approximately 0.5 seconds apart while standing still in the chosen area. Use the capture helper below. World HUD/minimap visible; no camera rotation, combat, map menu, or loading. These enable visual review alongside live Test A. |
| `landmarks.csv` | At least three unmistakable landmarks with `label,image_x,image_y,kuro_x,kuro_y,source_location_id`. Pixel coordinates are in **reference.png after any crop**. Use two separated landmarks for calibration and the third for independent error measurement. Include how each landmark was identified. |
| Camp evidence | Mob name/item id, area name, location id(s) for exactly one camp, screenshots of the camp and map/layer, and confirmation that the approach is open surface terrain without climbing, water, entrances, or transitions. |
| Safe Test B point | A manually checked nearby coordinate, with its landmark/source evidence, outside enemy aggro. Do not use an arbitrary offset from the player. |
| Database | Existing `Z:/Game/wuwa-map/map_items.db` can supply item/location records; identify the exact selected records. If using a different source snapshot, supply it. English mob names may not match this database. |
| Acceptance tolerance | Agree a stationary spread tolerance in **reference pixels** from the image scale and required arrival accuracy. It is not inferred from the observed noise. Absolute error is measured separately with a known landmark. |

The reference does not have to be a full game frame. PNG is recommended;
`cv2.imdecode(..., IMREAD_COLOR)` reads it as three-channel BGR and discards
alpha. The current matcher neither rescales nor rotates the minimap/reference
and does not perform SIFT or stitching. An arbitrary big-map screenshot or
Kuro tile is not automatically a valid reference. If landmark fitting requires
rotation, reflection, separate X/Y scales, or substantial residual error, stop
and correct the reference/calibration before testing movement.

The live minimap crop comes from the existing `box_minimap` feature. Its source
annotation is `(x=72, y=57, width=372, height=370)` at 3840×2160, scaled by
OK-Script to the live frame. Supply full frames so the actual crop can be
checked; do not manually substitute a visually similar crop. The matcher uses
the existing circular mask with a central rectangle about 1/4.4 of the crop
width/height removed. The matched rectangle's **center** is treated as player
position. Both this center assumption and facing recognition need live checks.

## Capture the stationary frames automatically (no hunt required)

Close other OK-WW instances so background automation cannot act. Launch the
game yourself, go to the selected surface location and stand still. From a
PowerShell terminal at `Z:\Game\jh-wuthering-waves`, run:

```powershell
.\.venv\Scripts\python.exe -m src.overworld.calibration_capture --profile surface-test-01
```

Switch back to the game manually when the helper logs its five-second delay;
keep the game visible and the character/camera stationary until completion.
The helper never focuses/resizes the game, sends keyboard/mouse input, starts
combat, teleports, or starts HuntMobTask. It uses OK-Script's normal capture
selection and `BaseTask.next_frame()` with a no-input interaction backend.
It does not crop, resize, annotate, or mask the returned game frames.

Output is `assets/overworld/calibration/surface-test-01/stationary_001.png`
through `stationary_010.png`, plus `metadata.json`. The profile argument is a
capture-set label; no calibrated profile JSON is required. Choose a new label
for a repeat: existing capture sets, including partial sets, are not overwritten.
Ctrl+C cancels. Missing frames, PNG errors, or a changed resolution fail the
capture; any partial output is retained and marked incomplete in metadata.

Metadata includes UTC host receipt timestamps (not game-render timestamps),
actual dimensions/backend per frame, requested interval/count, saved count,
profile label and completion state. Timing is best-effort: inspect the recorded
elapsed times if the capture backend or PNG encoding is slow. PNGs preserve
the raw HUD, including any visible UID; review before sharing.
This collects calibration evidence only, not a localization stability pass.

## Existing profile model, without invented calibration

The profile's filename/path serves as its id; no duplicate camp model is needed.

| Field | Required meaning |
| --- | --- |
| `surface_verified` | `true` only after manual surface/route verification; blank floor ids do not prove surface status. |
| `map_image` | Path to the calibrated reference image. |
| `kuro_database` | Path to the existing Kuro-schema SQLite database. |
| `target_mob` | Exact selected item id or name; must equal task **Target Mob**. |
| `state_id`, `floor_id` | Exact source layer. The locator reports these from the profile; it does not recognize them independently. |
| `origin` | Kuro `[x,y]` at the reference image's top-left corner, derived from measured landmarks. |
| `units_per_pixel` | One finite positive, uniform scale. `world_x = origin_x + image_x * scale`; likewise Y. Kuro units are not asserted to be meters. |
| `frame_size` | Exact `[width,height]` of OK-Script's captured **game frame**, not Windows desktop size and not reference-image size. |
| `spawn_ids` | Exact location ids for one verified camp. Coordinates are loaded from the database; the existing builder computes the camp anchor. More than one generated camp is rejected. |
| `match_threshold` | Current policy default 0.7, accepted range 0.6–1. This is a match score threshold, not positional accuracy or probability. Do not lower it to force a pass. |
| `localization_tolerance_pixels` | Optional positive stationary spread limit. Omission produces measurements only, never a stability pass. |
| `matcher_calibration` | Optional path to reference/mask/layer-bound offline gradient/SIFT calibration. Omission preserves legacy color matching. This opt-in is restricted to Localization Only; it cannot be used to start movement. No live profile is populated automatically. |

Two landmarks determine the candidate scale/translation; a third must agree.
No calibration numbers should be filled in until those correspondences exist.
The accepted localization bounds are the reference-image rectangle
`0 <= pixel_x < width`, `0 <= pixel_y < height`. The current model has no
separate bounds polygon or custom radius fields. Arrival radius is
`8 * units_per_pixel`; clear-check proximity is `16 * units_per_pixel` from
the nearest known spawn; merge radius is `20 * units_per_pixel`.
If these policies are inappropriate for measured data, review before movement.

## Controlled sequence

**A — Localization only.** Select the verified profile and target. Leave
**Localization Only = true** (new default), **Max Camps = 1**, **Safe Test Mode
= true**, **Surface Only = true**, **Use Teleport = false**, **Use Motorcycle
= false**. Start already standing in the world. This path skips normal task
startup, camera clicks, navigation, combat, and all key/mouse input. It takes
10 fresh samples at 0.5-second intervals using existing frame/locator APIs.

The `[HUNT] stationary_localization` log contains all coordinates, confidence
samples, maximum pairwise spread in pixels/Kuro units, and the supplied
tolerance result. A failure, unstable result, or missing tolerance does not
authorize Test B. A stable but wrong match is still possible: independently
compare the reported position with a known landmark. No test automatically
advances to the next stage. Inspect the live screen and preserve screenshots.

**B — Short walk, pending A.** Agree the safe point above after reviewing A.
Use the existing navigator for this single segment with a short, agreed limit;
do not invoke the camp controller or combat. Record bearing, decreasing
distance, arrival, cancellation response, and recovery events. A COMBAT result
ends this test and requires repositioning/review; do not turn it into Test C.
No new general-purpose movement/calibration automation is provided here.
The hunt toggle below is **not a Test B command**.

**C — One camp, pending B.** Only after A/B are observed to pass, set
**Localization Only = false** to run the existing one-camp hunt. Exactly one
generated camp and Max Camps 1 are enforced. Recovery remains capped at four
stages and camp retries at the configured bound; do not raise limits to get
past unsafe terrain. Use OK-WW's configured Start/Stop shortcut to cancel
(verify its binding; F9 is the repository default). Cancellation/exception
cleanup sends releases for owned movement, camera, and combat controls. An
input backend failure is logged as failure, not a successful clean exit.

## Diagnostics and live result record

Logs use the existing configured OK-WW log, normally `logs/ok-ww.log`, with
`[HUNT]` JSON event payloads. Position/confidence and distance/bearing updates
are throttled to once per two seconds per event/validity. State transitions,
navigation result, cleanup failure, stuck/recovery stage, combat start/end,
clear/retry/failed camp state, replan reason, and task exit are immediate.
`validation_profile` records source paths, resolution, scale, target ids,
camp anchor, and radii. No combat return alone marks a camp clear.

Fill this record only from observed live evidence:

| Item | Current result |
| --- | --- |
| Exact reference/profile/database files | surface-test-01 candidate reference + landmark CSV + local Kuro DB; no accepted live profile |
| Test A spread/tolerance and independent absolute error | Closed-dataset hybrid replay 10/10 accepted, 0/60 negative accepts; integer spread 0 px, SIFT subpixel spread 0.039421 px; no fresh live validation or surveyed absolute ground truth |
| Test B navigation/cancellation/recovery | Not run |
| Test C navigation/combat handoff/input release | Not run |
| True positive clear | Not observed |
| False clear | Not assessed |
| Failure to detect clear | Not assessed |
| Combat reacquisition after apparent clear | Not assessed |
| Post-combat localization and session result | Not observed |
| Clean exit without teleport | Not observed |

Stop after this one camp. Phase 4.5 is incomplete until the observed live chain
succeeds. Passing mocked tests, repeatability alone, and an unobserved empty
camp are not substitutes for that evidence.
