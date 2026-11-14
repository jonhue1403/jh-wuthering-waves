# Material-first Farming Assistant — catalog inventory and Codex qualification

## Screenshot inventory

The 27 names below were transcribed **as displayed** in the operator-supplied
nine-row, three-column material screenshot (14 November 2026). They are
searchable/display-only targets, not validated numerical item IDs, drop tables,
recipes, domains, camps, routes or direct game-controlled farming jobs.

| # | Material name | Stable UI ID | Acquisition evidence | Automated farming |
| ---: | --- | --- | --- | --- |
| 1 | Premium Tuner | `premium-tuner` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 2 | Premium Sealed Tube | `premium-sealed-tube` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 3 | Premium Resonance Potion | `premium-resonance-potion` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 4 | Heterized Metallic Drip | `heterized-metallic-drip` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 5 | Mysterious Code | `mysterious-code` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 6 | FF Whisperin Core | `ff-whisperin-core` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 7 | FF Howler Core | `ff-howler-core` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 8 | Tailored Ring | `tailored-ring` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 9 | Mask of Insanity | `mask-of-insanity` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 10 | Flawless Phlogiston | `flawless-phlogiston` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 11 | Presto Helix | `presto-helix` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 12 | Waveworn Residue 239 | `waveworn-residue-239` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 13 | Cadence Blossom | `cadence-blossom` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 14 | Premium Energy Core | `premium-energy-core` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 15 | FF Tidal Residuum | `ff-tidal-residuum` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 16 | FF Polygon Core | `ff-polygon-core` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 17 | Echo Modifier | `echo-modifier` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 18 | FF Exoswarm Core | `ff-exoswarm-core` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 19 | Reverb Combustor | `reverb-combustor` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 20 | FF Mech Core | `ff-mech-core` | Possible enemy sources documented; actual drops not verified | **NOT QUALIFIED** |
| 21 | Intact Exoswarm Pendant | `intact-exoswarm-pendant` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 22 | Layered Wing Polarizer | `layered-wing-polarizer` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 23 | Melodic String | `melodic-string` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 24 | FF Carved Crystal | `ff-carved-crystal` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 25 | FF Waveworn Shard | `ff-waveworn-shard` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 26 | Transducer | `transducer` | Unknown; needs in-game verification | **NOT QUALIFIED** |
| 27 | FF Autopuppet Kernel | `ff-autopuppet-kernel` | Unknown; needs in-game verification | **NOT QUALIFIED** |

FF Mech Core retains the five existing **community-documented possible enemy
sources**: Geospider S4, Sabercat Reaver, Spacetrek Explorer, Twin Nova:
Collapsar Blade and Twin Nova: Nebulous Cannon. Those are informational only;
neither numeric game IDs nor verified loot receipts/eligible routes are present.

No source relationships have been created for the other 26 materials. Do not
assume all items are enemy drops or can be farmed. Some items may have a
non-combat acquisition method (synthesis, challenge rewards, shops, other UI
flows); these are hypotheses and **must be checked from actual game evidence**
before implementation. No icons were extracted from the screenshot. The
catalog contains display names and stable UI slugs only.

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
