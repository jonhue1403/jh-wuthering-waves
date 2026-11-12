# Farming Assistant — read-only receipt evidence intake

Status: **LOCAL CANDIDATE AUDIT ONLY; NEVER GAMEPLAY AUTHORIZATION** (13 Nov 2026).

This feature gives the Material-first Farming Assistant a bounded way to inspect
**locally collected, independently reviewed evidence metadata** without exposing
developer paths in the Material/Mob UI. It does **not** produce a live material
source mapping, qualify a reviewed movement route, start an executor, attest that
screenshots genuinely show the game, or override existing PR #4 safety gates.

## Operator workflow (only in a separately authorized local game session)

1. Keep Story Watch/no-skip enabled and the normal exclusive input owner/focus,
   capture-freshness and privilege checks intact. Preserve the running recorder.
   This audit does not capture screenshots or send inputs.
2. Independently observe an actual game version, exact material item-detail
   label, exact *game* mob ID and a source mob in the current Kuro map database.
   The wiki's `geospider-s4`-style strings are **catalog identifiers**, not Kuro
   IDs. Never infer a real game ID, drop rate or spawn from the display name.
3. For a separately qualified bounded test, record two distinct fresh item-detail
   screenshots showing the exact same material before and after, distinct frame
   IDs, the same observed run/session ID and an actual positive inventory delta.
   A combat win, pickup prompt or clicking F is **not** proof of a drop.
4. An independent reviewer checks the original images, item label and quantity,
   frame provenance, game version, exact mob identity and live sequence. Only
   after an actual review may the evidence manifest say `"status":"REVIEWED"`
   and `"independent_review":true`. These flags are *claims in the file*;
   the preview cannot authenticate who reviewed it.
5. Store the two evidence images and manifest in the private local application
   folder `configs/farming-assistant/evidence/`. Do not commit screenshots or
   account details to GitHub. Maximum 24 JSON manifests per scan; only direct
   child files are used. The scanner accepts at most 16 KiB per manifest and
   16 MiB per image. It rejects symlinks, missing files, invalid digests,
   ambiguous IDs, future-dated or older-than-30-day receipts, no inventory gain,
   duplicate frame IDs, and unsupported screenshot paths. The shared strict
   JSON reader additionally rejects duplicate keys at any nesting level,
   nonstandard `NaN`/`Infinity` tokens, and files that grow beyond the
   manifest byte limit during read. Ambiguous metadata never becomes a receipt
   candidate.
6. In the Farming Assistant, a local hash-matched record appears as
   **Local receipt candidate (unverified)**, never as a verified mob/route.
   A changed file, expired snapshot or incomplete scan must trigger renewed
   inspection. A 10-second bounded read-only cache avoids repeated hashing.
7. **Separate live qualification**: use the existing `RuntimeQualification`,
   `MaterialRoute`, `SurfaceProfile`, exact source/profile/image/database hashes,
   reviewed map layer and stage-specific evidence. Current runtime/game
   versions, session ownership, fresh capture and stop/cancel checks are
   mandatory. This feature does **not** connect to, or substitute for, those
   executor checks.

## Local manifest contract

Write one JSON object per observed receipt. All values below are descriptive
placeholders, **not captured results**, and MUST NOT be copied into a purported
real reviewed manifest without replacing them with genuine measurements.

```json
{
  "schema_version": 1,
  "status": "DRAFT",
  "independent_review": false,
  "material_id": "ff-mech-core",
  "catalog_mob_id": "geospider-s4",
  "game_mob_id": "REPLACE_WITH_OBSERVED_NUMERIC_GAME_ID",
  "game_version": "REPLACE_WITH_OBSERVED_VERSION",
  "session_id": "REPLACE_WITH_ACTUAL_SESSION_ID",
  "observed_at": "2026-11-13T04:00:00+08:00",
  "inventory_before": 0,
  "inventory_after": 0,
  "frame_before": "REPLACE_WITH_ACTUAL_BEFORE_FRAME_ID",
  "frame_after": "REPLACE_WITH_ACTUAL_AFTER_FRAME_ID",
  "inventory_before_image": "before.png",
  "inventory_after_image": "after.png",
  "evidence_sha256": {
    "before.png": "REPLACE_WITH_ACTUAL_SHA256_OF_BEFORE_IMAGE",
    "after.png": "REPLACE_WITH_ACTUAL_SHA256_OF_AFTER_IMAGE"
  }
}
```

The draft example intentionally **fails** the reader. In actual records, the
game mob ID must be an observed numeric ASCII string (not a catalog slug);
`after` must be greater than `before`; SHA256 digests must be lowercase
64-digit hex for actual screenshot bytes; both screenshots must be different
files with distinct frames; date/time must be timezone-aware; and independent
review must have happened. Do not invent or backdate observations.

The scanner reports only aggregate counts, source identities asserted by
historical metadata, evidence hash status and safe next steps; it does not
expose image bytes, private file paths, session identifiers or reviewer details.

## Validation handoff to Codex

From the working branch in Windows PowerShell:

```powershell
git fetch origin
git switch agent/material-first-farming
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingEvidence.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingStaticJSON.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantView.py -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingAssistantQt.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_evidence.py src/automation/farming_view.py src/gui/FarmingAssistantTab.py
node --check src/web/farming_assistant/index.js
```

After unit tests, open both UI implementations and verify `PREVIEW_ONLY`,
visible candidate count, non-disclosure of local paths, disabled Start/Pause/Stop,
no installed game inputs, and no false route readiness even if a synthetic
hash-consistent manifest is present. Preserve existing tasks, PR #4 and
calibration artifacts; never enable live execution based on an offline test.
