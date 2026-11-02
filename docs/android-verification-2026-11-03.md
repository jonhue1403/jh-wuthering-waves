# Android prototype verification record

Recorded 2026-11-03 (Asia/Kuala_Lumpur; 2026-11-02 UTC).

## Result and evidence boundary

The Android feasibility prototype builds into an installable, debug-signed APK.
The local core and Android component checks pass. This record does **not** claim
that the APK has been installed on a phone, that Wuthering Waves accepts its
capture or touch input, or that any daily, combat or farming task has succeeded.

No physical phone or usable Android emulator was available in the build
environment. The Android component tests run under Robolectric at API 35.

## Verification performed

The project was built with JDK 17.0.21, Gradle 8.11.1, Android Gradle Plugin 8.9.2,
Kotlin 2.1.20, Android SDK platform 35 and build-tools 35.0.0. From `android/`:

```sh
./gradlew :core:test :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

The local environment used the same Gradle distribution through a launcher that
supplied the SDK, JDK and network proxy locations. The checked-in wrapper pins
that distribution and its SHA-256 checksum.

| Check | Result |
| --- | --- |
| Core tests | 34 passed; 0 failures, errors or skips |
| Android component tests | 28 passed; 0 failures, errors or skips |
| Android lint | Completed; 0 errors and 11 warnings |
| Debug APK assembly | Passed |
| APK signature | `apksigner verify` passed; v2 signature, one signer |
| APK metadata | `com.jh.wuwa.mobile`, version `0.1.0-prototype` (1), target API 35 |
| Permission inspection | Foreground service, media-projection service and notifications; no Internet or storage permission |
| Independent source review | Concrete findings addressed before the final local verification |
| Physical-device / game checks | NOT RUN |

### Test coverage

- Geometry, calibrated-region matching, insufficient contrast and invalid inputs.
- Fresh and distinct frames, stable appearance, disappear/reappear rearming,
  cooldown, timeout, tap limits and delayed gesture acknowledgements.
- Loss of capture/focus, cancellation and bounded overlapping gesture plans.
- Strict local calibration decoding, including overflow and fractional numbers.
- Portrait/landscape activity creation, calibration selection and state transfer.
- Lab pause/destruction, queued callbacks, own-package restrictions and cancellation
  of an armed lab routine when the lab leaves the foreground.

These checks exercise implementation logic. They do not measure native input
latency, OEM behavior, game recognition quality, thermals or battery use.

### Remaining lint warnings

The 11 warnings comprise eight `SetTextI18n` messages for the prototype's English
UI, one allocation in custom-view drawing, one custom-view constructor warning,
and one legacy backup-configuration warning. Backup is disabled in the manifest;
Android 12+ extraction rules also exclude app data. These warnings are recorded
and are not represented as a warning-free result.

### Review findings addressed

- Serialize capture-resource teardown after in-flight image processing completes.
- Coalesce captured frames into one pending delivery slot.
- Reject stale frames across focus/session changes and recheck the active app
  immediately before touch dispatch.
- Reject a second manual gesture before advancing its callback generation.
- Cancel both pending and active own-app routines when the touch lab pauses.
- Keep the landscape target pad stable while its controls scroll; preserve a
  usable calibration image alongside the landscape controls.
- Preserve meaningful terminal status instead of overwriting it on every frame.

Stop prevents new touch scheduling immediately. An already dispatched finite
gesture can still finish within the enforced 750 ms limit.

## Delivered APK

The locally built file provided with this record is named
`jh-wuwa-mobile-0.1.0-prototype.apk`.

| Property | Value |
| --- | --- |
| File size | 985,409 bytes |
| SHA-256 | `b462f3a65f804f09d1bdca27e76c50a42205b218e36ff758e4bdc104040befe5` |
| Package | `com.jh.wuwa.mobile` |
| Version | `0.1.0-prototype` / code 1 |
| Minimum Android | Android 8.0 / API 26 |
| Target Android API | 35 |
| Signing | Local debug key; development use |

The APK is not committed to git. A fresh CI build may have a different debug
signing key and hash. Replacing an installation signed by another key can require
uninstalling it first, which clears that installation's saved calibration.

## CI and remaining acceptance

The Android workflow runs the same test/lint/build tasks and retains APK and
verification reports for 14 days. GitHub workflow outcomes should be checked on
the draft PR; this record reports the completed local verification.

Follow [implementation and device checks](android-prototype.md) for installation,
the touch lab, a single calibrated game-menu action, interruption checks and the
physical-device acceptance table. All device rows remain NOT RUN. One verified
daily/reward sequence and one farming loop are subsequent implementation work.
