"""
Tests for Notification API Endpoints

Tests for the /test and /send notification API endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.notifications.base import NotificationPriority
from cybershield.notifications.orchestrator import NotificationOrchestrator


class TestNotificationEndpoints:
    """Tests for notification API endpoints."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock notification orchestrator."""
        orch = NotificationOrchestrator()
        return orch

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_test_notification_channel_not_configured(self, mock_session):
        """Test /test endpoint returns 400 when channel is not configured."""
        from cybershield.api.v1.notifications import test_notification
        from cybershield.schemas.notification import NotificationTest

        test_data = NotificationTest(channel="telegram", message="Test message")

        with patch(
            "cybershield.api.v1.notifications.get_notification_orchestrator"
        ) as mock_get_orch:
            mock_get_orch.return_value = NotificationOrchestrator()
            with pytest.raises(Exception) as exc_info:
                await test_notification(test_data, mock_session)
            assert "not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_test_notification_success(self, mock_session):
        """Test /test endpoint sends successfully when channel is configured."""
        from cybershield.api.v1.notifications import test_notification
        from cybershield.notifications.email import EmailNotifier
        from cybershield.schemas.notification import NotificationTest

        test_data = NotificationTest(channel="email", message="Test message")

        orch = NotificationOrchestrator()
        mock_notifier = MagicMock(spec=EmailNotifier)
        mock_notifier.enabled = True
        mock_notifier.send_safe = AsyncMock(return_value=True)
        orch.register("email", mock_notifier)

        with patch(
            "cybershield.api.v1.notifications.get_notification_orchestrator"
        ) as mock_get_orch:
            mock_get_orch.return_value = orch
            result = await test_notification(test_data, mock_session)

            assert result["success"] is True
            assert result["channel"] == "email"
            assert result["sent_at"] is not None

    @pytest.mark.asyncio
    async def test_send_notification_to_specific_channel(self, mock_session):
        """Test /send endpoint sends to a specific channel."""
        from cybershield.api.v1.notifications import send_notification
        from cybershield.schemas.notification import NotificationSendRequest

        request = NotificationSendRequest(
            channel="email",
            title="Test Alert",
            content="This is a test notification",
        )

        orch = NotificationOrchestrator()
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_notifier.send_safe = AsyncMock(return_value=True)
        orch.register("email", mock_notifier)

        with patch(
            "cybershield.api.v1.notifications.get_notification_orchestrator"
        ) as mock_get_orch:
            mock_get_orch.return_value = orch
            result = await send_notification(request, mock_session)

            assert result["success"] is True
            assert result["channel"] == "email"

    @pytest.mark.asyncio
    async def test_send_notification_to_all_channels(self, mock_session):
        """Test /send endpoint sends to all channels when channel is 'unknown'."""
        from cybershield.api.v1.notifications import send_notification
        from cybershield.schemas.notification import NotificationSendRequest

        request = NotificationSendRequest(
            channel="unknown",
            title="Broadcast",
            content="Hello everyone",
        )

        orch = NotificationOrchestrator()
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_notifier.send_safe = AsyncMock(return_value=True)
        orch.register("email", mock_notifier)
        orch.register("slack", mock_notifier)

        with patch(
            "cybershield.api.v1.notifications.get_notification_orchestrator"
        ) as mock_get_orch:
            mock_get_orch.return_value = orch
            result = await send_notification(request, mock_session)

            assert result["success"] is True
            assert result["channel"] == "unknown"

    @pytest.mark.asyncio
    async def test_send_notification_with_priority(self, mock_session):
        """Test /send endpoint respects priority field."""
        from cybershield.api.v1.notifications import send_notification
        from cybershield.schemas.notification import NotificationSendRequest

        request = NotificationSendRequest(
            channel="email",
            title="Urgent Alert",
            content="Critical issue",
            priority="urgent",
        )

        orch = NotificationOrchestrator()
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_notifier.send_safe = AsyncMock(return_value=True)
        orch.register("email", mock_notifier)

        with patch(
            "cybershield.api.v1.notifications.get_notification_orchestrator"
        ) as mock_get_orch:
            mock_get_orch.return_value = orch
            result = await send_notification(request, mock_session)

            assert result["success"] is True
            # Verify the message was sent with the orchestrator
            mock_notifier.send_safe.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_failure(self, mock_session):
        """Test /send endpoint handles send failure gracefully."""
        from cybershield.api.v1.notifications import send_notification
        from cybershield.schemas.notification import NotificationSendRequest

        request = NotificationSendRequest(
            channel="email",
            title="Test",
            content="Will fail",
        )

        orch = NotificationOrchestrator()
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_notifier.send_safe = AsyncMock(return_value=False)
        orch.register("email", mock_notifier)

        with patch(
            "cybershield.api.v1.notifications.get_notification_orchestrator"
        ) as mock_get_orch:
            mock_get_orch.return_value = orch
            result = await send_notification(request, mock_session)

            assert result["success"] is False
            assert "Failed" in result["message"]


class TestNotificationSendRequestSchema:
    """Tests for NotificationSendRequest schema validation."""

    def test_valid_request(self):
        """Test creating a valid notification request."""
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(
            channel="email",
            title="Test",
            content="Hello",
        )
        assert req.channel == "email"
        assert req.priority == "medium"

    def test_default_values(self):
        """Test default values for optional fields."""
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(content="Hello")
        assert req.channel == "unknown"
        assert req.title == "CyberGuide Notification"
        assert req.priority == "medium"

    def test_invalid_channel_pattern(self):
        """Test that invalid channel name is rejected."""
        from pydantic import ValidationError

        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(channel="invalid_channel", content="Hello")

    def test_invalid_priority_pattern(self):
        """Test that invalid priority is rejected."""
        from pydantic import ValidationError

        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(content="Hello", priority="super_urgent")

    def test_content_required(self):
        """Test that content field is required."""
        from pydantic import ValidationError

        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(channel="email")

    def test_content_max_length(self):
        """Test that content field respects max length."""
        from pydantic import ValidationError

        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(content="x" * 4097)

    def test_optional_data_field(self):
        """Test that data field accepts dict."""
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(
            content="Hello",
            data={"key": "value", "nested": {"a": 1}},
        )
        assert req.data == {"key": "value", "nested": {"a": 1}}
