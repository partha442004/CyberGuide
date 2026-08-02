"""
Unit tests for the route-listing helper (``src/cybershield/check_routes.py``).

The script executes at import time: it loads the FastAPI app, computes its
OpenAPI paths, and prints a summary. These tests exercise both the module
execution (via ``runpy``, capturing stdout) and the shared app it inspects.
"""

import runpy


class TestCheckRoutesScript:
    def test_module_runs_and_prints_path_summary(self, capsys):
        """Running the script prints the total API path count."""
        runpy.run_module("cybershield.check_routes", run_name="__main__")
        out = capsys.readouterr().out
        assert "Total API paths:" in out

    def test_module_reports_routes(self, capsys):
        """The printed paths include HTTP methods and route strings."""
        runpy.run_module("cybershield.check_routes", run_name="__main__")
        out = capsys.readouterr().out
        # Some /api/v1 route must be listed with its methods (OpenAPI method
        # keys are lowercase).
        assert "/api/v1" in out
        assert "get" in out or "post" in out

    def test_openapi_paths_are_nonempty(self):
        """The app exposes at least one API path (sanity check)."""
        from cybershield.main import app

        paths = app.openapi().get("paths", {})
        assert len(paths) > 0
