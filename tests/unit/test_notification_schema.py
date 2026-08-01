"""Tests for notification schema validation including priority normalizer."""

import pytest


class TestNotificationSendRequestSchema:
    """Tests for NotificationSendRequest schema validation."""

    def test_valid_request(self):
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(
            channel="email",
            title="Test",
            content="Hello",
        )
        assert req.channel == "email"
        assert req.priority == "medium"

    def test_default_values(self):
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(content="Hello")
        assert req.channel == "unknown"
        assert req.title == "CyberGuide Notification"
        assert req.priority == "medium"

    def test_priority_normalizer_normal_to_medium(self):
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(content="Hello", priority="normal")
        assert req.priority == "medium"

    def test_priority_normalizer_preserves_valid_values(self):
        from cybershield.schemas.notification import NotificationSendRequest

        for priority in ["low", "medium", "high", "urgent"]:
            req = NotificationSendRequest(content="Hello", priority=priority)
            assert req.priority == priority

    def test_invalid_channel_pattern(self):
        from pydantic import ValidationError
        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(channel="invalid_channel", content="Hello")

    def test_invalid_priority_pattern(self):
        from pydantic import ValidationError
        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(content="Hello", priority="super_urgent")

    def test_content_required(self):
        from pydantic import ValidationError
        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(channel="email")

    def test_content_max_length(self):
        from pydantic import ValidationError
        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(content="x" * 4097)

    def test_optional_data_field(self):
        from cybershield.schemas.notification import NotificationSendRequest

        req = NotificationSendRequest(
            content="Hello",
            data={"key": "value", "nested": {"a": 1}},
        )
        assert req.data == {"key": "value", "nested": {"a": 1}}

    def test_title_max_length(self):
        from pydantic import ValidationError
        from cybershield.schemas.notification import NotificationSendRequest

        with pytest.raises(ValidationError):
            NotificationSendRequest(content="Hello", title="x" * 201)
