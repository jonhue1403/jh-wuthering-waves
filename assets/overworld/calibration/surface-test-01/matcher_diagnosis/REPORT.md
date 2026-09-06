# Phase 4.5A — closed offline localization passes; no live validation

**Result: 10/10 saved positive frames accepted, 0/60 constructed negative controls accepted.** The candidate is supported by independently computed gradient and SIFT positions, geometric landmarks, and separation from wrong locations. This is not acceptance merely because a position was expected.

The user reports that an enemy subsequently knocked the character away. These files are a **closed dataset from the original position**. The current live position is unknown and was never queried. Test B remains unauthorized. No game movement, camera/mouse input, combat, teleporting, motorcycle, underground execution, or Phase 5 work was performed.

The original images, metadata, earlier failed Test A report, and candidate reference are unchanged. The old color matcher still rejects the dataset at 0.700. A reference-bound, opt-in gradient/SIFT method now exposes its measured evidence to PlayerLocator. No live profile or target mob/camp selection was fabricated or installed.

## 1. Root cause and artifacts

The current color path compares:

- Original 2560×1440 game capture → exact `box_minimap` crop `(48,38,248,247)`.
- The existing radius-123 circular mask centered at `(124,123)`, with a central rectangular hole drawn inclusively from `(96,95)` through `(152,151)`.
- A 248×247 unscaled minimap template against the whole 961×541 candidate reference, with no automatic rotation or zoom search.
- `TM_CCOEFF_NORMED` color correlation with the geometry-only binary mask. There is no HSV terrain/color mask, opacity correction, or POI removal in this path. Nonfinite correlation values are replaced with zero.
- The unchanged candidate reference is a uniform, linearly resampled full-map screenshot: original map pixels / **2.6657430025420137**. The map has no crop/rotation/offset applied during image derivation. PNG preserves the resulting samples, but downsampling necessarily loses detail; the native full-map file is preserved.

The matched terrain aligns, but appearance does not. The minimap contains a broad directional shading cone and edge translucency/vignetting absent or different in the full map. Its POIs remain HUD-sized, whereas the full-map POIs became smaller during geometric scale conversion. The center mask also leaves **5 yellow arrow pixels** visible in frame 001. The PNGs are three-channel images with presentation already composited; the original rendering alpha cannot be recovered from them.

At the fixed geometrically corroborated pose, frame 001's color score is **0.629698**. Subtracting broad low-frequency variation (Gaussian sigma 8, diagnostic only) raises it to **0.736928**. Signed Sobel-gradient correlation gives **0.728331**. Thus broad spatial appearance differences materially depress the color score; this is not explained by bad Kuro coordinate geometry. The precise individual contribution of cone, translucency, icon scale, and resampling is not separately identifiable here. Merely shrinking the mask is not uniformly beneficial: inner-three-quarter-radius color score is 0.658570, outer-quarter-radius score 0.735222. These alternative masks/high-pass settings were **not** adopted or used to tune acceptance.

Artifacts for frame 001:

- [Raw minimap](raw_minimap.png), [runtime mask](mask.png), [masked minimap](masked_minimap.png)
- [Corresponding reference crop](candidate_reference_crop.png), [masked absolute difference](masked_difference.png)
- [Color heatmap](color_heatmap.png), [gradient heatmap](gradient_heatmap.png)
- [Color top-five overlay](color_top5.png), [gradient top-five overlay](gradient_top5.png)
- `color_scores.npy` / `gradient_scores.npy` contain the unnormalized raw numeric score surfaces. Heatmap PNG colors are min/max-normalized visualizations, not numeric confidence.

Top five distinct peaks, frame 001, in reference-center pixels:

