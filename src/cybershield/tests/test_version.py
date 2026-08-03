"""
Unit tests for the cybershield package version consistency.
"""

import cybershield
from cybershield.config import Settings


class TestVersionConsistency:
    """Tests that the package and settings versions stay in sync."""

    def test_app_version_matches_package_version(self):
        """Settings.app_version must equal the package __version__."""
        assert Settings().app_version == cybershield.__version__

    def test_version_is_current_release(self):
        """The reported version matches the CHANGELOG's latest release.

        Canary: bump this string whenever a new CHANGELOG release is added so
        the version can never silently lag the documented release history.
        """
        assert cybershield.__version__ == "1.20.6"
