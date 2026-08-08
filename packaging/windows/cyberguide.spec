# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CyberGuide desktop EXE.

Build (from repo root, in a venv with streamlit + pyinstaller):
    python -m PyInstaller packaging/windows/cyberguide.spec --noconfirm

Output: dist/CyberGuide/CyberGuide.exe (one-folder build — fastest startup).
"""

import os

import streamlit

# ---------------------------------------------------------------------------
# Locate the dashboard app + streamlit static assets.
# REPO_ROOT is resolved from the build CWD (run the build from the repo
# root) rather than SPECPATH, which can be flaky under `python -m
# PyInstaller <spec>`.
# ---------------------------------------------------------------------------
REPO_ROOT = os.getcwd()
DASH_DIR = os.path.join(REPO_ROOT, "dashboard")
LAUNCHER = os.path.join(REPO_ROOT, "packaging", "windows", "launcher.py")
STREAMLIT_DIR = os.path.dirname(streamlit.__file__)
STATIC_SRC = os.path.join(STREAMLIT_DIR, "static")

datas = [
    # The dashboard app itself.
    (os.path.join(DASH_DIR, "app.py"), "dashboard"),
    (os.path.join(DASH_DIR, "requirements.txt"), "dashboard"),
    # Streamlit's static front-end assets (JS/CSS bundled by pyinstaller
    # otherwise breaks the rendered UI).
    (STATIC_SRC, os.path.join("streamlit", "static")),
    # Include the invite helper module next to app.py.
    (os.path.join(DASH_DIR, "invite.py"), "dashboard"),
]

hiddenimports = [
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.server.websocket_headers",
    "streamlit.web.server.browser_websocket_handler",
    "streamlit.runtime.caching.storage.dummy_cache_storage",
    "streamlit.runtime.caching.storage.local_disk_cache_storage",
    "streamlit.runtime.media_file_storage",
    "streamlit.connections",
    "streamlit.connections.sql_connection",
    "streamlit.connections.base_connection",
    "streamlit.elements.arrow",
    "streamlit.elements.arrow_altair",
    "streamlit.elements.arrow_vega_lite",
    "streamlit.elements.image",
    "streamlit.elements.lib.policies",
    "streamlit.elements.lib.utils",
    "streamlit.elements.widgets.button",
    "streamlit.elements.widgets.selectbox",
    "streamlit.elements.widgets.multiselect",
    "streamlit.elements.widgets.slider",
    "streamlit.elements.widgets.text_widgets",
    "streamlit.elements.widgets.file_uploader",
    "streamlit.elements.widgets.data_editor",
    "streamlit.elements.widgets.time_widgets",
    "streamlit.elements.widgets.radio",
    "streamlit.elements.widgets.checkbox",
    "streamlit.elements.widgets.download_button",
    "streamlit.elements.widgets.link_button",
    "streamlit.elements.widgets.popover",
    "altair",
    "altair.vegalite.v5",
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "pandas",
    "numpy",
    "httpx",
    "dateutil",
    "toolz",
    "toolz.dicttoolz",
    "toolz.functoolz",
    "toolz.itertoolz",
    "blinker",
    "packaging",
    "pyarrow",
    "pyarrow.lib",
]

from PyInstaller.utils.hooks import copy_metadata

# streamlit (and friends) call ``importlib.metadata.version(...)`` at import
# time; without the package metadata the frozen EXE crashes with
# PackageNotFoundError. Copy the dist-info for the ones that matter.
a = Analysis(
    [LAUNCHER],
    pathex=[REPO_ROOT, os.path.join(REPO_ROOT, "src")],
    binaries=[],
    datas=datas
    + copy_metadata("streamlit")
    + copy_metadata("altair")
    + copy_metadata("plotly")
    + copy_metadata("pandas")
    + copy_metadata("numpy")
    + copy_metadata("httpx")
    + copy_metadata("blinker")
    + copy_metadata("packaging")
    + copy_metadata("pyarrow"),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "notebook",
        "jupyter",
        "pytest",
        "mypy",
        "ruff",
        "cybershield",
        "interntrack",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CyberGuide",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CyberGuide",
)
