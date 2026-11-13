# Farming Assistant — current-runtime capture claim handoff (v1)

**Status: implementation of a review-packet contract, NOT live evidence, a
trusted runtime adapter, completed Terra review or permission to farm.**

`src/automation/farming_live_handoff.py` implements a small, frozen Python
`FarmingObservationHandoff` record and `build_observation_handoff` parser.
This is a **pure in-memory intake** for later local Codex/Terra qualification.
The module cannot control the screen, inspect files, invoke OK Script tasks,
review its own evidence, change FarmingCatalog readiness or unlock any Start,
Pause or Stop control.

## Boundary and intended use

1. A future **local trusted runtime capture adapter** observes the installed
   game and OK Script versions, current game enemy ID, map layer, fresh frame
   identities, relevant profile/reference/database bindings, source hashes
   and SHA256 of original evidence frames. The packet is not constructed from
   user-facing path text or the web/Qt preview. No account secrets or raw
   screenshots should be included in JSON payloads.
2. The adapter sends one capture **claim** to
   `build_observation_handoff(payload)` within 15 minutes of capture.
   Timezone-aware timestamps are mandatory; a future skew beyond two minutes
   is rejected. The builder checks types, declared digest coverage, stages,
   exact numeric enemy IDs, valid receipt deltas and duplicate/identical
   images, then creates an immutable packet and deterministic SHA256 digest.
3. Codex preserves the private original evidence and performs local hash
   verification against **actual files**. The packet digest binds *declared*
   fields; it does not prove that they came from the game or that a reviewer
   approved them. Do not export original images to the repository or include
   their paths in an ordinary user-facing response.
4. Terra (independent of implementation) verifies source/enemy identity,
   actual inventory before/after, chronological frame sequence, game version,
   runtime version, map layer, bounded route/spawns and focus/session safety.
   `RuntimeQualification.assert_compatible` and its stage-specific SHA256
   checks remain mandatory before any separately authorized executor path.
   A material receipt alone does not prove a route; a route alone does not
   prove a drop. No historical route/profile flag substitutes for live review.
5. Record independent review findings outside the capture object. Do **not**
   add `approved`, `can_start`, `status=REVIEWED`, `signature` or similar
   fields to the intake: the exact schema rejects these. The `public_summary`
   is deliberately path-free, marks everything unauthenticated and always
   returns `can_start: false`.

## Exact v1 capture schema

All 19 fields below are mandatory and extra fields are rejected:

| Field | Requirements |
| --- | --- |
| `schema_version` | integer `1`, never bool |
| `purpose` | `SOURCE_DROP`, `ROUTE_SURVEY`, `RUNTIME_PREFLIGHT` |
| `target_kind`, `target_id` | `material`/`mob` and exact catalog slug; selection identity still needs independent checking |
| `game_mob_id` | observed ASCII-decimal string, 1–32 digits, **preserve leading zeros** |
| `game_version`, `ok_script_version` | bounded printable version claims, NOT authenticated |
| `session_id`, `observed_at` | private opaque session token and timezone-aware timestamp |
| `stage` | one of existing runtime qualification stages; source drop requires `SINGLE_CAMP` or `MATERIAL_ROUTE` |
| `route_id` | opaque ID or empty for non-route observation; `ROUTE_SURVEY` needs an ID |
| `state_id`, `floor_id` | explicit map layer claim |
| `frame_ids` | 1–4 distinct frame tokens; two frames required for `SOURCE_DROP` |
| `frame_sha256` | exact frame-token-to-lowercase-hex SHA256 mapping; source-drop frame digests must differ |
| `bindings_sha256` | `profile`, `reference`, `database`; optional `matcher_calibration` |
| `source_sha256` | exactly the existing `REQUIRED_SOURCES` from `src/overworld/qualification.py`; for `MATERIAL_ROUTE`/`BEACON`, also material route and bounded-route task source hashes |
| `inventory_before`, `inventory_after` | for `SOURCE_DROP`: genuine nonnegative integers and positive delta, no booleans; for other purposes: both `null` |

The builder does not read the sources or evidence itself. **Matching digests
in a supplied JSON packet only means that the claim is internally consistent.**
It must never be passed as `source_is_qualified` or
`route_is_qualified` for an executor.

## Tests and Codex handoff

The synthetic regression suite checks the frozen record, canonical digest
stability, incoming value alterations, unknown status/approval fields, stale
timestamps, missing SHA bindings, invalid identifiers, duplicate/identical
frames, insufficient item gains, route-only claims and public-summary
non-disclosure.

Run on a clean checkout of `agent/material-first-farming`:

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCalibrationGuide.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingPreflight.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_live_handoff.py
```

**Tests are NOT RUN in the connected GitHub-only session.** Neither a built-in
`python -m compileall` check nor GitHub file commits are a substitute for the
actual Windows/Qt runtime and independent Terra review.

## Next independently reviewable implementation increment

Implement an **internal, read-only, opt-in observation capture adapter**
using the existing frame/focus/session abstractions, first in local preview
mode. It should not request new gameplay input, route dispatch or OCR clicks.
Capture actual version strings and immutable frame provenance from the running
client, then compare declared digests with the original local evidence before
forwarding the packet for review. A successful structural handoff still has
no ability to start farming. Codex's screen-controlled tests belong to the
later explicitly authorized test phase.
