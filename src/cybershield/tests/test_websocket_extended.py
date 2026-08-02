"""
Unit Tests for WebSocket Manager (extended)

Covers the remaining branches of ``cybershield/notifications/websocket.py``:
- send_to_user failure cleanup
- WebSocketNotifier error paths (send / send_to_user)
- send_safe with to_dict objects and plain strings
"""

from unittest.mock import AsyncMock, patch

import pytest

from cybershield.notifications.websocket import (
    ConnectionManager,
    WebSocketNotifier,
    ws_manager,
)


class TestConnectionManagerConnect:
    """Tests for the ConnectionManager.connect method."""

    @pytest.mark.asyncio
    async def test_connect_accepts_and_registers(self):
        """Should accept the socket, assign an id, and store metadata."""
        manager = ConnectionManager()
        ws = AsyncMock()

        conn_id = await manager.connect(ws, "user-1")

        assert conn_id == 1
        ws.accept.assert_awaited_once()
        assert manager._connections["user-1"] == [ws]
        assert manager._metadata[conn_id]["user_id"] == "user-1"
        assert manager.total_connections == 1
        assert manager.connected_users == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_connections_same_user(self):
        """Should accumulate multiple connections for the same user."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1, "user-1")
        await manager.connect(ws2, "user-1")

        assert manager._connection_counter == 2
        assert len(manager._connections["user-1"]) == 2
        assert manager.connected_users == 1
        assert manager.total_connections == 2


class TestSendToUserFailureCleanup:
    """Tests for the failed-connection cleanup in send_to_user."""

    @pytest.mark.asyncio
    async def test_failed_websocket_is_cleaned_up(self):
        """Should drop websockets that raise on send_json and report 0 sends."""
        manager = ConnectionManager()
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = RuntimeError("disconnected")
        manager._connections["user-1"] = [good_ws, bad_ws]

        sent = await manager.send_to_user("user-1", {"msg": "hi"})

        assert sent == 1
        # bad connection should have been removed from the list
        assert manager._connections["user-1"] == [good_ws]
        bad_ws.send_json.assert_called_once()


class TestWebSocketNotifierErrorPaths:
    """Tests for WebSocketNotifier failure handling."""

    @pytest.mark.asyncio
    async def test_send_handles_broadcast_error(self):
        """Should record a failure and return False when broadcast raises."""
        notifier = WebSocketNotifier()
        with patch.object(ws_manager, "broadcast", side_effect=RuntimeError("boom")):
            result = await notifier.send({"title": "t"})
        assert result is False
        assert notifier._stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_send_to_user_success(self):
        """Should send to a specific user and record a success."""
        notifier = WebSocketNotifier()
        with patch.object(ws_manager, "send_to_user", return_value=1) as mock_send:
            result = await notifier.send_to_user("user-1", {"title": "t"})
        assert result is True
        mock_send.assert_awaited_once()
        assert notifier._stats["sent"] == 1

    @pytest.mark.asyncio
    async def test_send_to_user_error(self):
        """Should record a failure when targeted send raises."""
        notifier = WebSocketNotifier()
        with patch.object(ws_manager, "send_to_user", side_effect=RuntimeError("boom")):
            result = await notifier.send_to_user("user-1", {"title": "t"})
        assert result is False
        assert notifier._stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_send_safe_with_to_dict_object(self):
        """Should convert objects exposing to_dict before sending."""
        notifier = WebSocketNotifier()

        class FakeMessage:
            def to_dict(self):
                return {"title": "from object", "content": "body"}

        with patch.object(ws_manager, "broadcast", return_value=1) as mock_broadcast:
            result = await notifier.send_safe(FakeMessage())

        assert result is True
        payload = mock_broadcast.call_args.args[0]
        assert payload["title"] == "from object"
        assert payload["content"] == "body"

    @pytest.mark.asyncio
    async def test_send_safe_with_plain_string(self):
        """Should wrap plain strings into a message dict."""
        notifier = WebSocketNotifier()
        with patch.object(ws_manager, "broadcast", return_value=0) as mock_broadcast:
            result = await notifier.send_safe("just a message")

        assert result is False  # no receivers -> broadcast returns 0
        payload = mock_broadcast.call_args.args[0]
        assert payload["title"] == "just a message"
        assert payload["content"] == ""
