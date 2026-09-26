# Phase 4.5B: offline subpixel matcher validation

2026-09-06. **Offline validation passes; fresh Test A is still pending.**
No game capture, movement, combat, Test B, or live profile installation was
performed during this work. The existing surface-test-02 rejection record is
preserved as the frozen integer baseline.

## Method and policy

The SIFT translation is estimated using the existing descriptor matching and
translation consensus, independently of the gradient result. Its fractional
part specifies ONE sampling phase for the entire reference Sobel-gradient
field. Bilinear interpolation uses OpenCV's 1/32-pixel table; returned positions
use that actual grid. There is no fractional score maximization, angle search,
scale search, expected-position prior, or per-candidate choice of phase.

The gradient search compares every integer translation on this one shifted
grid. Both the best candidate and the spatially distinct runner-up therefore
use the same sampling method. Templates requiring pixels beyond the reference
are excluded rather than padded. Missing/nonfinite SIFT phase fails closed.

The agreement gate is the larger of (a) the ORIGINAL integer-gradient/SIFT
disagreement and (b) refined-gradient/SIFT disagreement. The original independent
coarse check cannot be erased by adopting SIFT's sampling phase. The refined
agreement alone is partially coupled to SIFT and is not independent corroboration.

Interpolation materially changes scores. The acceptance policy was revalidated
jointly, not transferred on the assumption that integer and interpolated scores
are interchangeable:

| Gate | New policy | Basis |
| --- | --- | --- |
| Gradient score | >=0.700 | Unchanged mandatory floor, checked against both datasets and all controls |
| Distinct radius | 8 reference pixels | Existing definition of a distinct location |
| Best/second-best margin | >=0.3634031228721142 | Original frames 001–005 positive minimum 0.6774536297 and fitting-negative maximum 0.0493526161; midpoint, bounded below by old margin 0.3487453572 |
| Unique SIFT inliers | >=11 | Unchanged |
| Feature hull coverage | >=1/61256 | Unchanged non-collinearity requirement |
| SIFT maximum residual | <=1.481737015915146 px | Unchanged prior geometry bound |
| Agreement, including integer check | <=1.481737015915146 px | Unchanged bound |

The margin was fitted only on the original fitting partition; original withheld
frames/angles and all surface-test-02 data validate it without adjusting it.
The combined results support retaining 0.700 with these joint gates for this
reference. They do not support a score-only classifier: exact duplicate terrain
has positive-like scores and must fail ambiguity checks.

## Acceptance and score distributions

All rates count frames/control queries, not independent field trials. The ten
frames within each pose are correlated. Original withheld frames 006–010 were
withheld from fitting this margin, but had already been examined in prior work.
Surface-test-02 motivated the method and is not an untouched prospective test.

| Positive partition | Integer accepts | Subpixel accepts | Integer score range | Subpixel min / median / max |
| --- | --- | --- | --- | --- |
| surface-test-01 001–005, fitting | 5/5 | 5/5 | 0.728228–0.728409 | 0.753791 / 0.754440 / 0.754792 |
| surface-test-01 006–010, withheld | 5/5 | 5/5 | 0.728169–0.728596 | 0.753852 / 0.754859 / 0.755110 |
| surface-test-02 001–010, fresh replay | 0/10 | 10/10 | 0.658472–0.666146 | 0.702668 / 0.709818 / 0.711989 |
| Combined | 10/20 (50%) | **20/20 (100%)** | 0.658472–0.728596 | 0.702668 / 0.732890 / 0.755110 |

| Positive partition | Second-best range | Margin range | SIFT inliers | Maximum residual range, px | Retained agreement range, px |
| --- | --- | --- | --- | --- | --- |
| Original fitting | 0.075655–0.076986 | 0.677454–0.678862 | 17–19 | 0.560931–0.927816 | 0.736869–0.744826 |
| Original withheld | 0.075506–0.076429 | 0.678021–0.678945 | 17–20 | 0.531244–0.628628 | 0.726885–0.765242 |
| Fresh replay | 0.079300–0.083703 | 0.618964–0.632006 | 17–20 | 0.625114–1.055119 | 0.768925–0.816256 |

SIFT evidence and residuals are unchanged. Its pairwise spread is 0.039421 px
over surface-test-01 and 0.053257 px over surface-test-02. The actual 1/32-pixel
gradient output grid has spread 0.044194 px and 0.069877 px respectively. These
are offline spreads, not an absolute-error or stationary-tolerance certification.
The minimum fresh score clears 0.700 by only 0.002668; no threshold was reduced.

## Negative controls and false-positive behavior

