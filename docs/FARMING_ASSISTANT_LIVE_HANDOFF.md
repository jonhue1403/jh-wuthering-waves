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

## Local original-artifact verification (offline; not approval)

`src/automation/farming_capture_verify.py` provides
`verify_local_capture_claim(packet, source_root=..., evidence_root=...,
frame_files=..., binding_files=...)`. This is the next **read-only local
artifact adapter**, NOT a screen capture implementation or a trusted
current-game observation. It accepts an immutable v1 capture handoff from the
previous step. Only internal local capture code may supply the roots and
file maps; the operator-facing Farming Assistant has no path inputs.

- Required source names come from the handoff; their actual bytes are hashed
  beneath a local trusted checkout root. Frame tokens and binding labels map
  to relative artifact filenames beneath a separate private evidence root.
- Exact map coverage, relative-path syntax, containment, symlink rejection,
  missing/unreadable artifacts and bounded byte reads are enforced. Any
  digest mismatch rejects the **entire** packet: there is no partial pass.
- Original frame files, calibration bindings and source code each must match
  their declared SHA256. An independently checked packet must still pass
  actual game-origin, installed-version, enemy identity, inventory OCR,
  frame chronology, session/focus and Terra review gates separately.
- An expired 15-minute observation is rejected even if every saved byte
  still hashes correctly. Private evidence files remain local and must not
  be committed or uploaded to GitHub.
- The only positive outcome is `LOCAL_HASH_MATCH_ONLY`; all outcomes have
  `evidence_authenticated=false`, `route_qualified=false`,
  `independent_review_complete=false`, `can_start=false`.
  No task dispatch, combat, navigation, OCR interaction or resource spending
  is connected.

Local offline test commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_verify.py
```

**Tests NOT RUN in the GitHub-only editing session.** A matching local hash
is never a live FF Mech Core receipt or executable route.

## Next independently reviewable implementation increment

When Codex begins the authorized local testing phase, wire an internal
**opt-in, read-only frame/focus/version capture producer** using the current
OK Script runtime abstractions. Feed actual images and observed versions into
the handoff and local-byte verifier without user path fields. Preserve the
independent Terra verification boundary; do not connect the farming executor
or trigger game input while calibration evidence is missing.

## Opt-in OK Script frame producer (untrusted, read-only)

`src/automation/farming_runtime_capture.py` introduces
`capture_readonly_frame(task, opted_in=True)` as an **internal-only**
foreground screenshot acquisition boundary. No Qt/Web operator action or
task registration currently calls it. It uses existing OK Script
`task.next_frame()` / `task.frame` primitives; matches the task's real
`executor.device_manager.hwnd_window.hwnd` against the Windows foreground
HWND before and after capture/encoding; checks cancellation; rejects
malformed/oversized frames; and reads the installed `ok-script` package version.
PNG bytes remain private in a frozen `ReadOnlyFrameSnapshot`, excluded from
repr and `public_summary()`. No profile paths or user file inputs are exposed.

On non-Windows systems without a test monkeypatch, focus checks fail closed.
The producer proves **neither** frame freshness nor uncached capture, installed
game version, inventory OCR/receipt, enemy identity, authenticated origin, route
qualification, nor independent review. It cannot make `RuntimeQualification`
or source-to-route authorization; source and calibration hashes still need
actual local verification. It never calls game input or starts a route.

Local Codex follow-up: validate this bridge on the actual Windows OK Script
installation and inspect WGC cached/focus metadata before any review packet.
Do not connect Start/Pause/Stop or the executor to unreviewed snapshots.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRuntimeCapture.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_runtime_capture.py
```

The 10 synthetic tests **PASSED in an isolated Linux container** using mocked
task, window and runtime metadata. Windows/real-game startup, end-to-end
handoff integration and independent Terra review remain **NOT RUN**.


## Opt-in private capture retention (no reviewer authority)

`src/automation/farming_capture_retention.py` provides the **internal-only**
`retain_readonly_snapshot(snapshot, private_root=..., capture_token=..., opted_in=True)`.
It takes a `ReadOnlyFrameSnapshot` from the read-only OK Script capture adapter
and writes its original PNG bytes for later local Codex/Terra examination.
It is **not wired to any UI action, Start button, route task, inventory OCR,
or game controller**. It does not issue game input or create a live handoff packet.

- A pre-existing, absolute **private evidence directory outside the Git
  repository** must be provisioned by local Codex. Do not publish, sync or
  commit screenshots. Restrict access to the intended Windows user via
  filesystem ACLs; `0o600` on Windows is not a complete ACL policy.
