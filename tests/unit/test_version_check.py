"""
Unit tests for the monorepo version consistency checker
(``scripts/check_versions.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts"

sys.path.insert(0, str(SCRIPT_DIR))

import check_versions  # noqa: E402


class TestVersionSources:
    """Tests that every version source parses and agrees."""

    def test_all_sources_report_same_version(self):
        """interntrack, cybershield, .env.example, and pyproject must agree."""
        versions = check_versions.sources()
        assert len(versions) == 4
        assert check_versions.is_consistent(versions), versions

    def test_sources_are_current_release(self):
        """The agreed version must match the CHANGELOG's latest release.

        Canary: bump this string whenever a new CHANGELOG release is added.
        """
        assert check_versions.is_consistent(check_versions.sources())
        assert check_versions.sources()["interntrack.__version__"] == "1.15.0"

    def test_version_from_init_parses(self):
        """Both package __init__.py files expose a parseable __version__."""
        assert check_versions.version_from_init("interntrack") == "1.15.0"
        assert check_versions.version_from_init("cybershield") == "1.15.0"

    def test_version_from_env_example_parses(self):
        """.env.example exposes a parseable APP_VERSION."""
        assert check_versions.version_from_env_example() == "1.15.0"

    def test_version_from_pyproject_parses(self):
        """Root pyproject.toml exposes a parseable project.version."""
        assert check_versions.version_from_pyproject() == "1.15.0"


class TestConsistencyDetection:
    """Tests that the checker detects drift between sources."""

    def test_is_consistent_true_when_all_match(self):
        assert check_versions.is_consistent(
            {
                "a": "1.15.0",
                "b": "1.15.0",
                "c": "1.15.0",
            },
        )

    def test_is_consistent_false_on_any_mismatch(self):
        assert not check_versions.is_consistent(
            {
                "a": "1.15.0",
                "b": "1.9.0",
                "c": "1.15.0",
            },
        )

    def test_main_exits_zero_when_consistent(self):
        """main() returns 0 when all sources agree (real repo state)."""
        with mock.patch.object(check_versions, "sources") as mock_sources:
            mock_sources.return_value = {
                "interntrack.__version__": "1.15.0",
                "cybershield.__version__": "1.15.0",
                ".env.example APP_VERSION": "1.15.0",
                "pyproject.toml version": "1.15.0",
            }
            assert check_versions.main() == 0

    def test_main_exits_nonzero_on_mismatch(self):
        """main() returns 1 when any source disagrees."""
        with mock.patch.object(check_versions, "sources") as mock_sources:
            mock_sources.return_value = {
                "interntrack.__version__": "1.15.0",
                "cybershield.__version__": "1.15.0",
                ".env.example APP_VERSION": "1.9.0",
                "pyproject.toml version": "1.15.0",
            }
            assert check_versions.main() == 1

    def test_missing_source_raises_systemexit(self, tmp_path):
        """A source file missing __version__ aborts with SystemExit."""
        with (
            mock.patch.object(check_versions, "ROOT", tmp_path),
            pytest.raises(SystemExit),
        ):
            check_versions.version_from_init("interntrack")
