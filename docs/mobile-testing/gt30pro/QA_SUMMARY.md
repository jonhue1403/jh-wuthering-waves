# QA Summary & Physical Readiness Assessment — Infinix GT 30 Pro

**Evaluation Date:** 2026-11-03  
**QA Coordinator:** Lead Android QA Automation Engineer  
**Target Device:** Physical Infinix GT 30 Pro (`Infinix_X6873`, Android 16, XOS 16.3, 1224×2720 @ 480dpi)  
**Prototype Evaluated:** `com.jh.wuwa.mobile` (v0.1.0-prototype, PR #3)  

---

## 1. Overall Physical Verification Verdict

**VERDICT: ON-DEVICE FEASIBILITY VALIDATED ON PHYSICAL HARDWARE (CRITICAL GATE PASSED).**

Following the mandatory QA reconciliation and revalidation protocol, the critical on-device automation chain has passed on the physical **Infinix GT 30 Pro** across **three consecutive, uninterrupted runs** with zero contradictory observations.

### Revalidation Summary:
- **Total Tests Evaluated:** 51
- **Physical Pass (Hardware Asserted):** 28
- **Static Review (Architecture & Invariant Audited):** 21
- **Blocked (Live Gameplay & Account Scope):** 2
- **Failures / Contradictions:** 0
- **Integrity Status:** Audited and verified by `android/qa/validate_assertions.py` (`assertion_consistency_report.json`).

The critical gate defined in PR #3 — requiring physical-device proof before considering the architecture viable — has been satisfied with empirical observations.

---

## 2. What Is Verified on Hardware (The Critical Chain)

Across 3 consecutive validation cycles on the physical Infinix GT 30 Pro:
1. **Accessibility Service Touch Injection:**
   - Single tap (`C02`): Canvas target tap registered cleanly; target taps counter incremented from baseline 0 $\to$ 1 in every run.
   - Directional swipe (`C03`): Continuous movement stroke registered 29, 30, and 30 movement events across runs.
   - Simultaneous multi-touch (`C04`): Concurrent two-finger gesture registered `max_fingers = 2` simultaneously in all runs.
2. **MediaProjection Screen Capture & Frame Pipeline:**
   - Active foreground capture verified running with `types=0x00000020` (mediaProjection).
   - Live frames delivered continuously to `SessionController` (advancing by 202, 221, and 219 frames per session).
   - Clean lifecycle teardown upon user Stop action; fresh restart correctly prompts Android MediaProjection system consent and cleanly resumes capture (`B05`, `B07`).
3. **On-Device Visual Recognition (`TemplateMatcher`):**
   - Live 6×6 high-contrast checkerboard target calibrated on device.
   - Three sequential visual tap cycles completed with strict enforcement of target disappearance (1000ms absent window) and reappearance (`C05`, `C06`): target taps counter incremented from 2 $\to$ 5 (exactly $+3$ visual hits) in every run.
4. **Runtime Resource Bounds (`F01`):**
   - Memory footprint is remarkably lightweight: **83.2 MB average PSS** (83.8 MB peak), well under the 250 MB ceiling.
   - Zero fatal crashes or ANRs across repeated launch and capture cycles.
   - Steady device thermals (34.3 °C).
5. **Security & Privacy Boundaries:**
   - Zero internet or network permissions declared or used.
   - Exported diagnostics contain only timestamps and event counters; zero screenshots, personal identifiers, or game credentials exist in memory or export.

---

## 3. What Remains Unverified and Blocked

1. **Active Wuthering Waves Gameplay Automation (Tests H01, H02):**
   - The official game package `com.kurogame.wutheringwaves.global` (v3.7.1) was confirmed installed on the GT 30 Pro, and package alignment was verified (`G01`, `G02`).
   - However, **in-game combat loops, daily farming routines, and overworld navigation remain unverified and blocked**. In accordance with the v0.1.0 prototype scope and non-destructive testing policy, live game state manipulation was not attempted.
2. **Prolonged Multi-Hour Background Capture:**
   - The 30-second benchmark proves short-term memory and thermal stability. Long-duration sessions (e.g. 2–4 hours of continuous capture while the phone runs heavy 3D GPU gaming load) were not benchmarked.
3. **Formal End-to-End Latency:**
   - Frame delivery is smooth and uninterrupted, but claims of $<50\text{ms}$ latency remain an unmeasured engineering estimate until verified with specialized high-speed optical capture hardware.
4. **Android 16 Accessibility Unbinding Caveat:**
   - Force-stopping the app or swipe-killing it from Android Recents causes Android 16 to unbind the accessibility service. Users must manually re-enable it in Android Settings after a force-stop.

---

## 4. Release Decision Regarding PR #3

**PR #3 Status: MUST REMAIN IN DRAFT (DO NOT MERGE).**

Although the physical feasibility gate is validated:
1. PR #3 represents an exploratory architectural prototype (`0.1.0-prototype`).
2. Live in-game interactions (`H01`, `H02`) and multi-hour endurance testing have not yet been evaluated.
3. The accessibility service unbinding caveat on Android 16 requires documentation and a UI warning before public release.
4. The draft PR status preserves testing agility while maintaining production branch hygiene.

---

## 5. Next Recommended Engineering Milestones

1. **Phase 2 In-Game Safe Menu Probe:**
   Develop a non-destructive in-game probe (e.g., verifying template detection on the game's Bag or Character menu icon) with explicit user approval.
2. **Accessibility Unbinding Detection:**
   Implement a lightweight check in `MainActivity` to detect when `AutomationAccessibilityService` has been disconnected by an OS kill, providing an immediate one-tap deep link to Android's accessibility toggle.
3. **Floating Overlay Bubble (Optional):**
   Introduce an optional floating UI bubble so users can start and stop automation without switching away from the active game.
