"""Version consistency checker for the CyberGuide monorepo.

Verifies that every source of truth for the release version agrees:

- ``src/interntrack/__init__.py``   (``__version__``)
- ``src/cybershield/__init__.py``   (``__version__``)
- ``.env.example``                  (``APP_VERSION``)
- ``pyproject.toml``                (``project.version``)

Exits non-zero (printing a per-source summary) whenever any source drifts,
so CI fails on the kind of silent version skew that historically crept in
(e.g. ``__version__`` lagging the CHANGELOG, or ``APP_VERSION`` stuck at an
old release). Wired into ``make version-check`` and the CI ``version`` job.

Usage:
    python scripts/check_versions.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_PACKAGE_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
_ENV_VERSION_RE = re.compile(r"^APP_VERSION\s*=\s*(.+)$", re.MULTILINE)
_PYPROJECT_VERSION_RE = re.compile(
    r"^version\s*=\s*[\"']([^\"']+)[\"']",
    re.MULTILINE,
)


def _read_source(path: Path) -> str:
    """Read a version source file, aborting with a clear message if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Missing version source: {path}") from None


def version_from_init(package: str) -> str:
    """Extract ``__version__`` from a package's ``__init__.py``."""
    path = ROOT / "src" / package / "__init__.py"
    match = _PACKAGE_VERSION_RE.search(_read_source(path))
    if not match:
        raise SystemExit(f"Could not parse __version__ from {path}")
    return match.group(1)


def version_from_env_example() -> str:
    """Extract ``APP_VERSION`` from ``.env.example``."""
    path = ROOT / ".env.example"
    match = _ENV_VERSION_RE.search(_read_source(path))
    if not match:
        raise SystemExit(f"Could not parse APP_VERSION from {path}")
    return match.group(1).strip()


def version_from_pyproject() -> str:
    """Extract ``project.version`` from the root ``pyproject.toml``."""
    path = ROOT / "pyproject.toml"
    match = _PYPROJECT_VERSION_RE.search(_read_source(path))
    if not match:
        raise SystemExit(f"Could not parse version from {path}")
    return match.group(1)


def sources() -> dict[str, str]:
    """Return a mapping of source name -> reported version."""
    return {
        "interntrack.__version__": version_from_init("interntrack"),
        "cybershield.__version__": version_from_init("cybershield"),
        ".env.example APP_VERSION": version_from_env_example(),
        "pyproject.toml version": version_from_pyproject(),
    }


def is_consistent(versions: dict[str, str]) -> bool:
    """True when every source reports the same version."""
    return len(set(versions.values())) == 1


def main() -> int:
    """Print the version summary and return 0 when consistent, else 1."""
    versions = sources()
    expected = versions["interntrack.__version__"]
    ok = True
    for name, value in versions.items():
        marker = "OK" if value == expected else "MISMATCH"
        if value != expected:
            ok = False
        print(f"  {name:<28} {value:<12} {marker}")
    if ok:
        print(f"\nAll version sources agree: {expected}")
        return 0
    print("\nERROR: version sources disagree - fix before releasing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
