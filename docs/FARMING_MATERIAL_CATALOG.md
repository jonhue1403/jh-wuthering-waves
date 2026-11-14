# Material-first Farming Assistant — catalog inventory and Codex qualification

## Screenshot inventory

The 27 names below were transcribed **as displayed** in the operator-supplied
nine-row, three-column material screenshot (14 November 2026). They are
searchable/display-only targets, not validated numerical item IDs, drop tables,
recipes, domains, camps, routes or direct game-controlled farming jobs.

| # | Material name | Stable UI ID | Acquisition evidence | Automated farming |
| ---: | --- | --- | --- | --- |
| 1 | Premium Tuner | `premium-tuner` | [Tacet Field / synthesis](https://wutheringwaves.fandom.com/wiki/Premium_Tuner) — reference-only | **NOT QUALIFIED** |
| 2 | Premium Sealed Tube | `premium-sealed-tube` | [Tacet Field / exploration](https://wutheringwaves.fandom.com/wiki/Premium_Sealed_Tube) — reference-only | **NOT QUALIFIED** |
| 3 | Premium Resonance Potion | `premium-resonance-potion` | [Simulation / quest rewards](https://wutheringwaves.fandom.com/wiki/Premium_Resonance_Potion) — reference-only | **NOT QUALIFIED** |
| 4 | Heterized Metallic Drip | `heterized-metallic-drip` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Heterized_Metallic_Drip) — reference-only | **NOT QUALIFIED** |
| 5 | Mysterious Code | `mysterious-code` | [Casket Delivery / quests (non-mob)](https://wutheringwaves.fandom.com/wiki/Mysterious_Code) — reference-only | **NOT QUALIFIED** |
| 6 | FF Whisperin Core | `ff-whisperin-core` | [Whisperin enemies / synthesis](https://wutheringwaves.fandom.com/wiki/FF_Whisperin_Core) — reference-only | **NOT QUALIFIED** |
| 7 | FF Howler Core | `ff-howler-core` | [Howler enemies / synthesis](https://wutheringwaves.fandom.com/wiki/FF_Howler_Core) — reference-only | **NOT QUALIFIED** |
| 8 | Tailored Ring | `tailored-ring` | [Exile enemies / synthesis](https://wutheringwaves.fandom.com/wiki/Tailored_Ring) — reference-only | **NOT QUALIFIED** |
| 9 | Mask of Insanity | `mask-of-insanity` | [Fractsidus enemies / synthesis](https://wutheringwaves.fandom.com/wiki/Mask_of_Insanity) — reference-only | **NOT QUALIFIED** |
| 10 | Flawless Phlogiston | `flawless-phlogiston` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Flawless_Phlogiston) — reference-only | **NOT QUALIFIED** |
| 11 | Presto Helix | `presto-helix` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Presto_Helix) — reference-only | **NOT QUALIFIED** |
| 12 | Waveworn Residue 239 | `waveworn-residue-239` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Waveworn_Residue_239) — reference-only | **NOT QUALIFIED** |
| 13 | Cadence Blossom | `cadence-blossom` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Cadence_Blossom) — reference-only | **NOT QUALIFIED** |
| 14 | Premium Energy Core | `premium-energy-core` | [Simulation / quest rewards](https://wutheringwaves.fandom.com/wiki/Premium_Energy_Core) — reference-only | **NOT QUALIFIED** |
| 15 | FF Tidal Residuum | `ff-tidal-residuum` | [Dark Tide enemies / synthesis / Forgery](https://wutheringwaves.fandom.com/wiki/FF_Tidal_Residuum) — reference-only | **NOT QUALIFIED** |
| 16 | FF Polygon Core | `ff-polygon-core` | [Clamoring/Tranquilite enemies / synthesis](https://wutheringwaves.fandom.com/wiki/FF_Polygon_Core) — reference-only | **NOT QUALIFIED** |
| 17 | Echo Modifier | `echo-modifier` | [Events/exchange (item name needs confirmation)](https://wutheringwaves.fandom.com/wiki/Modifier) — reference-only | **NOT QUALIFIED** |
| 18 | FF Exoswarm Core | `ff-exoswarm-core` | [Exoswarm enemies / synthesis](https://wutheringwaves.fandom.com/wiki/FF_Exoswarm_Core) — reference-only | **NOT QUALIFIED** |
| 19 | Reverb Combustor | `reverb-combustor` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Reverb_Combustor) — reference-only | **NOT QUALIFIED** |
| 20 | FF Mech Core | `ff-mech-core` | [Clamorling enemies / synthesis / Forgery](https://wutheringwaves.fandom.com/wiki/FF_Mech_Core) — reference-only | **NOT QUALIFIED** |
| 21 | Intact Exoswarm Pendant | `intact-exoswarm-pendant` | [Roya Outcast enemies / synthesis](https://wutheringwaves.fandom.com/wiki/Intact_Exoswarm_Pendant) — reference-only | **NOT QUALIFIED** |
| 22 | Layered Wing Polarizer | `layered-wing-polarizer` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Layered_Wing_Polarizer) — reference-only | **NOT QUALIFIED** |
| 23 | Melodic String | `melodic-string` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/Melodic_String) — reference-only | **NOT QUALIFIED** |
| 24 | FF Carved Crystal | `ff-carved-crystal` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/FF_Carved_Crystal) — reference-only | **NOT QUALIFIED** |
| 25 | FF Waveworn Shard | `ff-waveworn-shard` | [Forgery / synthesis](https://wutheringwaves.fandom.com/wiki/FF_Waveworn_Shard) — reference-only | **NOT QUALIFIED** |
| 26 | Transducer | `transducer` | [Historical subscription (not assumed currently available)](https://senseos.gg/guides/wuthering-waves/wuthering-waves-echoes/) — reference-only | **NOT QUALIFIED** |
| 27 | FF Autopuppet Kernel | `ff-autopuppet-kernel` | [Autopuppet enemies / synthesis](https://wuthering.th.gl/db/inventory/item_41100094) — reference-only | **NOT QUALIFIED** |

FF Mech Core retains the five existing **community-documented possible enemy
sources**: Geospider S4, Sabercat Reaver, Spacetrek Explorer, Twin Nova:
Collapsar Blade and Twin Nova: Nebulous Cannon. Those are informational only;
neither numeric game IDs nor verified loot receipts/eligible routes are present.

The catalogue now includes **reference-only acquisition categories and URLs
for all 27 materials** under `src/automation/farming_acquisition_reference.py`.
These are community/guide statements, not qualified game sources. Actual item
identities, eligibility, live drops, route geometry and any resource cost remain
unknown. Only FF Mech Core's existing five possible named enemies are
documented as catalog mob entries; the other materials have no verified
mob-to-route relationships. Never assume all 27 can be farmed by combat,
or that time-limited/event/shop items are repeatable. No icons were extracted
from the screenshot.

## Source-aware planning and stop-policy boundary

The new `src/automation/farming_strategy.py` maps each **reference-only**
acquisition method to its potential task family, without invoking it:

| Reference method | Internal candidate task | Status / consideration |
| --- | --- | --- |
| Overworld mob | `BoundedRouteTask` | Exact numeric enemy ID, current map and reviewed route required |
| Forgery Challenge | `ForgeryTask` | Current eligible challenge, exact reward and Waveplate budget required |
| Simulation Training | `SimulationTask` | Current task/reward and resource budget required |
| Tacet Field | `TacetTask` | Current reward eligibility and Waveplate budget required |
| Synthesis | No qualified automatic task | Must verify recipe, ingredients and consumption |
| Quest/exploration/event/exchange | No qualified automatic task | May be one-time or time-limited |
| Historical subscription | No qualified automatic task | Do not assume current availability |

These are code-side integration *candidates*, not qualified sources.
`FarmingAssistantView.preview(...).acquisition_plan` exposes path-free
workflow suggestions, possible resource warnings, `selected_provider=None`,
`qualified_provider_ids=[]` and `can_dispatch=false`. A material being
selectable is not permission to dispatch any task. The browser API never
accepts a file path, arbitrary task class or an execution authorization flag.

`src/automation/farming_stop_policy.py` implements a conservative
`INVENTORY_TOTAL` versus `ENCOUNTER_LIMIT` stop-rule evaluation with at
most three bounded attempts. Missing observations block decisions; reaching
the target or attempt cap requests a stop. A value below goal does NOT enable
another action without independently approved runtime input/safety gates.
View previews keep `state=PLANNED_ONLY`, `enforced=false`,
`can_continue=false` and `can_dispatch=false`.

Codex must test these source/stop contracts in addition to the existing
inventory receipt and route runtime tests. Actual game observations remain
unauthenticated until independently reviewed. None of these modules is a
new executor or a replacement for the current `RuntimeQualification`.

## Implementation contract

- `src/automation/farming_selection.py` owns the 27 explicit material
  identifiers plus the existing five FF Mech Core mob name candidates.
- `FarmingAssistantView.targets("material")` displays all 27 and keeps
  `ff-mech-core` featured first for backwards-compatible initial selection.
- The Qt tab and standalone browser load the same `FarmingAssistantView`,
  without separate hard-coded material lists.
- Search is case-insensitive. New material previews accept an optional
  `INVENTORY_TOTAL` but keep observed inventory unknown and
  `can_start=false`, `can_pause=false`, `can_stop=false`.
- `SOURCE_UNRESOLVED` is the correct status when acquisition evidence is
  missing. `SOURCE_DOCUMENTED` for FF Mech Core means information only;
  it is not readiness to execute.

## Codex testing and source-qualification backlog

Codex must validate *each* of the 27 targets independently. For each item,
record exact in-game displayed name and numeric item ID, confirmed acquisition
method, corresponding enemy/domain/recipe/UI source **when observed**, game
version and map layer when relevant, actual before/after inventory receipt and
reviewed evidence hashes.

For confirmed mob drops, validate enemy numeric IDs, exact spawn geometry,
current-version map/reference calibration, bounded navigation and pickup, and
independent route qualification. For non-mob materials, do not assign a mob
route; implement an independently reviewed provider adapter only where a
verified appropriate non-combat flow exists. Distinguish drop probability
unknown from confirmed reliable drop behavior. Count combat clear and item
receipt separately. Stop when inventory target is confirmed, not after an
unobserved assumption.

Testing in order:

1. Run source/list/view/Qt/standalone HTTP tests; search and select **all 27**
   with no duplicate/missing names, and verify all Start buttons remain disabled.
2. Compare spelling and icons against the current game's actual inventory
   screen without committing account-identifying screenshots.
3. Establish genuine source method / item IDs one material at a time; do not
   invent mappings or routes based on display names.
4. Perform staged read-only capture and localization, then separately gated
   bounded game-control testing only after the existing independent Terra
   review and current-runtime qualification requirements pass.
5. Update each material's evidence/status separately. Do not mark catalog
   completeness as live farming success.

Windows commands (use repository-local interpreter):

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingSelection.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingStandaloneWeb.py -v
.\.venv\Scripts\python.exe scripts/verify_core_routes.py --all --output logs/core-routes/farming-27-materials
node --check src/web/farming_assistant/index.js
node --check src/web/farming_assistant/standalone.js
```

**Current release gates:** Catalog implementation completed in source only;
new regressions and Windows/Qt/browser execution **NOT RUN** in the
GitHub-only development session. FF Mech Core and the other 26 materials
remain **LIVE_VERIFICATION_PENDING / SOURCE_UNRESOLVED** as applicable. No
game input, spending, route execution or independent new Terra review claimed.
