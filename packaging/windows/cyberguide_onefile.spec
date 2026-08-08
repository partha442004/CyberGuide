# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file spec for the CyberGuide desktop dashboard.

Build:  python -m PyInstaller packaging/windows/cyberguide_onefile.spec --noconfirm
Output: dist/CyberGuide.exe  (single file, self-contained)
"""

from pathlib import Path

import PyInstaller.utils.hooks

project_root = Path(SPECPATH).resolve().parent.parent.parent if SPECPATH else Path.cwd()
if not (project_root / "dashboard").exists():
    project_root = Path.cwd()

datas = [
    (str(project_root / "dashboard" / "app.py"), "dashboard"),
]

# Bundle streamlit's static assets (JS/CSS served by the dashboard).
# collect_all returns a single (datas, binaries, hiddenimports) tuple.
from PyInstaller.utils.hooks import collect_all  # noqa: E402

_streamlit_datas, _streamlit_binaries, hiddenimports = collect_all("streamlit")
datas += list(_streamlit_datas)

# The dashboard (app.py) is bundled as a data file, so PyInstaller never
# statically sees its imports — declare them explicitly.
for _pkg in ("httpx", "plotly", "pandas", "numpy", "pytz"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += list(_d)
        hiddenimports += list(_h)
    except Exception:
        hiddenimports.append(_pkg)

# Package metadata so importlib.metadata can resolve streamlit's version.
from PyInstaller.utils.hooks import copy_metadata  # noqa: E402

datas += copy_metadata("streamlit")

a = Analysis(
    [str(project_root / "packaging" / "windows" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib.tests",
        "numpy.testing",
        "pytest",
        "PyInstaller",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CyberGuide",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "packaging" / "windows" / "cyberguide.ico")
    if (project_root / "packaging" / "windows" / "cyberguide.ico").exists()
    else None,
)
