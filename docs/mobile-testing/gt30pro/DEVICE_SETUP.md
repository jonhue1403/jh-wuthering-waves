# Device Setup Record — Infinix GT 30 Pro

**QA Coordinator:** Gemini 3.8 Flash (Lead Android QA Automation Engineer)  
**Date:** 2026-11-03  
**Target Device:** Infinix GT 30 Pro (`Infinix_X6873`)  
**Application:** JH WuWa Mobile Companion (`com.jh.wuwa.mobile` v0.1.0-prototype)  

---

## 1. Host Environment & Tool Versions

- **Host Operating System:** Microsoft Windows 11 Pro (Build 10.0.26200)
- **Host Terminal:** PowerShell 5.1 / UTF-8 Console
- **Package Manager / Environment Tool:** Astral `uv` 0.12.5
- **Python Execution Engine:** Python 3.12.14 (MobileRun environment via `uv tool`) & Python 3.13.15 (repository `.venv`)
- **Android Debug Bridge (ADB):** Version 1.0.41 (Google Platform-Tools 37.0.1-15733141)
- **MobileRun Framework:** `mobilerun` 0.7.4, `mobilerun-core-local` 0.7.1, `mobilerun-sdk` 6.0.1
- **MobileRun Portal APK:** Version 0.7.28 installed on device

---

## 2. Physical Device Identification

The physical test device was discovered over USB and verified through hardware and system properties:

- **ADB Serial Number:** `[REDACTED_SERIAL]` (Discovered dynamically at runtime)
- **Manufacturer:** `INFINIX`
- **Product Model:** `Infinix X6873` (Infinix GT 30 Pro)
- **Product Board / Hardware:** `X6873-OP`
- **Android OS Version:** Android 16 (API Level 36 / Preview/Baklava)
- **Build / Display ID:** `X6873-16.3.0.150SP09(OP006PF001AZ)`
- **XOS Flavor:** XOS 16.3
- **Display Resolution:** 1224 × 2720 pixels
- **Display Density:** 480 dpi
- **USB Device ID:** Discovered dynamically via ADB PnP enumeration

---

## 3. Installation & Configuration Steps

### 3.1 Platform-Tools (ADB) Installation
ADB was acquired directly from Google's official platform-tools repository:
```powershell
Invoke-WebRequest -Uri "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile "$env:TEMP\platform-tools.zip"
Expand-Archive -Path "$env:TEMP\platform-tools.zip" -DestinationPath "$env:LOCALAPPDATA\Android" -Force
[Environment]::SetEnvironmentVariable("Path", "$([Environment]::GetEnvironmentVariable('Path', 'User'));$env:LOCALAPPDATA\Android\platform-tools", "User")
```

### 3.2 MobileRun Local Framework Installation
Installed into an isolated Python 3.12 tool environment:
```powershell
uv tool install --python 3.12 mobilerun
```

### 3.3 MobileRun Portal Deployment
The Portal service APK (v0.7.28) was deployed to the GT 30 Pro:
```powershell
mobilerun setup
mobilerun ping
```
Result: `Portal is installed and accessible.`

### 3.4 Target Application Deployment
The signed debug prototype was downloaded from GitHub Actions Run `41485496391` on branch `feat/android-on-device-prototype` (PR #3) and installed:
```powershell
adb install -r android-artifact/app-debug.apk
```
Package details verified on device:
- Package: `com.jh.wuwa.mobile`
- Version Code: `1`
- Version Name: `0.1.0-prototype`
- Target SDK: `35` (Android 15), running on Android 16 runtime

---

## 4. Permission & Security Requirements

1. **USB Debugging:** Connected via high-speed USB data cable with developer options authorized.
2. **Mobilerun Accessibility Service:** `com.mobilerun.portal/.service.MobilerunAccessibilityService` enabled for non-intrusive automation.
3. **JH WuWa Accessibility Service:**
   - Component: `com.jh.wuwa.mobile/com.jh.wuwa.runtime.AutomationAccessibilityService`
   - Purpose: Dispatches user-approved input gestures bounded to the active application.
   - Setup: Enabled in `Settings -> Accessibility -> Downloaded apps -> JH WuWa touch control -> Use JH WuWa touch control -> Allow`.
   - OS Caveat: On Android 16, force-stopping the app (`am force-stop`) disables its accessibility binding; reopening the companion and re-enabling in Settings is required after forced terminations.
4. **MediaProjection Screen Capture:**
   - Foreground service type: `mediaProjection`.
   - Setup: User grants standard Android consent via the system dialogue (`Share your screen with JH WuWa Mobile? -> Share entire screen -> Share screen`).