All 60 original controls are reproduced: original fitting rotations
10/45/90/180 degrees with the left absent-terrain gallery, and withheld rotations
-10/-45/-90/135/+2/-2 degrees with the right gallery. Fresh controls add
rotations +/-2, +/-10, 45, 90, 180 degrees and two absent-terrain galleries.
Both datasets also supply blank and duplicate-terrain controls.

| Control type | Queries | Finite subpixel scores | Subpixel score min / median / max | Maximum subpixel margin | Accepts |
| --- | --- | --- | --- | --- | --- |
| Rotated | 120 | 120 | 0.049243 / 0.079322 / 0.236356 | 0.109480 | 0 |
| Absent terrain | 30 | 3 | 0.034433 / 0.034475 / 0.034848 | 0.002717 | 0 |
| Blank | 20 | 0 | No SIFT phase; no score | None | 0 |
| Exact duplicate terrain | 20 | 0 | Descriptor ties; no SIFT phase | None | 0 |
| Duplicate + strong SIFT injection | 20 | 20 | 0.702668 / 0.732890 / 0.755110 | 0 | 0 |
| **Combined** | **210** | **143** | Missing values are not zeros | | **0/210 (0%)** |

The injected duplicate controls deliberately supply the real positive's SIFT
evidence at one identical copy. They are adversarial fault-injection tests,
not naturally obtained independent feature results. All have sufficient
feature support and strong gradient scores; all reject on zero margin.

Integer hybrid false accepts were also 0/210. Thus **no observed increase in
false-positive acceptance**, although raw negative scores do change: rotated
maximum increases from 0.216404 to 0.236356, and injected duplicate scores cross
0.700 for all fresh frames. Some fresh rotated controls have up to 15 SIFT
inliers; SIFT support alone is insufficient. Across finite negative evidence,
residuals span 0–1.497393 px and agreement spans approximately 0.290–373.591 px;
some negatives pass individual geometry gates. Rejection depends on the joint
policy, not requiring every individual gate to fail.

For every positive query, all locations outside the 8-pixel coarse peak basin
are also checked: 4,208,660 integer and 4,188,419 shifted-grid samples. Maximum
scores are 0.083345 and 0.083703, respectively; **zero reach 0.700**. These
overlapping locations are not counted as millions of independent negative trials.

All original axial offset probes (+/-1,2,4,8,16,32 px) are reproduced and extended
to every positive frame: 480 diagnostic probes. They use an actual distinct
competitor outside each probe's own radius when measuring margin. An adjacent
probe can coincide with the true refined peak, so nearby probes are not labeled
false locations. Distinct wrong-location probes (more than 8 px from SIFT) all
reject. Per-probe score, margin, agreement, and classification are in results.json.

## Integration and verification

The evidence justifies an explicit, reference-bound localization-only opt-in:
`sampling_mode: "sift_phase"` in matcher calibration. Old calibrations default
to `integer`; the legacy color matcher is untouched. The original calibration
file is not overwritten. The new calibration is saved alongside this report,
but no live Hunt Profile or task setting is populated.

HuntMobTask's existing hybrid movement-startup prohibition is unchanged.
Localization Only=true, Safe Test Mode=true, Surface Only=true, Max Camps=1,
Use Teleport=false, Use Motorcycle=false remain unchanged.

The regression suite covers fractional synthetic localization, direct normalized
dot-product agreement at correct/wrong/boundary samples, wrong SIFT translations,
missing/nonfinite phase, strong duplicate ambiguity, calibration compatibility,
and full runtime replay of both datasets and every control. Existing hybrid,
capture-only, locator, and HuntMobTask tests cover hash/mask/layer binding,
threshold/bounds checks, legacy replay, and the prohibition on hybrid movement.

Reproduce from the repository with:

```powershell
.\.venv\Scripts\python.exe scripts/validate_subpixel_gradient.py
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest tests.TestSubpixelMapMatcher tests.TestHybridMapMatcher tests.TestCalibrationCapture tests.TestHuntPlayerLocator tests.TestHuntMobTask
```

`results.json` records hashes checked against the original/fresh manifests,
reference hash, matcher/evaluator source hashes, OpenCV version, full per-query
integer/subpixel evidence, and distributions including min/median/p95/p99/max.
Wrong galleries intentionally rebind image hashes to test matching itself;
normal runtime reference binding would reject an unapproved substitute earlier.

## Next step and limits

Follow [surface-test-03 capture instructions](../../../../../../docs/overworld-hunt-surface-test-03.md).
The current layer, surface status, and full-map geometry must be established
from fresh evidence at the unmoved character position. The old state 906 / empty
floor values describe the stored reference only. No generalization to other
regions, scales, headings, changing map content, movement, or aggro is established.
**Stop after offline validation and capture instructions. Test B is not run.**
