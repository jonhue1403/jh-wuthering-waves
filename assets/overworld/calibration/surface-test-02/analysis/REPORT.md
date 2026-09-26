# Phase 4.5B fresh capture: Test A failed; Test B not run

Captured 2026-09-06 at 12:14:42–12:14:47 Asia/Kuala_Lumpur using the existing
`python -m src.overworld.calibration_capture --profile surface-test-02` helper
and the repository `.venv`. The user confirmed safe stationary positioning.
No navigation, combat, teleport, motorcycle, or underground routing was run.

## Capture integrity

- Ten full 2560×1440 lossless PNGs; metadata reports completion and WGC for every frame.
- Host receipt intervals: 495.329–518.974 ms (requested 500 ms).
- All ten PNG file hashes differ; original resolution is preserved.
- First and last images show a changed world-camera view. The minimap candidate
  is stable, but this is not a fully camera-stationary capture sequence.
- `surface-test-01` remains a closed offline dataset and was not overwritten.
  Its stored reference is reused for this diagnostic comparison, never its old
  player position as live ground truth.

## Frozen matcher replay

`frozen_replay.json` contains every frame hash, full measured evidence, capture
metadata, exact policy, and source paths. Frames use the runtime `box_minimap`
crop at (48,38), size 248×247, and the existing circular mask with center hole.
Reference and mask hashes and dimensions match the original calibration.

**0/10 accepted. Every frame fails `gradient_score`.**

| Gate | Fresh measurements | Unchanged requirement |
| --- | --- | --- |
| Gradient score | 0.658472–0.666146 | >=0.700 |
| Distinct peak margin | 0.575127–0.584646 | >=0.34874535724520683 |
| Unique SIFT inliers | 17–20 | >=11 |
| SIFT maximum residual | 0.625114–1.055119 px | <=1.481737015915146 px |
| Gradient/SIFT disagreement | 0.768925–0.816256 px | <=1.481737015915146 px |
| Feature coverage | 0.151028–0.167837 | >=1/61256; non-collinear |

The rejected integer candidate is (503,284) reference pixels in all ten frames.
Independent SIFT pairwise spread is 0.053257 reference pixels. These are
diagnostic candidates, not accepted localization or a stationary-tolerance pass.
The candidate is inside the 961×541 reference, with full-template support.

The reference belongs to state 906 / empty floor. Current state and floor were
not independently verified; the quest tracker is not evidence of current area.
No fresh full-map image was captured, no new landmark transform was fitted, and
no live profile or absolute-position ground truth was installed.

## Diagnosis

The independent SIFT translations are approximately (378.68,161.22) pixels,
between integer search positions. To isolate sampling sensitivity, a diagnostic
only comparison samples the existing reference Sobel-gradient field at those
translations using `cv2.remap(..., INTER_LINEAR)` and computes normalized dot
product against minimap gradients over the unchanged mask. It does not search
for a favorable offset or change scale or rotation.

This produces scores 0.702668–0.711989, versus 0.658472–0.666146 at the frozen
integer search peaks. See `diagnostic_metrics.json`. The increase supports
subpixel sampling as a material contributor to rejection; it does not prove
that all appearance or geometry errors are resolved. A simple HSV yellow-pixel
check (H=20–40, S>=100, V>=180) found no arrow-colored pixels within the active
mask; this is only a diagnostic for that color range.

**Subpixel diagnostic scores do not override rejection.** Interpolation changes
the score distribution, and using SIFT to select the sample offset changes the
relationship between the two signals. The existing threshold and margin policy
have not been validated for that alternative. No runtime matcher changes or
acceptance-rule weakening were made.

Before another movement attempt: validate any proposed subpixel scoring change
offline with positive, held-out, wrong-location, and rotated controls; verify
the current map/layer and geometry with an unmoved full-map capture; then repeat
fresh Test A with character and camera stationary. Use a new capture label for
any repeat. A safe nearby waypoint and cancellation behavior remain untested.

## Test B record and verification

Test B was not run because Test A failed. There is no accepted starting
coordinate, intended waypoint, movement distance, observed movement progression,
arrival result, stuck-detector activity, live cancellation/cleanup result, or
accepted ending localization to report. No game controls were acquired by the
capture helper, which uses its no-input backend. This does not validate input
release during live movement. Test C and Phase 5 were not started.

Before capture, 94 tests passed: 90 focused tests including BaseCombatTask,
2 Map fixtures, 1 FarmEcho fixture, and 1 Echo fixture. Compile checks passed.
Fixture runs used offscreen Qt, temporary configuration, disabled game access,
and the configured OpenVINO backend where needed. Initial harness encoding and
OCR configuration errors were resolved in the invocation, without source edits.
After capture, 28 hybrid-matcher/capture tests passed. Fresh-frame hashes,
original dataset/reference hashes, and frozen-policy equality were verified;
`git diff --check` passed.

Production code, frozen thresholds, and HuntMobTask settings are unchanged:
Localization Only=true, Max Camps=1, Safe Test Mode=true, Surface Only=true,
Use Teleport=false, Use Motorcycle=false.
