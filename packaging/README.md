# CyberGuide — Desktop & Mobile Packaging

This folder builds **desktop (Windows EXE)** and **mobile (Android APK)**
versions of the CyberGuide dashboard. Both are thin shells that load the
live dashboard — the EXE runs the Streamlit dashboard locally (pointing at
the live Vercel API), and the APK is a native WebView wrapper around the
deployed Streamlit Community Cloud app.

They need **no local database or backend** — all data, alerts, matches and
jobs come from the live API, exactly like the hosted dashboard.

## 📦 Windows EXE

### What you get

`dist/CyberGuide/CyberGuide.exe` — a self-contained desktop app that:

1. starts the dashboard on a free local port,
2. opens your default browser to it,
3. runs until you close it.

The dashboard reads `API_URL` from the environment and defaults to
`https://cyberguide-api.vercel.app/api/v1`.

### Building it yourself

```bash
# from the repo root, in any venv that has streamlit installed
python -m pip install pyinstaller
python -m PyInstaller packaging/windows/cyberguide.spec --noconfirm
```

Output: `dist/CyberGuide/CyberGuide.exe` (one-folder build).

**Single-file variant** (great for sharing — one `.exe` to send):

```bash
python -m PyInstaller packaging/windows/cyberguide_onefile.spec --noconfirm
```

Output: `dist/CyberGuide.exe` (~110 MB, self-extracting).

> **Note:** both specs bundle Streamlit's static assets and package metadata
> (both required or the frozen EXE crashes at import time), force
> `--global.developmentMode false` (frozen Streamlit would otherwise reject
> `--server.port`), and — because the dashboard `app.py` is bundled as a
> *data* file — explicitly pull in its imports (`httpx`, `plotly`, `pandas`,
> `numpy`) that static analysis can't see.

## 📱 Android APK

### What you get

`dist/CyberGuide-Android.apk` — a native Android app (WebView) that loads
`https://cyberguide2026aug.streamlit.app/`. Back/forward navigation, JS +
DOM storage enabled, cookies persisted, progress indicator. Package
`com.cyberguide.app`, minSdk 24 (Android 7.0+), signed with the debug key
so it installs directly.

`dist/CyberGuide-Android-release.apk` — the **Play-Store-ready release build**, signed
with the project keystore (`packaging/android/cyberguide-release.keystore`, alias
`cyberguide`, password `cyberguide123`). **Keep that keystore safe** — it is
`.gitignore`d; without it you cannot update the app on the same identity.

### Installing on a phone

1. Copy `dist/CyberGuide-Android.apk` to the phone (Google Drive / USB).
2. Tap it; allow "Install unknown apps" for your file manager.
3. Open **CyberGuide** — the dashboard loads (needs internet).

### Building it yourself

Requires: JDK 17, Android SDK (platform 34 + build-tools 34.0.0), Gradle 8.9.

```bash
export JAVA_HOME="C:\jdk-17.0.20+8"
cd packaging/android
# ensure local.properties points sdk.dir at your Android SDK
gradle assembleDebug
```

Output: `packaging/android/app/build/outputs/apk/debug/app-debug.apk`.

For a Play-Store-ready build, generate a signing key and use
`gradle assembleRelease` with the keystore configured (the repo ships
`keystore.properties` wiring for `packaging/android/cyberguide-release.keystore`).

## 🍎 iOS

Building a native iOS app requires **macOS + Xcode** (no Windows/iOS toolchain
here). Two ways to get CyberGuide on an iPhone:

### Option A — PWA (works today, no Mac)

`packaging/ios/PWA/` is a self-contained install page + web manifest + icons.
Host those files on any static host, then on the iPhone:

1. Open the page in **Safari**,
2. tap **Share → Add to Home Screen** — it installs as a full-screen app
   with the CyberGuide icon.

Generate the icons (any machine):

```bash
python -m pip install pillow
python packaging/ios/PWA/icons/generate_icons.py
```

### Option B — Xcode project

`packaging/ios/CyberGuide.xcodeproj` is a complete SwiftUI WebView wrapper
(bundle id `com.cyberguide.app`, iOS 15+, pull-to-refresh + back/forward
toolbar). On a Mac:

1. `open packaging/ios/CyberGuide.xcodeproj`
2. set your Apple Developer team under **Signing & Capabilities**,
3. run to your device or archive to the App Store.

## 🔁 Rebuilding after dashboard changes

- **EXE**: re-run the PyInstaller command above (dashboard `app.py` is
  bundled, so it reflects the latest dashboard code).
- **APK**: the APK loads the *deployed* dashboard — no rebuild needed for
  dashboard-only changes; only re-build if you change the wrapper itself
  (`MainActivity.java`, permissions, URL).