| Rank | Color candidate | Color score | Gradient candidate | Gradient score |
| --- | --- | ---: | --- | ---: |
| 1 | (479,270) | 0.629698 | (479,270) | 0.728331 |
| 2 | (799,124) | 0.297014 | (478,262) | 0.073620 |
| 3 | (478,278) | 0.295667 | (492,262) | 0.069418 |
| 4 | (480,262) | 0.294650 | (480,278) | 0.069374 |
| 5 | (807,124) | 0.286594 | (466,276) | 0.068185 |

Distinct-peak suppression uses the existing **8-reference-pixel arrival scale** to avoid calling adjacent samples of one peak different locations. This is not proof that localization is accurate to 8 pixels. For transparency, the unsuppressed immediate runner-up is also recorded: gradient **0.644356**, margin **0.083975**, at one pixel above the best translation. Distinct-peak gradient margin is **0.654711**; color margin is **0.332684**.

## 2. Geometry validation — preserved, not retuned

```text
reference_xy = full_map_xy / 2.6657430025420137
Kuro_xy = (-98320.1328209656, -526959.0328891921)
          + reference_xy * 133.55384704852096
```

Equivalent native full-map scale is **50.100045998870094 Kuro units/pixel**. Both x and y increase in the corresponding image-axis direction; there is no x/y swap or reflection. The prior unconstrained similarity rotation was **0.089764°**, with maximum north-up uniform-fit terrain residual **1.899605 original-map pixels**. We retain north-up translation matching; no runtime rotation or scale correction is added.

The two beacons fit the transform; the third fixed marker remains held out:

| Landmark / location ID | Kuro x,y | Original-map residual | Reference residual | Kuro residual |
| --- | --- | ---: | ---: | ---: |
| Northeast Beacon / 1451326173333368832 | 9962, -513189 | 0.235376 px | 0.088297 px | 11.7923 |
| South Beacon / 1451327183948935168 | -26192, -469086 | 0.235376 px | 0.088297 px | 11.7923 |
| West fixed settlement / 1451217545689624576 | -64962, -498537 | 1.344522 px | 0.504371 px | 67.3606 |

All three DB records have **state_id=906, floor_id=""**. This preserves the verified source layer, but the matcher does not infer the current game layer. Empty floor IDs are not independent proof of surface status. The user's original surface report and outdoor imagery supplement the source records. State 8 was not substituted based on its composite name.

## 3. Methods and negative controls

| Method | Saved positives accepted | Negative controls accepted |
| --- | ---: | ---: |
| A: existing masked color, threshold 0.700 | 0/10 | 0/60 |
| B: signed x/y Sobel gradients, normalized dot-product correlation ≥0.700 | 10/10 | 0/60 |
| C: SIFT + unique translation support and residual checks | 10/10 | 0/60 |
| D: gradient proposal + SIFT corroboration + calibrated gates | **10/10** | **0/60** |

SIFT uses OpenCV from the existing Python 3.13 venv, exact brute-force descriptor matching (the gallery is small), and the existing analysis's 0.7 nearest/second-nearest descriptor ratio. No PR code was copied; FLANN is unnecessary here. Duplicate keypoint orientations and shared reference keypoints are deduplicated. A deterministic maximal translation consensus is independently computed from descriptor correspondences; it is not initialized from the gradient location, expected position, or prior frame. Hull support must be non-collinear. Gradient correlation and SIFT provide different signals on the same imagery, **not statistically independent sensors**.

Calibration fitting used frames **001–005** and 25 negative controls. Frames **006–010** and 35 different controls were withheld from threshold selection. Training negatives rotate the query by 10°,45°,90°,180° or use a left-side reference gallery with the correct terrain absent. Withheld negatives use -10°,-45°,-90°,135°,±2°, or the disjoint right-side gallery. Wrong-gallery controls intentionally evaluate the underlying matcher in isolation; normal runtime reference-hash binding rejects a substituted gallery even earlier. Rotated queries test the unsupported non-north-up case, not a claim that the map should be rotation-invariant.

