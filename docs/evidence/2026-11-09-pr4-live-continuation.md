# PR 4 live continuation, 9 November 2026

Timezone: Asia/Kuala_Lumpur. Candidate source checkpoint: `04b27a64` plus
the offline registration correction described below. Overall qualification
remains **LIVE_VERIFICATION_PENDING**. No merge or release.

## Story Watch deferred by user

The selected Shades of Battle quest opened **Tactical Hologram: Sparring**, a
separate combat activity. The user requested deferring Story Watch in favor of
the single-camp work. Its dialogue observations are partial evidence, not a
complete supported story travel/dialogue/combat segment.

Registered Story Watch native playback run `7fc6505c0c8b4a1f992a493443468c21`
advanced Ceshi's dialogue and stopped at the first branching choice. The user
approved “Go on.”, the following informational question, and “Sure.” individually,
then authorized automatically selecting sole responses. Branching choices and
resource decisions remain outside that sole-response authorization. The observed
world objective subsequently changed to Enter the Battle Shade Shroud.

Two earlier clicks on a misidentified top-left icon had no observed effect; they
are not evidence about native autoplay. The correctly recognized native playback
feature was at the top right. Full voice/cutscene continuity was not established.

An authorized combat-helper attempt `0b6800b3602f44e681b4fa79deac583a`
recognized Changli, Aemeath and Shorekeeper and issued rotations, then stopped on
the fresh-frame guard. The subsequent screen showed Challenge Failed. The thin
harness had not installed the registered task as `executor.current_task`, which
controls periodic capture during sleeps; source review supports that harness
gap, without proving it was the only cause. No freshness limits were weakened.
The corrected-context retry `c52b86ba1f9a400c80a92e4fa415766d` failed the combat
precondition during arena loading. Neither attempt qualifies combat clear.

Recovery `1dad7e0a9ba84655a18c0907813864b0` stopped at the Leave the Sparring
Ground confirmation. Run `602506ef08c444dfa12825ae8b6a5768` confirmed leaving;
fresh observation `8c98d0b2e7e84585ac8dec22da66ee98` verified the open world.
No purchases or resource claims were made.

## Academy preparation and localization

The map menu visibly lists Startorch Academy under Roya Frostlands / Lahai-Roi.
Xuanfang Hold is a **different region**; the earlier inferred rename was wrong.
Do not interpret the previous Xuanfang localization rejection as a same-area
reference replay. Its recorded rejection remains genuine for that location.

Native map selection `f474ca443bba41daa3dbd0870cb03046` selected the southwest
academy Resonance Beacon. Terra medium independently confirmed the beacon's
historical road/interchange relationship. Native travel
`03ed8ffde6344bfe836b901e59f91e57` showed Startorch Academy loading; fresh
observation `470880950d144f08a2ae5d7c33497ba8` verified surface-world arrival.
This supervised preparation does not qualify automated beacon travel.

The historical profile still rejected stationary sample 1 in
`24a8283ce7fa47b8a1bad94c3d44f6fe`. A fresh reference replay passed offline but
the live task also rejected it in `b59062c359bd4e669ef4d09141a7253a`.
Read-only probe `5ebcd9854d024b388fab6cdf1df23610` established the cause:
the active split-template box is `(48, 38, 249, 247)`, while the offline script
hardcoded a 248-pixel-wide crop. Mask hashes and policy sizes therefore differed.

`scripts/register_surface_capture.py` now derives crops with the runtime's
FeatureSet and split asset, binds the policy to the measured dimensions, rejects
mixed crop geometry, sizes rotation controls accordingly, and removes stale
sidecars/reports before a new replay. It does not resize live inputs or relax
score, margin, feature-support or geometry thresholds. Two focused tests cover
the actual rounding regression and mixed-resolution rejection. Terra medium
found no blocking source defect and recommended clearing stale reports, which
was applied.

Fresh 249-pixel replay accepted 10/10 correlated stationary captures and rejected
90/90 generated negatives. Registered Hunt **localization-only** run
`4d5fcc1571c648de881621c4d861185d` then succeeded on ten new live samples:
confidence 0.76817–0.76935 and maximum pairwise spread **0.04419 pixels** against
the unchanged 1-pixel tolerance. See
[numerical live result](2026-11-09-pr4-academy-localization.json).

This establishes one stationary pose, not independent absolute position error,
route traversal, target presence, combat clear, or inventory acquisition. The
fresh profile remains local under `logs/live-pr4/calibration-academy-20261109`,
with localization/navigation execution flags false. No movement qualification
or runtime version approval was fabricated. Raw screenshots contain account
identifiers and remain local.

## Remaining gates

Story Watch is deferred, not passed. Single-camp work still needs distributed
independent world/pose validation, installed-game-version qualification, the
reviewed bounded walk and actual combat/clear loop. Route execution, resource
profiles and explicit spending budgets remain unconfigured. Spending stays off;
the final world-state check persists PAUSED with story lock true and resource
profile `{}`. Sole-option dialogue authorization does not enable Skip Dialog.

Verification: 17 focused tests passed across the registration and hybrid matcher
modules; strict MkDocs build and `git diff --check` passed. The previous 799-test
source checkpoint is recorded separately and was not rerun for this offline-only
script correction. Final pause run: `6de422ca5f30472bab881fbd5ba38c2f`.
