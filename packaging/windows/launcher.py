"""CyberGuide Desktop — Windows launcher.

Bundles the Streamlit dashboard into a single desktop EXE. On launch it:

1. Starts the dashboard on a local port (Streamlit server),
2. Opens the default browser to it,
3. Runs until the user closes the window.

The dashboard reads ``API_URL`` from the environment and defaults to the
live Vercel API, so the desktop app works out of the box with no local
backend — the same data, alerts and matches as the hosted app.
"""

import os
import socket
import sys
import threading
import time
import webbrowser

API_URL = os.environ.get("API_URL", "https://cyberguide-api.vercel.app/api/v1")
HEALTH_URL = os.environ.get("HEALTH_URL", "https://cyberguide-api.vercel.app/health")


def _free_port() -> int:
    """Ask the OS for an ephemeral free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _open_browser_later(url: str, delay: float = 4.0) -> None:
    """Open the dashboard in the default browser shortly after boot."""

    def _open() -> None:
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def main() -> int:
    port = _free_port()
    url = f"http://localhost:{port}"

    # Point the bundled dashboard at the live API (overridable via env).
    os.environ["API_URL"] = API_URL
    os.environ["HEALTH_URL"] = HEALTH_URL

    # Determine the dashboard path. PyInstaller puts bundled files in
    # sys._MEIPASS; a plain python run uses the repo layout.
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        dash_dir = os.path.join(bundle_root, "dashboard")
    else:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dash_dir = os.path.join(repo_root, "dashboard")
    app_path = os.path.join(dash_dir, "app.py")

    # Streamlit refuses to run when it detects it's the frozen interpreter,
    # so we must patch sys.argv BEFORE importing streamlit.web.cli.
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        # Frozen streamlit auto-enables global.developmentMode, which then
        # rejects --server.port; force it off so the local port works.
        "--global.developmentMode",
        "false",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--browser.gatherUsageStats",
        "false",
    ]
    _open_browser_later(url)

    from streamlit.web import cli as stcli

    return stcli.main()


if __name__ == "__main__":
    sys.exit(main())
