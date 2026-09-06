# Surface-test-01: offline Test A — FAIL

No movement, combat, teleporting, camera input, live task startup, or Phase 5 work was performed.
The existing PlayerLocator accepted **0/10** positions. Test B is not justified.

## Inputs and reference provenance

- Ten unchanged 2560×1440 WGC frames and their metadata; the user confirms stationary surface positioning.
- `full_map_position.png`, also 2560×1440, shows **Startorch Academy** and the same player position.
- Read-only `../../../../../../wuwa-map/map_items.db` supplies the landmark coordinates.
- The adjacent repository has **no local tiles, stitched maps, or map-coordinate sidecars**. Its four `qzx_*.png` assets are chest icons, not terrain. `map_parse.py` can download/stitch tiles, but was not run. Its hard-coded 83.008 scale was not assumed to calibrate these screenshots.
- `reference_candidate.png` is derived from the supplied full-map screenshot, not from a Kuro tile. All originals remain unchanged. This is a diagnostic candidate, **not an accepted live hunt reference**.

The native full-map screenshot has a different zoom from the minimap: matching it unchanged gives only 0.296877 confidence on frame 001. An analysis-only SIFT correspondence measurement on the native images found 22 unique pairs, including 20 geometric inliers. The central player-arrow region was excluded by the existing runtime mask. A north-up uniform-scale fit measures **2.665743002542 full-map pixels per minimap pixel**. An unconstrained similarity fit reports only 0.089764° rotation; no rotation was applied. The uniform fit's maximum terrain residual is 1.899605 full-map pixels. Seven spatially interleaved withheld correspondences have maximum residual 2.064965 full-map pixels; their inlier selection shares the full correspondence pool, so this is diagnostic cross-checking, not wholly independent validation.

The candidate is generated once at 961×541 using `warpAffine`, uniform scale `1/2.665743002542`, zero translation and `INTER_LINEAR`. There is no crop, score-driven scale search, per-frame registration, masking of the reference, or threshold reduction. Scale comes from terrain geometry, not optimization of the runtime match score. Sampling/downscaling can still affect appearance and remains part of the failure diagnosis.

Two beacon correspondences independently provide:

```text
Kuro x = -98320.1328209656 + full_map_pixel_x * 50.1000459988701
Kuro y = -526959.0328891921 + full_map_pixel_y * 50.1000459988701

Kuro x = -98320.1328209656 + reference_pixel_x * 133.553847048521
Kuro y = -526959.0328891921 + reference_pixel_y * 133.553847048521
```

These are measured candidate transforms, not exact surveyed coordinates; displayed digits preserve reproducibility, not accuracy. Pixel correspondences, segmentation ROIs, algorithm parameters, source hashes, and all intermediate measurements are in `test_a_results.json`. No runnable SurfaceProfile JSON, target mob, camp, or acceptance threshold was invented.

## Three coordinate landmarks

| Landmark | Source location ID | Item ID | Kuro x | Kuro y | state_id | floor_id | Use |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| Northeast Resonance Beacon | 1451326173333368832 | CS_02 | 9962 | -513189 | 906 | `""` | Fit |
| South Resonance Beacon | 1451327183948935168 | CS_02 | -26192 | -469086 | 906 | `""` | Fit |
| West fixed Tacet Discord settlement marker | 1451217545689624576 | 7010 | -64962 | -498537 | 906 | `""` | Held-out check |

The third is a fixed map marker, not an individual roaming mob. No Resonance Nexus is identifiable in this screenshot, so one was not guessed. The beacons' DB descriptions name `罗伊冰原-蚀刻平原`; item 7010 is `陷足流川残象聚落`. The screenshot's displayed area label and these POI descriptions need not be identical at area boundaries.

Icon centers are measured from HSV connected-component bounding boxes at native resolution: NE `(2161.5,275)`, south `(1439.5,1155)`, west `(664.5,567.5)`. Beacon fit residuals are 0.235376 pixels each. The independent west-marker residual is **1.344522 full-map pixels**, or approximately **0.5044 reference pixels**. Among same-layer state-906 beacon-pair assignments checked against that fixed marker, this pair has maximum residual 1.3445 pixels; the next assignment is 490.0732 pixels away. This strongly supports the coordinate correspondence, though it is not an exhaustive cross-state map detector.

