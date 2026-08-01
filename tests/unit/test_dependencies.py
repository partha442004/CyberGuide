"""Unit tests for dependencies.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetSettingsCached:
    """Tests for get_settings_cached function."""

    @patch("interntrack.dependencies.get_settings")
    def test_get_settings_cached_returns_settings(self, mock_get_settings):
        from interntrack.dependencies import get_settings_cached

        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings

        # Clear LRU cache
        get_settings_cached.cache_clear()

        result = get_settings_cached()

        assert result == mock_settings
        mock_get_settings.assert_called_once()

    @patch("interntrack.dependencies.get_settings")
    def test_get_settings_cached_caches_result(self, mock_get_settings):
        from interntrack.dependencies import get_settings_cached

        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings

        # Clear LRU cache
        get_settings_cached.cache_clear()

        # Call twice
        result1 = get_settings_cached()
        result2 = get_settings_cached()

        assert result1 == mock_settings
        assert result2 == mock_settings
        # get_settings should only be called once due to caching
        assert mock_get_settings.call_count == 1


class TestGetDB:
    """Tests for get_db dependency."""

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.get_db_session")
    async def test_get_db_yields_session(self, mock_get_db_session):
        from interntrack.dependencies import get_db

        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session

        # Test the generator
        gen = get_db()
        session = await gen.__anext__()

        assert session == mock_session


class TestServiceFactories:
    """Tests for service factory functions."""

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.get_db_session")
    @patch("interntrack.dependencies.JobService")
    async def test_get_job_service_with_db(self, mock_service_cls, mock_get_db):
        from interntrack.dependencies import get_job_service

        mock_db = AsyncMock()
        result = await get_job_service(db=mock_db)

        mock_service_cls.assert_called_once_with(mock_db)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.JobService")
    @patch("interntrack.dependencies.get_db_session")
    async def test_get_job_service_without_db(self, mock_get_db, mock_service_cls):
        from interntrack.dependencies import get_job_service

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await get_job_service()

        mock_service_cls.assert_called_once_with(mock_session)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.get_db_session")
    @patch("interntrack.dependencies.ApplicationService")
    async def test_get_application_service_with_db(self, mock_service_cls, mock_get_db):
        from interntrack.dependencies import get_application_service

        mock_db = AsyncMock()
        result = await get_application_service(db=mock_db)

        mock_service_cls.assert_called_once_with(mock_db)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.ApplicationService")
    @patch("interntrack.dependencies.get_db_session")
    async def test_get_application_service_without_db(
        self,
        mock_get_db,
        mock_service_cls,
    ):
        from interntrack.dependencies import get_application_service

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await get_application_service()

        mock_service_cls.assert_called_once_with(mock_session)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.get_db_session")
    @patch("interntrack.dependencies.NotificationManager")
    async def test_get_notification_manager_with_db(
        self,
        mock_service_cls,
        mock_get_db,
    ):
        from interntrack.dependencies import get_notification_manager

        mock_db = AsyncMock()
        result = await get_notification_manager(db=mock_db)

        mock_service_cls.assert_called_once_with(mock_db)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.NotificationManager")
    @patch("interntrack.dependencies.get_db_session")
    async def test_get_notification_manager_without_db(
        self,
        mock_get_db,
        mock_service_cls,
    ):
        from interntrack.dependencies import get_notification_manager

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await get_notification_manager()

        mock_service_cls.assert_called_once_with(mock_session)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.get_db_session")
    @patch("interntrack.dependencies.ReportService")
    async def test_get_report_service_with_db(self, mock_service_cls, mock_get_db):
        from interntrack.dependencies import get_report_service

        mock_db = AsyncMock()
        result = await get_report_service(db=mock_db)

        mock_service_cls.assert_called_once_with(mock_db)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.ReportService")
    @patch("interntrack.dependencies.get_db_session")
    async def test_get_report_service_without_db(self, mock_get_db, mock_service_cls):
        from interntrack.dependencies import get_report_service

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await get_report_service()

        mock_service_cls.assert_called_once_with(mock_session)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.get_db_session")
    @patch("interntrack.dependencies.AIService")
    async def test_get_ai_service_with_db(self, mock_service_cls, mock_get_db):
        from interntrack.dependencies import get_ai_service

        mock_db = AsyncMock()
        result = await get_ai_service(db=mock_db)

        mock_service_cls.assert_called_once_with(mock_db)
        assert result == mock_service_cls.return_value

    @pytest.mark.asyncio
    @patch("interntrack.dependencies.AIService")
    @patch("interntrack.dependencies.get_db_session")
    async def test_get_ai_service_without_db(self, mock_get_db, mock_service_cls):
        from interntrack.dependencies import get_ai_service

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await get_ai_service()

        mock_service_cls.assert_called_once_with(mock_session)
        assert result == mock_service_cls.return_value