- Each capture needs an internal unique opaque token; filenames are fixed
  under that root. Existing files cannot be overwritten. The implementation
  rejects relative/traversal tokens, symlink/junction roots where visible,
  malformed or changed PNG/hash claims, missing/unsafe directories, and
  claims outside the 15-minute freshness window. It uses exclusive creation,
  file sync and local readback. It never removes prior accepted evidence.
  Caller-controlled root paths must not come from the operator form.
- Filesystem concurrency is a **trusted-local-root assumption**: this is
  not a sandbox against an attacker with write access to the private directory
  or its ancestors. Codex must verify Windows ACL/reparse-point behavior.
  A PNG signature/readback proves bytes were stored, not game-frame origin.
- The returned private record keeps a relative filename for eventual
  `verify_local_capture_claim` integration; `public_summary()` omits the
  filename and raw bytes and explicitly reports `can_start=false`.
- No snapshot is taken merely by importing the module. Independent game
  version, capture chronology/cached-frame flags, numeric enemy ID, inventory
  delta, source SHA-bound review and route/runtime qualification remain blocked.

Synthetic isolated verification: **9/9 unittest cases PASSED**, using the
retention module with a stub `ReadOnlyFrameSnapshot` type contract; Python
compilation of source/tests also passed. These are **not** tests of the full
checkout or a real Windows/OK Script game session. Local Codex commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureRetention.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingRuntimeCapture.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_retention.py
```


## Private retained-frame binding to observation claims (2026-11-13)

`src/automation/farming_capture_binding.py` now provides an **internal-only,
read-only** bridge between `RetainedReadOnlySnapshot` records and the frozen
`FarmingObservationHandoff`. It requires exact frame-ID coverage, unchanged
SHA256 per frame, private basename-only `farm-frame-*.png` references, distinct
private filenames, timezone-aware freshness and strictly increasing capture
timestamps. The handoff observation timestamp must follow the frame captures
and the last frame must be within two minutes of the observation claim.
A `SOURCE_DROP` claim inherits the v1 requirement for distinct before/after
frames and a positive **claimed** delta; that is not independent OCR evidence.

`bind_retained_frame_files(packet, retained, now=...)` returns an immutable
frame-reference binding. Its `internal_frame_files()` is **never** for
operator/UI serialization. `verify_retained_capture_claim(...)` connects
this binding to the existing `verify_local_capture_claim` which checks
original source, binding and frame **bytes on disk**. It returns only
`LOCAL_HASH_MATCH_ONLY` or a rejected integrity audit; a successful result
cannot promote a drop source, approve a route, qualify runtime or enable input.
Binding records are still untrusted claims, and the private directory must
remain protected and local. No file paths are accepted from the user UI.

Focused Windows commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureBinding.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureRetention.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingLiveHandoff.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_binding.py
```

The 10 binding tests passed in a **Linux synthetic stub-contract harness**
using the new production binding module and stand-in classes for its three
existing dependencies. This does NOT establish that the complete repository
test suite, actual OK Script, Windows ACL behavior or live game works. Those
remain pending Codex/Terra local qualification. No gameplay execution is wired.


## In-memory snapshot/retention/handoff consistency (read-only)

`src/automation/farming_capture_session.py` now provides
`inspect_readonly_capture_session(packet, snapshots, retained, now=...)`.
This **pure, private consistency check** runs before
`verify_retained_capture_claim(...)` hashes original files on disk. The caller
must use snapshots from the opt-in OK Script capture producer and matching
`RetainedReadOnlySnapshot` records; no operator-supplied filenames or mutable
UI/route state enter this API.

It fails closed on missing/extra frame IDs, altered in-memory PNG bytes,
wrong retention size/hash, OK Script version mismatch, changed dimensions,
timestamp disagreement, reversed/expired captures and unsafe retained
frame bindings. All success means is that **the same private image bytes**
are consistently represented in memory and metadata. PNG-signature
inspection is not a full image decode. Capture timestamps are not independently
attested sequence numbers. A matching session is **not** proof of installed
game version, genuine frame freshness, FF Mech Core drop, executable route
or OCR inventory receipt. Gameplay controls remain disabled.

The frozen summary is path-free, has no session ID, screenshot bytes, private
filename or inventory quantity and reports `can_start=false`,
`original_files_verified=false`, `independent_review_complete=false`,
`route_qualified=false`. Actual original disk bytes must still pass the
separate verifier followed by Codex/Terra independent live qualification.

Windows checkout commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureSession.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureBinding.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestFarmingCaptureVerify.py -v
.\.venv\Scripts\python.exe -m py_compile src/automation/farming_capture_session.py
```

Local Windows/Qt/OK Script integration and independent Terra qualification
remain **NOT RUN**. The isolated synthetic harness used stand-in dependencies,
not the complete checkout.
