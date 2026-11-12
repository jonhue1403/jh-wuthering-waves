# Farming Assistant — local profile and route candidate audit

**Status (13 November 2026): read-only static intake, NEVER a route permission.**

The Farming Assistant scans private local metadata to help an operator identify
which candidate route files need calibration. The audit cannot move the player,
run combat, read the live game, call the existing route executor, or assert a
current-version route is qualified. Even a route labeled `REVIEWED` is merely
an unauthenticated local file claim; a matching SHA256 proves file consistency,
not the truth of the observation, the reviewer, or the game version.

## Private local intake

Store a **copy** of candidate files at:

`configs/farming-assistant/routes/`

- Route manifests: direct-child files named `*.route.json`, maximum 8 per scan.
- Each manifest references one direct-child JSON `profile` and its exact
  `profile_sha256`. For this isolated read-only audit, filenames must be
  single-component names, e.g. `surface.profile.json`; nested paths and
  absolute paths are rejected. Copies must be rebound and hashes updated by
  the operator; **do not** modify an approved runtime manifest merely to
  make a stale candidate pass. The actual executor uses its own independently
  reviewed source location and current-game qualification.
- All files in `evidence_sha256` must be direct child files of this private
  directory. Max 8 evidence files per manifest, max 8 MiB each; the complete
  scan has a 64 MiB hashing budget. Excess/changed/missing/symlinked files
  are rejected or make the scan incomplete. Max 48 KiB per route JSON, max
  32 KiB per profile JSON.
- The route must explicitly claim `schema_version: 1`,
  `status: REVIEWED`, `surface_only: true`, an observed source mapping,
  a numeric game mob ID (not a catalog slug), exact matching profile/layer,
  1–3 camps, bounded finite waypoints, a finite time/radius, a compatible
  inventory-reader contract, and hashed evidence for every camp, source,
  item reader and pickup.
- Malformed/ambiguous JSON is rejected, including duplicate keys at **any**
  nesting level and nonstandard `NaN`/`Infinity` literals. The JSON decoder
  also enforces its byte cap when reading, not only from the prior file stat.
- Two different local manifest filenames cannot count as two independent
  routes if they claim the same `route_id`. Duplicate route identity is
  rejected as a static input error; neither the surviving candidate nor the
  rejected duplicate authorizes farming.
- Files are never uploaded, and account/profile screenshots should never be
  committed to GitHub. The scanner has a bounded 10-second read-only cache.

If the UI says **Local route candidates (not live-qualified)**, the local
metadata and bounded hashes passed *static inspection only*. It still cannot
populate `qualified_route_ids`, `verified_mob_ids`, `owned_quantity` or
`can_start`. A zero count or audit error is a useful calibration problem to
resolve, not an instruction to invent a route.

The Material/Mob screens show only a path-free candidate count and an error
flag; users never have to enter a Route Manifest or Hunt Profile path.
Mob-name selection cannot infer an internal numeric game mob ID from a wiki
slug; the material and mob execution pathways remain blocked independently.

## What this audit deliberately cannot qualify

Static intake does **not** validate an actual drop from the game's inventory
screen, independently prove a route reviewer, inspect the current Kuro map
spawn database, compare map images with live frames, observe current
`ok-script` or game versions, bind all current source-code hashes or authorize
input. It does not replace `MaterialRoute.load`,
`MaterialRoute.validate_spawns`, `SurfaceProfile.load`, or
`RuntimeQualification.assert_compatible`.

Before gameplay, Codex and an independently assigned reviewer must verify
the real FF Mech Core drop source and inventory delta, exact numeric mob ID,
spawn/database/image/profile provenance, map layer, every camp and connecting
waypoint, current game/runtime versions, fresh focus/capture,
Story Watch/no-skip, exclusive input ownership, a valid reviewed
`MATERIAL_ROUTE` sidecar, cancellation/held-input release, and bounded
inventory receipt checks. Current documented source names do **not** meet
these gates. Start/Pause/Stop remain disabled and no executor is dispatched.

## Local Codex checks (Windows PowerShell)

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRouteAudit.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingEvidence.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_route_audit.py src/automation/farming_view.py src/gui/FarmingAssistantTab.py
node --check src/web/farming_assistant/index.js
```

Review screenshots of the two preview tabs and ensure that invalid/stale
local entries never enable Start, Pause, Stop or any game input. The tests
use synthetic in-memory/temp-file data only: passing them would **not**
be a live FF Mech Core qualification.
