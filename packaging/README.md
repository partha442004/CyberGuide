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

> **Note:** the spec bundles Streamlit's static assets and package metadata
> (both required or the frozen EXE crashes at import time), forces
> `--global.developmentMode false` (frozen Streamlit would otherwise reject
> `--server.port`), and excludes the backend packages entirely.

## 📱 Android APK

### What you get

`dist/CyberGuide-Android.apk` — a native Android app (WebView) that loads
`https://cyberguide2026aug.streamlit.app/`. Back/forward navigation, JS +
DOM storage enabled, cookies persisted, progress indicator. Package
`com.cyberguide.app`, minSdk 24 (Android 7.0+), signed with the debug key
so it installs directly.

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
`gradle assembleRelease` with the keystore configured.

## 🔁 Rebuilding after dashboard changes

- **EXE**: re-run the PyInstaller command above (dashboard `app.py` is
  bundled, so it reflects the latest dashboard code).
- **APK**: the APK loads the *deployed* dashboard — no rebuild needed for
  dashboard-only changes; only re-build if you change the wrapper itself
  (`MainActivity.java`, permissions, URL).
