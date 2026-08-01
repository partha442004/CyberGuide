"""Live smoke test for the InternTrack API.

Boots the real uvicorn server against a temporary SQLite database on an
ephemeral port, then verifies over HTTP that the deployed surface behaves
correctly:

- ``GET /``        -> 200 app info
- ``GET /health``  -> 200 ``status: healthy`` and ``version`` == package
  ``__version__`` (single source of truth)
- ``GET /metrics`` -> 200 with the snapshot shape
- ``GET /metrics/prometheus`` -> 200 text/plain with the ``# HELP``
  exposition header
- CORS preflight  -> 200 with ``access-control-allow-origin``
- Rate limiting   -> burst yields ``200``s then ``429`` with the
  ``RATE_LIMITED`` error contract
- Unknown route   -> 404

Exits non-zero on any failure. Wired into ``make smoke`` and the CI
``smoke`` job so a booted server can never silently drift from the code.

Usage:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _free_port() -> int:
    """Pick an ephemeral port that is currently free."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_ready(base_url: str, timeout: float = 30.0) -> bool:
    """Poll /health until the server responds or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with suppress(Exception):
            response = httpx.get(f"{base_url}/health", timeout=2)
            if response.status_code < 500:
                return True
        time.sleep(0.5)
    return False


def _check(description: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {description}" + (f" - {detail}" if detail else ""))
    if not condition:
        raise SystemExit(f"Smoke test failed: {description}")


def main() -> int:
    """Run the smoke test suite and return a process exit code."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_fd, db_path = tempfile.mkstemp(prefix="smoke_", suffix=".db")
    os.close(db_fd)
    # Log to the OS temp dir so a fresh checkout (no data/) isn't mutated;
    # the log is removed in the finally block below. mkstemp returns a str,
    # so wrap it in Path for the .open()/.unlink() calls below.
    log_fd, log_path = tempfile.mkstemp(prefix="smoke_", suffix=".log")
    os.close(log_fd)
    log_path = Path(log_path)

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": "src",
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_PER_MINUTE": "3",
            # Force the in-memory rate-limit store so the burst is deterministic
            # even on a machine with a local Redis running.
            "REDIS_URL": "",
            "API_PORT": str(port),
        },
    )

    # The command is a fixed interpreter + module name, never user input, so
    # ruff's subprocess warning (S603) does not apply here.
    server = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "uvicorn", "interntrack.main:app", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=log_path.open("w"),
        stderr=subprocess.STDOUT,
    )

    try:
        if not _wait_until_ready(base_url):
            print("Server failed to start within timeout; log tail:")
            print("\n".join(log_path.read_text().splitlines()[-20:]))
            return 1

        with httpx.Client(base_url=base_url, timeout=10) as client:
            response = client.get("/")
            _check("GET / returns 200", response.status_code == 200)

            response = client.get("/health")
            _check("GET /health returns 200", response.status_code == 200)
            payload = response.json()
            import interntrack

            reported = payload.get("version")
            _check(
                "health version == package __version__",
                reported == interntrack.__version__,
                f"reported {reported}, expected {interntrack.__version__}",
            )
            _check("health status == healthy", payload.get("status") == "healthy")

            response = client.get("/metrics")
            _check("GET /metrics returns 200", response.status_code == 200)
            metrics = response.json()
            for key in (
                "total_requests",
                "error_rate",
                "avg_latency_ms",
                "status_codes",
            ):
                _check(f"metrics contains {key}", key in metrics)

            response = client.get("/metrics/prometheus")
            _check("GET /metrics/prometheus returns 200", response.status_code == 200)
            _check(
                "prometheus content-type is text/plain",
                response.headers.get("content-type", "").startswith("text/plain"),
            )
            _check(
                "prometheus body has HELP header",
                "# HELP interntrack_http_requests_total" in response.text,
            )

            response = client.options(
                "/api/v1/jobs/",
                headers={
                    "Origin": "http://localhost:8501",
                    "Access-Control-Request-Method": "GET",
                },
            )
            _check("CORS preflight returns 200", response.status_code == 200)
            _check(
                "CORS allows origin",
                response.headers.get("access-control-allow-origin") == "*",
            )

            # Unknown route -> 404 (checked before the rate-limit burst so the
            # exhausted limit can't mask a missing route with a 429). The 404
            # consumes one of the 3 per-minute credits, so with limit=3 the
            # burst that follows allows exactly 2 requests before throttling.
            response = client.get("/definitely-not-a-route")
            _check(
                "unknown route returns 404",
                response.status_code == 404,
            )

            codes = []
            for _ in range(5):
                codes.append(client.get("/api/v1/jobs/").status_code)
            _check(
                "rate limit burst 200,200,429,429,429",
                codes == [200, 200, 429, 429, 429],
                f"got {codes}",
            )
            blocked = client.get("/api/v1/jobs/")
            _check(
                "429 uses RATE_LIMITED contract",
                blocked.status_code == 429
                and blocked.json().get("error", {}).get("code") == "RATE_LIMITED",
            )

        print("\nAll smoke checks passed.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        Path(db_path).unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
