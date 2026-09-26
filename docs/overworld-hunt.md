# Overworld hunt: setup and live validation

This fork implements a **single verified surface camp**. It is not yet certified
for unattended farming. The September 26 integration includes upstream `61bfa64`,
the subpixel matcher, and executable localization, short-walk, and hunt stages.
Saved-image and mocked tests are not evidence of successful gameplay.

The [September 26 live report](overworld-hunt-live-2026-09-26.md) records successful
localization, movement cancellation, short walks, combat, and one-camp clearance,
plus the fixes found during those trials and the remaining runtime/reliability limits.

## Run this checkout

Use `./.venv/Scripts/python.exe main.py` from this repository. A separately
installed OK-WW application does **not** include these local changes. Close that
other instance before starting this checkout or collecting calibration captures.
Keep the game running on an unlocked desktop. Configure the normal Start/Stop
shortcut and verify it before movement. All stages start already in the world.
On Windows, movement also checks the game's process privileges. If the game is
elevated and this checkout is not, start this checkout with matching privileges.
The task reports the mismatch before sending inputs; localization-only capture
remains available. This check does not elevate applications or accept prompts.
For an elevated game, right-click `run-local.cmd` in this repository and choose
**Run as administrator**, then handle the Windows prompt yourself. This starts
the repository's local Python app without automatically starting a hunt.
Codex's desktop-control helper may remain unelevated; in that case start tests
manually in the project app while Codex reads captures and logs.

Alternatively, close the Qt app and run `run-local-web.cmd` with the same
privileges as the game. It uses the built-in web interface on `127.0.0.1` and
opens the browser; it does not automatically start a hunt. The browser mode
requires FastAPI and Uvicorn, as declared by the framework's web extra:
`./.venv/Scripts/python.exe -m pip install "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0"`.
The existing `main_web.py` embedded-window mode remains the default; `--browser`
selects a normal browser and does not require pywebview.

## Prepare the profile

Use a north-up reference at the live minimap's pixel scale and the same game
resolution/UI/minimap settings as calibration. Identify two separated fitting
landmarks and at least one independent held-out landmark. The CSV format is:

```csv
label,image_x,image_y,kuro_x,kuro_y,role
```

Use `fit` or `held_out` in `role`. Fill coordinates from measured evidence;
do not use guessed coordinates. Existing CSVs with `reference_x/reference_y`
are also supported. The helper fits only uniform positive scale and translation,
checks the held-out error, verifies the exact mob/layer/spawns against the local
database, and checks camp count and image bounds.

```powershell
.\.venv\Scripts\python.exe -m src.overworld.profile_setup --help
```

Required arguments: `--reference`, `--landmarks`, `--database`, `--target`,
`--state`, one or more `--spawn-id`, `--frame-size WIDTH HEIGHT`,
`--max-error-pixels`, `--stationary-tolerance-pixels`, and `--output`.
Use `--floor` for a nonempty source floor id and `--matcher-calibration` for the
reference-bound hybrid calibration. Choose error limits before observing results.
The helper refuses to overwrite a profile and always produces a **draft** with
all three review flags false. Successful fitting does not attest surface terrain
or the current game layer.

After checking the surface, layer, reference scale, three landmarks, and safe
route in the game, set `surface_verified: true`. Set **Hunt Profile** to that
JSON file and **Target Mob** to its exact `target_mob` value.

## A: localization

Keep **Localization Only=true**, **Test Walk Only=false**, **Max Camps=1**,
**Safe Test Mode=true**, **Surface Only=true**, **Use Teleport=false**, and
**Use Motorcycle=false**. This mode sends no input, including camera input.

Run while the character and camera are stationary. Inspect the ten measurements,
the supplied stationary tolerance, and the absolute position against an independent
landmark. A consistent wrong location is still a failure. If those checks pass,
record the evidence and set `localization_verified: true` in this exact profile.
Invalidate this review if you change the reference/calibration or game map settings.

## B: short walk

Add `test_walk_target: [x, y]` in Kuro coordinates for a manually checked nearby
surface point outside enemy aggro. Add `test_walk_timeout` (1–30 seconds;
default 10). The target must lie inside the calibrated reference.

Set **Localization Only=false** and **Test Walk Only=true**. A fresh ten-sample
stationary check must pass before any movement starts. The short walk uses a
four-reference-pixel arrival radius, disables recovery actions, and stops on
combat, lost positioning, timeout, or cancellation. It never starts combat or
the camp controller. Check decreasing distance, correct heading, actual arrival,
and cancellation while moving. `ARRIVED` must agree with the actual screen.

Preserve the `[HUNT] test_walk` and navigation logs. After reviewing successful
walking and cancellation, set `navigation_verified: true`. The program does not
set review flags automatically.

## C: one camp

With both reviews complete, set **Localization Only=false** and
**Test Walk Only=false**. A fresh stationary preflight still runs. The controller
approaches the known spawns, hands combat to existing OK-WW character logic,
relocalizes after combat, and checks the camp before declaring it clear.

Verify fighting, actual remaining enemies, post-combat positioning, recovery,
and input release. Repeat from a fresh start. Already-empty camps do not prove a
successful kill, and the clear heuristic does not count loot or identify species.
The task remains limited to one camp, surface walking, and no teleport/motorcycle.

## Evidence and current limits

- `docs/overworld-hunt-live-validation.md` preserves the prior validation record.
- `assets/overworld/calibration/subpixel-validation/REPORT.md` describes saved-image
  results; its September 6 movement restriction describes the historical code.
- Current live A/B/C results remain pending until observed and recorded.
- Fresh profile/reference coverage is needed for a different area or scale.
- Logs are normally written to `logs/ok-ww.log`; retain the `[HUNT] events`.

Run the hunt regression modules with the local interpreter. Run Qt screenshot
test modules in separate processes, as `run_tests.ps1` does, to avoid application
singleton conflicts. Do not store calibration captures in `screenshots/`: the
framework's screenshot test runner clears that directory.