- Training negative maximum gradient score: **0.108696**; maximum unique SIFT inliers: **4**.
- Withheld negative maximum gradient score: **0.192688**; maximum unique SIFT inliers: **9**.
- Training/withheld negative maximum color scores: **0.350877 / 0.424177**.
- Every valid sliding-window translation outside the 8-pixel local cluster is also measured: **210,433 per frame**, **2,104,330 evaluations** total, with **zero scores ≥0.700**. These highly overlapping windows are not millions of independent validation samples.
- For frame 001, spatial-negative gradient median/p95/p99/max: **0.000496 / 0.014235 / 0.022547 / 0.073620**.
- Deliberate fixed-pose offsets ±1,±2,±4,±8,±16,±32 in each axis are recorded separately. Even the best one-pixel neighbor scores below 0.700.

The controls cover nearby wrong translations, distant same-reference terrain, absent-terrain galleries, and unsupported rotations. They do **not** establish performance in another world region, at another heading/zoom, after map-content changes, or during movement/aggro.

## 4. Frozen acceptance rule

All conditions must hold:

1. Exact reference-pixel hash, minimap dimensions, and mask hash match the offline calibration. Runtime profile state/floor match the calibration, and the resulting coordinate is inside the profile image bounds.
2. Signed-gradient score **≥0.700**. The numeric cutoff was not lowered; gradient score is a different measured quantity from color score, not a remapped or fabricated confidence.
3. Best minus next distinct gradient score **≥0.3487453572**. This is the midpoint between training positive minimum margin **0.6544008106** and training negative maximum margin **0.0430899039**.
4. At least **11 unique SIFT translation inliers**. This is the rounded-up midpoint between training positive minimum **17** and negative maximum **4**. Repeated orientations cannot inflate support.
5. Non-collinear spatial support: inlier convex hull covers at least one reference-template pixel of area. This is a structural degeneracy check, not a learned confidence threshold; observed positive hull coverage is roughly 35–39% of the template.
6. SIFT maximum translation residual **≤1.4817370159 reference pixels**, and gradient/SIFT position disagreement **≤1.4817370159 reference pixels**. The bound was fixed from the earlier withheld terrain residual: `2.0649651278 / 2.6657430025 + sqrt(2)/2` (measured mapping error plus integer-grid half-diagonal). It is not a guarantee of absolute world-coordinate accuracy or a motion safety radius.

The policy was frozen before evaluating held-out frames/controls. Its JSON records the provenance and scope. The original `SurfaceProfile.match_threshold` is still enforced by PlayerLocator as well. No minimum threshold was trained using positives alone.

## 5. All ten final positions and evidence

Source for every row: **gradient_sift**, confidence = raw signed-gradient correlation. SIFT support/residual and cross-method disagreement are separately exposed via `LocalizationEvidence` and diagnostic logs. Confidence is not a probability. Layer for every row is **906 / empty floor**, inherited from the calibrated source profile, not live-detected.

| Frame | Accepted | Kuro x | Kuro y | Gradient score | Second distinct | Margin | SIFT inliers | SIFT residual px | Signal disagreement px |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 001 | Yes | -34347.84 | -490899.49 | 0.728331 | 0.073620 | 0.654711 | 18 | 0.577 | 0.740 |
| 002 | Yes | -34347.84 | -490899.49 | 0.728321 | 0.073540 | 0.654781 | 19 | 0.580 | 0.742 |
| 003 | Yes | -34347.84 | -490899.49 | 0.728228 | 0.073828 | 0.654401 | 17 | 0.561 | 0.743 |
| 004 | Yes | -34347.84 | -490899.49 | 0.728280 | 0.073514 | 0.654765 | 19 | 0.709 | 0.737 |
| 005 | Yes | -34347.84 | -490899.49 | 0.728409 | 0.073637 | 0.654772 | 18 | 0.928 | 0.745 |
| 006 | Yes | -34347.84 | -490899.49 | 0.728169 | 0.073941 | 0.654228 | 19 | 0.569 | 0.732 |
| 007 | Yes | -34347.84 | -490899.49 | 0.728596 | 0.073779 | 0.654817 | 17 | 0.539 | 0.765 |
| 008 | Yes | -34347.84 | -490899.49 | 0.728319 | 0.073818 | 0.654501 | 18 | 0.531 | 0.753 |
| 009 | Yes | -34347.84 | -490899.49 | 0.728325 | 0.073660 | 0.654665 | 17 | 0.540 | 0.748 |
| 010 | Yes | -34347.84 | -490899.49 | 0.728345 | 0.073541 | 0.654804 | 20 | 0.629 | 0.727 |

