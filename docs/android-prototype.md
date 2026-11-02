# Android prototype: implementation and device checks

Date: 2026-11-03 (Asia/Kuala_Lumpur)

See the [local verification record](android-verification-2026-11-03.md) for build,
test, lint and APK results. Physical-device checks below remain NOT RUN.

## Delivered scope

The standalone `android/` project is the first runnable step toward an Android
version of this fork. Both recognition and control execute locally. The app has
no network or broad storage permission and does not require a PC during use.

| Capability | Implementation | Evidence limit |
| --- | --- | --- |
| Setup and session screen | Native Kotlin Android views | Software startup tests; physical UX still needs checking. |
| Screen capture | User-consented MediaProjection + foreground service | Build/API checks do not prove a particular game/device permits usable capture. |
| Local recognition | Calibrated region, luminance + spatial correlation | Exact learned appearance; not universal OCR or mobile HUD recognition. |
| Touch control | Serialized AccessibilityService gesture plans | Real game acceptance and timing still need a phone. |
| Visual routine | Fresh stable frames, one pending action, disappear/reappear rearming, bounded timeout/taps | Touch completion is not verified game-task completion. |
| Touch lab | Tap, swipe, two simultaneous strokes and three visual taps | Tests the installed app's own target; not a game farming benchmark. |
| Calibration | Drag a region on a captured game image and save locally | Bound to target app and image dimensions; changed game UI requires recapture. |
| Diagnostics | Bounded metadata event history, device/SDK/session information and JSON export | No screenshots, credentials or game text included. |

No daily/boss/character profile is declared validated. No desktop validation
result is reused as mobile evidence. Existing Python source and Windows behavior
are unchanged.

## Architecture decisions

- Kotlin app + independent Kotlin/JVM `:core` module. Native Android views avoid
  an additional runtime UI framework for this first capability proof.
- The core owns geometry, calibration matching, task decisions and gesture plans.
  Android adapters own capture, focus tracking, permissions and touch dispatch.
- This version uses a small local matcher instead of shipping an OCR model before
  actual mobile screenshots establish a need. OpenCV/ONNX remain options for a
  later recognizer; they are not represented as installed features here.
- Screen data is downsampled to at most 720 pixels wide and sampled at most five
  times per second. These are implementation limits, not measured game latency.
- A whole-display capture is required so visual coordinates map to touches.
  Changes to display orientation/size end the session instead of guessing a remap.
- Foreground package and capture-generation checks bind every accepted frame to
  the current target. Gesture dispatch rechecks focus, frame age and display size.
- The touch lab is allowed only while its activity is resumed, including when the
  user enters the companion's own package as the selected target.
- The phone must remain unlocked. There is no reboot receiver, silent permission
  acceptance, root backend, game-file access or account login automation.

## First on-device run

1. Install the APK. If Android blocks enabling a downloaded accessibility
   service, follow its app-info prompt before returning to Accessibility settings.
2. Enable **JH WuWa touch control**. Return to the companion and confirm connected.
3. Turn the phone to landscape before capture when testing Wuthering Waves.
4. Start capture and accept Android's **Entire screen** prompt.
5. Open the touch lab. The frame count should advance and the game package should
   be replaced by the lab package only while the lab is active.
6. Tap **Tap**: expect one target touch. Try **Swipe**: movement events should rise.
   Try **2 fingers**: expect at least two concurrent pointers to be observed.
7. Tap **Run 3 visual taps**: the checkerboard should receive three touches, each
   separated by its disappearance and return. Compare the visible counter with
   the successful touch callback count; neither proves game automation.
8. Use Stop, switch apps, then lock the phone. Verify the routine ends and does
   not resume without a new explicit start; lock should end capture as well.
9. Export the report. A report contains metadata and event counts, not proof of
   screenshots or game outcomes that were not observed.

## Calibrate one game-menu action

Open the installed game from the companion and show a distinctive, harmless
menu button. Return to the companion, choose **Calibrate from game image**, and
drag a small rectangle around the button's text or icon. Avoid blank backgrounds,
animated regions and controls whose centre should not be tapped.

Save the calibration. Start with one tap. The routine waits up to ten seconds
for the game and a fresh capture; it then requires several matching frames
before dispatch. If it never matches, check the game UI, orientation and selected
region instead of lowering the threshold blindly. Creating a new calibration is
the recovery path for changed dimensions or layout.

Multiple taps require the learned appearance to disappear and then return.
This does not yet describe the whole daily-task sequence. Start from a known menu
and visually confirm what the touch actually did.

## Physical-device acceptance record

These checks remain **NOT RUN** until performed on the intended phone. Record the
phone model, actual Android version, game version/server, resolution/UI scaling,
orientation and graphics settings with the results.

| Check | Expected evidence | Status |
| --- | --- | --- |
| Fresh game capture | Visible mobile game image; no black/protected frame | NOT RUN |
| Single and overlapping gestures | Actual menu response and movement + attack behavior | NOT RUN |
| Focus/lock/revocation stops | No new touches after interruption; session does not auto-resume | NOT RUN |
| Calibrated game routine | Repeated observed expected menu outcome | NOT RUN |
| Sustained 20–30 minute session | Frame stability, capture-to-action latency, temperature, battery and failure log | NOT RUN |
| Representative farming loop | Complete fight, collect reward, repeat, recover | NOT IMPLEMENTED / NOT RUN |

## Next implementation milestones

1. Resolve any device-specific capture/input defects using the exported report and
   observed screen behavior.
2. Capture real mobile UI references and implement a verified menu/reward sequence.
3. Add one team's combat strategy and one farming loop with observed completion
   and recovery evidence.
4. Expand characters, bosses, device profiles and recognition only after those
   foundations are measured.

The repository's existing game-account risk notice still applies.

## Reference APIs

- [Android MediaProjection](https://developer.android.com/media/grow/media-projection)
- [AccessibilityService gesture dispatch](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#dispatchGesture(android.accessibilityservice.GestureDescription,android.accessibilityservice.AccessibilityService.GestureResultCallback,android.os.Handler))
- [Gesture strokes](https://developer.android.com/reference/android/accessibilityservice/GestureDescription.StrokeDescription)
- [Foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types)
- [AGP 8.9 compatibility](https://developer.android.com/build/releases/agp-8-9-0-release-notes)
