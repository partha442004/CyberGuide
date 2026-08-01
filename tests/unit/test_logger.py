"""Unit tests for utils/logger.py."""

import logging
from unittest.mock import MagicMock, patch


class TestSetupLogging:
    """Tests for setup_logging function."""

    @patch("interntrack.utils.logger.structlog")
    @patch("interntrack.utils.logger.logging")
    def test_setup_logging_default(self, mock_logging, mock_structlog):
        from interntrack.utils.logger import setup_logging

        setup_logging()

        mock_structlog.configure.assert_called_once()
        mock_logging.basicConfig.assert_called_once()

    @patch("interntrack.utils.logger.structlog")
    @patch("interntrack.utils.logger.logging")
    def test_setup_logging_debug(self, mock_logging, mock_structlog):
        from interntrack.utils.logger import setup_logging

        # Store the real DEBUG value before patching
        real_debug = logging.DEBUG
        mock_logging.DEBUG = real_debug

        setup_logging(debug=True)

        mock_structlog.configure.assert_called_once()
        mock_logging.basicConfig.assert_called_once()

        # Verify debug level
        call_kwargs = mock_logging.basicConfig.call_args
        assert call_kwargs[1]["level"] == real_debug


class TestGetLogger:
    """Tests for get_logger function."""

    @patch("interntrack.utils.logger.structlog")
    def test_get_logger(self, mock_structlog):
        from interntrack.utils.logger import get_logger

        mock_logger = MagicMock()
        mock_structlog.get_logger.return_value = mock_logger

        result = get_logger("test_module")

        mock_structlog.get_logger.assert_called_once_with("test_module")
        assert result == mock_logger