Final integer reference position is `(479,270)` in every frame: pairwise spread **0 px**, sample x/y variance **0**. Independently estimated SIFT positions have maximum pairwise spread **0.039421 reference pixels**, about **5.265 Kuro units**. This exposes subpixel variation hidden by integer template peaks rather than asserting zero measurement error.

The full-map-derived yellow-arrow centroid remains **1.790253 reference pixels** away, approximately **239.10 Kuro units**. Its anchor is unverified; do not interpret that as surveyed absolute error. The measured geometric residual cap above and observed stationary spread serve different purposes. No arbitrary live stationary tolerance was installed. The ten observations are temporally correlated and the original scale calibration used frame 001. These limitations remain even with perfect control rejection.

## 6. Implementation, tests, and runtime boundary

Changed/added code:

- `src/overworld/navigation/image_matcher.py`: pure image-only gradient/SIFT matcher and reference-bound calibration policy.
- `src/overworld/navigation/player_locator.py`: optional calibration-path metadata, evidence dataclass, accepted/rejected evidence reporting; original tuple matching and threshold/bounds checks preserved.
- `src/task/HuntMobTask.py`: optional capture-only adapter; hybrid calibration is rejected **before startup** unless Localization Only is true, and rejected on layer/reference mismatch. Legacy matcher remains the default. No combat or navigation routines changed.
- `scripts/diagnose_surface_matcher.py`: reproducible offline controls, calibration, geometry check, artifacts, and replay.
- `tests/TestHybridMapMatcher.py`: 15 tests, including frozen real-dataset replay (skipped if private files are unavailable), unique-feature support, duplicate terrain, rotations, wrong gallery, blank/nonfinite input, invalid policies, hash/mask/size binding, layer binding, evidence preservation, threshold/bounds checks, no-input adapter, and prevention of hybrid movement startup.
- Live-validation guide updated to distinguish this closed-dataset pass from a live Test A pass. Earlier failed evidence remains intact.

**93 tests passed:** 88 focused tests (including 15 new), 2 existing `tests.TestMap`, 1 `tests.TestEcho`, and 2 `tests.TestBaseCombatTask`. The existing image-fixture tests were run with Windows/ADB/browser access disabled, offscreen Qt, and temporary configuration storage. Compile checks and source-hash verification passed. Initial test-harness-only encoding/OCR-configuration issues were corrected in the invocation, not application code. Python 3.13 dependencies worked; no dependency workaround was added.

`configs/HuntMobTask.json` remains unconfigured and unchanged: Localization Only=true, Max Camps=1, Safe Test Mode=true, Surface Only=true, teleport=false, motorcycle=false. A calibrated live hunt profile was not installed. The new optional `matcher_calibration` profile path is not automatically populated, and this calibration is limited to Localization Only even if explicitly selected.

Reproduce **offline only** from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/diagnose_surface_matcher.py
```

See `results.json` for every control, score distribution, top-five candidate, geometry residual, source hash, and per-frame estimate; `matcher_calibration.json` for the frozen rule. The current character position is irrelevant to this command.

**Conclusion:** the saved dataset now passes the requested offline stability-and-discrimination test. This is not a generalized or fresh-live localization certification. Since the character was displaced, fresh live validation requires a new, safely positioned capture set outside enemy aggro and review. **STOP: no Test B, movement, combat, or Phase 5.**
