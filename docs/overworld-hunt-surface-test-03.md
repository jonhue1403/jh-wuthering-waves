# Fresh Test A capture: surface-test-03

The combined offline matcher validation passes. This capture is the next
prospective check; it does not authorize movement or Test B.

1. Close other OK-WW instances and disable all movement/combat/background
   automation. Manually choose a safe, open **surface** location outside enemy
   aggro, away from edges, water, entrances, transitions, and moving platforms.
   Verify the current area and floor from the game itself. Do not copy state 906
   or an empty floor id from the old reference as evidence of current location.
2. Stop the character and camera completely. Use the same north-up minimap mode,
   minimap zoom, HUD/UI scale, and 2560x1440 game-client resolution as the saved
   datasets. Keep the world HUD visible. Keep the PC awake, unlocked, and the
   game running and visible, with WGC capture access available.
3. In PowerShell at `Z:\Game\jh-wuthering-waves`, run the command below. It uses
   the existing no-input capture helper with a process-local WGC-only allowlist;
   it does not modify saved configuration or start HuntMobTask:

   ```powershell
   .\.venv\Scripts\python.exe -c "from config import config; config['windows']['capture_method'] = ['WGC']; from src.overworld.calibration_capture import main; main(['--profile', 'surface-test-03'])"
   ```

4. When the helper announces its five-second delay, switch to the game manually
   without rotating the camera. Leave all movement keys and mouse controls
   released. Keep **both character and camera stationary** through all ten
   samples, approximately 0.5 seconds apart, and until the helper completes.
   Do not open the map during those ten world frames. Ctrl+C cancels the helper.
5. **Without moving the character after the last world frame**, manually open
   the full map. Save one original-resolution, lossless PNG of the full game
   map screen as
   `assets/overworld/calibration/surface-test-03/full_map.png`. Use a screenshot
   capture, not a camera photo. Include the player marker, visible area/layer
   information, and surrounding landmarks. Do not teleport, switch map layers,
   use photo mode, resize the image, or move the character between the world
   frames and this screenshot. Keep the default map view if it already shows
   these details; record any map pan/zoom necessary to expose them.
6. Add `capture_notes.md` in the same folder recording the current area/layer
   as actually observed, why this is open surface terrain, whether the character
   and camera remained stationary, confirmation that the map screenshot is from
   the **exact same unmoved character position**, and any map pan/zoom. Leave
   uncertain state/floor IDs marked unknown for review; an old profile or quest
   tracker is not independent layer evidence.
7. Check `metadata.json`: `complete` must be true, `frame_count` must be 10,
   dimensions must be 2560x1440, and **each** frame's `capture_backend` must be
   `ok.device.capture_methods.windows_graphics.WindowsGraphicsCaptureMethod`.
   Preserve `stationary_001.png` through `stationary_010.png`, metadata, the one
   `full_map.png`, and notes together. Inspect all frames for HUD visibility and
   stationary character/camera. Any missing frame, non-WGC backend, camera change,
   displacement, aggro, or movement before the map screenshot invalidates the
   sequence. Retain that evidence and repeat under a new unused label; the
   helper refuses to overwrite an existing or partial capture.

No new live profile is installed automatically. The fresh map screenshot must
be reviewed for layer, reference coverage/scale, landmarks, and absolute position
before treating replay as live Test A validation. A low stationary spread alone
does not prove correct localization. If the current location is outside the
validated reference, stop for reference/calibration review rather than forcing
the old matcher or weakening its thresholds.

Keep Localization Only=true, Max Camps=1, Safe Test Mode=true, Surface Only=true,
Use Teleport=false, and Use Motorcycle=false. **Do not start any movement/combat
automation. Do not run Test B.** This document supplies capture instructions;
the capture has not been performed by this validation task.
