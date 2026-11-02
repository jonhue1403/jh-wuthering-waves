# JH WuWa Mobile

An **Android feasibility prototype** that runs screen capture, local image
matching and bounded touch actions on the phone. No running PC, root, API key or
cloud service is needed during a session.

This version includes a touch lab and a user-calibrated visual tap routine.
**It does not yet include verified daily farming, boss loops or character combat.**

## Try it

1. Install the prototype APK on Android 8.0 or newer.
2. Enable **JH WuWa touch control** in Android Accessibility settings.
3. Rotate the companion to landscape **before** starting capture when testing
   the landscape game. Enable system auto-rotate if needed.
4. Tap **Start screen capture** and choose **Entire screen** in Android's prompt.
5. Open **Touch lab**. Try **Tap**, **Swipe**, **2 fingers**, then **Run 3 visual
   taps**. Check the target counter, movement events and maximum finger count.
6. To test a game button, open the game, show the desired menu, return here, and
   choose **Calibrate from game image**. Drag around its distinctive text/icon.
7. Save the calibration, keep maximum taps at **1**, and run it. Check the result
   in the game before increasing the limit.

Keep the phone unlocked and the target app visible. Opening another app stops a
running routine. Capture stops on lock, screen-off or orientation changes; start
a fresh session afterward. A stop prevents new touches immediately; an already
dispatched gesture can finish within 750 ms.

The selected image must disappear and reappear before a repeat tap. The routine
ends after its tap limit, timeout or an interruption. Successful touch callbacks
are **not** proof that a game reward was collected.

Use **Export session report** to save diagnostic metadata. Images stay in memory;
the report contains no screenshots, credentials or game text. Calibration is
stored locally and bound to its target package and capture dimensions.

## Build and verify

Install JDK 17 and Android SDK platform 35/build-tools 35.0.0. From this directory:

```sh
./gradlew :core:test :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

On Windows use `gradlew.bat`. Set `ANDROID_HOME` or your local `local.properties`
to the SDK location. The Gradle wrapper downloads the pinned Gradle 8.11.1
distribution and verifies its checksum.

APK: `app/build/outputs/apk/debug/app-debug.apk`. This is a debug-signed prototype;
builds from different machines may have different signing keys and require
uninstalling an earlier prototype before installation (which clears calibration).
Do not commit signing keys.

The Android workflow publishes the APK and verification reports when its run
succeeds. The existing Windows application and workflows are separate.

See [implementation and device checks](../docs/android-prototype.md) for exact
scope, limitations and the remaining physical-device acceptance tests.

The [local verification record](../docs/android-verification-2026-11-03.md) lists
the 62 passing tests, lint warnings, source review and delivered APK checksum.