**Layer evidence:** `state_id=906` is supported by the three landmark correspondences, not guessed from the composite state-8 name. All three source records have empty `floor_id`. This verifies the DB layer label only: blank is not proof of surface, and PlayerLocator does not detect floors. The surface claim rests on the user's report plus the outdoor screenshot. No underground layer ID was substituted.

## Ten-frame replay

Replay uses OK-Script's actual `box_minimap` `(48,38,248,247)`, `create_circle_mask_with_hole`, `FeatureSet.find_one_feature` with `TM_CCOEFF_NORMED`, and PlayerLocator. The unchanged threshold is **0.700**. No game-dependent task is instantiated. A geometry-only dataclass carries the measured conversion; it does not claim to satisfy live hunt setup requirements.

Every row below is a **rejected diagnostic candidate**, not a valid PlayerLocator position. Source for every score is the existing masked color template matcher; confidence is a correlation score, not a probability. Every runtime position returned `None`.

| Frame | Candidate Kuro x | Candidate Kuro y | Confidence | Runtime result |
| --- | ---: | ---: | ---: | --- |
| 001 | -34347.84 | -490899.49 | 0.629698 | Rejected |
| 002 | -34347.84 | -490899.49 | 0.629088 | Rejected |
| 003 | -34347.84 | -490899.49 | 0.628376 | Rejected |
| 004 | -34347.84 | -490899.49 | 0.627412 | Rejected |
| 005 | -34347.84 | -490899.49 | 0.626512 | Rejected |
| 006 | -34347.84 | -490899.49 | 0.625356 | Rejected |
| 007 | -34347.84 | -490899.49 | 0.625036 | Rejected |
| 008 | -34347.84 | -490899.49 | 0.624617 | Rejected |
| 009 | -34347.84 | -490899.49 | 0.624978 | Rejected |
| 010 | -34347.84 | -490899.49 | 0.624550 | Rejected |

All candidates round to reference pixel `(479,270)` under runtime `Box.center()` semantics. Observed maximum pairwise spread and radial noise envelope are **0 pixels / 0 Kuro units**; sample x/y variance is numerically zero (floating-point y residue approximately 1.5e-20). This is integer-pixel repeatability over about 4.5 seconds, with shared reference calibration—not a claim of zero localization error. Frame 001 also contributed to scale calibration, so this is not ten independent validation samples.

## Position comparison and tolerance

The full-map yellow arrow's independently segmented centroid is `(1281.59395,720.56095)`, approximately Kuro `(-34112.22,-490858.90)` under the beacon transform. It is **1.7903 reference pixels** from the mean candidate. This is a weak, independently visible position cross-check: the arrow centroid is not a verified position anchor. It cannot establish absolute ground-truth accuracy. The visible HUD coordinate text was not converted with a guessed multiplier.

**Observed candidate noise envelope: 0 reference pixels. Accepted localization tolerance: undetermined.** With no accepted estimates, neither zero observed jitter nor the centroid discrepancy can honestly be installed as a safe acceptance tolerance. No arbitrary tolerance is chosen, and the task's existing positive-tolerance validation is not bypassed.

## Failure diagnosis and boundary

The initial incompatibility was a measured map/minimap zoom difference. Geometric conversion solves that mismatch and places the best candidate near the independent arrow, but does **not** make the current appearance matcher sufficiently confident. The minimap and big map differ in presentation, including the minimap's visible directional shading and overlays; resampling is another possible contributor. The current circle/center-hole mask does not exclude every such region. Their individual contributions are not established here. Grayscale matching was checked as an analysis-only diagnostic and scored only 0.592403 on frame 001, so merely removing color does not resolve this sample.

Do not lower the threshold to 0.62 or treat repeatability as a pass. The next work, if requested, remains calibration/localization diagnosis (reference appearance and mask/metric suitability), not navigation. No additional in-game action is currently needed to identify this area. **Test B remains blocked.**

Reproduce from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/analyze_surface_test_a.py
```

The script writes only its analysis outputs and opens the source database read-only. Compile checks and 14 existing PlayerLocator/diagnostics tests passed. Neither live Test A nor Test B/C was started.
