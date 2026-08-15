"""
Tests for the dashboard admin-only access helpers.

The dashboard is admin-only: login requires the owner email, and (when
``DASHBOARD_PASSWORD`` is set) the whole app is locked behind a password.

The checks run in a fresh subprocess because other dashboard tests inject a
fake ``streamlit`` module into ``sys.modules``; importing the real
``dashboard.app`` in-process would collide with those fakes depending on
collection order.
"""

import os
import subprocess
import sys
from pathlib import Path

_REPO = str(Path(__file__).resolve().parents[2])

_SCRIPT = r"""
import os, sys

import dashboard.app as app

# Owner-email check (case-insensitive, empty owner never matches).
assert app._email_is_owner("Partha@X.com", "partha@x.com") is True
assert app._email_is_owner("member@x.com", "partha@x.com") is False
assert app._email_is_owner("partha@x.com", "") is False

# Password unset -> open (local dev keeps working).
assert app._dashboard_password() == ""
assert app._password_matches("anything") is True

# Password set -> constant-time gate.
os.environ["DASHBOARD_PASSWORD"] = "s3cret"
assert app._dashboard_password() == "s3cret"
assert app._password_matches("s3cret") is True
assert app._password_matches("wrong") is False
assert app._password_matches("") is False
del os.environ["DASHBOARD_PASSWORD"]

# Env var wins over st.secrets.
class _Secrets:
    def get(self, key, default=None):
        return {"DASHBOARD_PASSWORD": "from-secrets"}.get(key, default)

class _FakeSt:
    secrets = _Secrets()

_real_st = app.st
app.st = _FakeSt()  # type: ignore[assignment]
assert app._dashboard_password() == "from-secrets"
assert app._password_matches("from-secrets") is True
assert app._password_matches("wrong") is False
os.environ["DASHBOARD_PASSWORD"] = "env-wins"
assert app._dashboard_password() == "env-wins"
del os.environ["DASHBOARD_PASSWORD"]
assert app._dashboard_password() == "from-secrets"
app.st = _real_st  # type: ignore[assignment]

# Owner-email lookup against the API.
app.fetch_data = lambda path: {"email": "partha@x.com"}  # type: ignore[assignment]
assert app._is_owner_email("partha@x.com") is True
assert app._is_owner_email("member@x.com") is False
assert app._is_owner_email("") is False
assert app._is_owner_email(None) is False

print("DASHBOARD-SECURITY-OK")
"""


def _run_script() -> tuple[str, str, int]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(_REPO) / "src")
    proc = subprocess.run(  # noqa: S603 - trusted fixed args (venv python, static script)
        [sys.executable, "-c", _SCRIPT],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO,
        timeout=180,
    )
    return proc.stdout, proc.stderr, proc.returncode


def test_dashboard_access_helpers():
    out, err, rc = _run_script()
    assert rc == 0, f"subprocess failed ({rc}):\n{err}\n{out}"
    assert "DASHBOARD-SECURITY-OK" in out
