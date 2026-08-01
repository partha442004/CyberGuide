"""Unit tests for scripts/export_jobs.py."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.domain.enums import ExperienceLevel, JobSource, JobType
from interntrack.domain.models import Job


def _make_job(**overrides) -> Job:
    """Create a Job instance with sensible defaults."""
    defaults = dict(
        id="job-1",
        title="Python Developer",
        company="TechCorp",
        url="https://example.com/job/1",
        source=JobSource.LINKEDIN,
        job_type=JobType.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        location="Remote",
        description="Build APIs",
        salary_min=80000,
        salary_max=120000,
        salary_currency="USD",
        is_remote=True,
        is_active=True,
        posted_at=datetime(2026, 1, 15, tzinfo=UTC),
        expires_at=None,
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
        updated_at=datetime(2026, 1, 10, tzinfo=UTC),
        tags=["python", "fastapi"],
    )
    defaults.update(overrides)
    return Job(**defaults)


class TestExportJobs:
    """Tests for the async export_jobs function."""

    @pytest.mark.asyncio
    async def test_export_csv_success(self, tmp_path):
        """Test CSV export with jobs found."""
        job = _make_job(id="j1")
        output = str(tmp_path / "out.csv")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.export_jobs.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.export_jobs.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.export_jobs import export_jobs

            result = await export_jobs(output_file=output, format="csv")

        assert result == output
        assert Path(output).exists()

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["title"] == "Python Developer"

    @pytest.mark.asyncio
    async def test_export_json_success(self, tmp_path):
        """Test JSON export with jobs found."""
        job = _make_job(id="j2")
        output = str(tmp_path / "out.json")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.export_jobs.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.export_jobs.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.export_jobs import export_jobs

            result = await export_jobs(output_file=output, format="json")

        assert result == output
        assert Path(output).exists()

        with open(output) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["title"] == "Python Developer"

    @pytest.mark.asyncio
    async def test_export_no_jobs(self):
        """Test export returns empty string when no jobs found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.export_jobs.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.export_jobs.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.export_jobs import export_jobs

            result = await export_jobs(format="csv")

        assert result == ""

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, tmp_path):
        """Test export returns empty string for unsupported format."""
        job = _make_job()
        output = str(tmp_path / "out.xml")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.export_jobs.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.export_jobs.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.export_jobs import export_jobs

            result = await export_jobs(output_file=output, format="xml")

        assert result == ""

    @pytest.mark.asyncio
    async def test_export_with_source_filter(self, tmp_path):
        """Test export filters by source."""
        job = _make_job(id="j3")
        output = str(tmp_path / "out.csv")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.export_jobs.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.export_jobs.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.export_jobs import export_jobs

            result = await export_jobs(
                output_file=output, format="csv", source="linkedin"
            )

        assert result == output

    @pytest.mark.asyncio
    async def test_export_with_limit(self, tmp_path):
        """Test export respects limit parameter."""
        job = _make_job(id="j4")
        output = str(tmp_path / "out.csv")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.export_jobs.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.export_jobs.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.export_jobs import export_jobs

            result = await export_jobs(output_file=output, format="csv", limit=5)

        assert result == output


class TestExportCSV:
    """Tests for _export_csv helper function."""

    def test_csv_export_basic(self, tmp_path):
        """Test CSV export writes correct headers and rows."""
        job = _make_job(
            posted_at=None,
            expires_at=None,
            created_at=None,
            updated_at=None,
        )
        output = tmp_path / "test.csv"

        from interntrack.scripts.export_jobs import _export_csv

        _export_csv([job], output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["title"] == "Python Developer"
        assert rows[0]["company"] == "TechCorp"
        assert rows[0]["is_remote"] == "True"

    def test_csv_export_empty_optional_fields(self, tmp_path):
        """Test CSV export handles None optional fields."""
        job = _make_job(
            location=None,
            description=None,
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            posted_at=None,
            expires_at=None,
            created_at=None,
            updated_at=None,
        )
        output = tmp_path / "test.csv"

        from interntrack.scripts.export_jobs import _export_csv

        _export_csv([job], output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["location"] == ""
        assert rows[0]["description"] == ""
        assert rows[0]["salary_min"] == ""
        assert rows[0]["salary_max"] == ""
        assert rows[0]["salary_currency"] == "USD"

    def test_csv_export_empty_tags(self, tmp_path):
        """Test CSV export handles empty tags."""
        job = _make_job(tags=[])
        output = tmp_path / "test.csv"

        from interntrack.scripts.export_jobs import _export_csv

        _export_csv([job], output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["tags"] == ""


class TestExportJSON:
    """Tests for _export_json helper function."""

    def test_json_export_basic(self, tmp_path):
        """Test JSON export writes correct structure."""
        job = _make_job(
            posted_at=None,
            expires_at=None,
            created_at=None,
            updated_at=None,
        )
        output = tmp_path / "test.json"

        from interntrack.scripts.export_jobs import _export_json

        _export_json([job], output)

        with open(output) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["title"] == "Python Developer"
        assert data[0]["company"] == "TechCorp"
        assert data[0]["source"] == "linkedin"

    def test_json_export_none_fields(self, tmp_path):
        """Test JSON export preserves None values for optional fields."""
        job = _make_job(
            location=None,
            description=None,
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            posted_at=None,
            expires_at=None,
            created_at=None,
            updated_at=None,
        )
        output = tmp_path / "test.json"

        from interntrack.scripts.export_jobs import _export_json

        _export_json([job], output)

        with open(output) as f:
            data = json.load(f)

        assert data[0]["location"] is None
        assert data[0]["description"] is None
        assert data[0]["salary_min"] is None
        assert data[0]["posted_at"] is None

    def test_json_export_empty_tags(self, tmp_path):
        """Test JSON export handles empty tags."""
        job = _make_job(tags=[])
        output = tmp_path / "test.json"

        from interntrack.scripts.export_jobs import _export_json

        _export_json([job], output)

        with open(output) as f:
            data = json.load(f)

        assert data[0]["tags"] == []


class TestExportMain:
    """Tests for the CLI main() entry point."""

    def test_main_defaults(self):
        """Test main() with default arguments."""
        mock_export = AsyncMock(return_value="jobs_export.csv")
        with (
            patch("sys.argv", ["export_jobs"]),
            patch("interntrack.scripts.export_jobs.export_jobs", mock_export),
            patch("asyncio.run") as mock_run,
        ):
            mock_run.side_effect = lambda coro: None
            from interntrack.scripts.export_jobs import main

            main()
            mock_run.assert_called_once()

    def test_main_custom_args(self):
        """Test main() with custom arguments."""
        mock_export = AsyncMock(return_value="custom.csv")
        with (
            patch(
                "sys.argv",
                ["export_jobs", "-o", "custom.csv", "-f", "json", "-l", "5", "-s", "linkedin"],
            ),
            patch("interntrack.scripts.export_jobs.export_jobs", mock_export),
            patch("asyncio.run") as mock_run,
        ):
            mock_run.side_effect = lambda coro: None
            from interntrack.scripts.export_jobs import main

            main()
            mock_run.assert_called_once()
