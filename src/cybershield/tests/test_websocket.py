"""
Unit Tests for WebSocket Manager and Notifier

Tests the ConnectionManager and WebSocketNotifier classes covering:
- Connection lifecycle
- User-based messaging
- Room management
- Broadcasting
- Statistics
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cybershield.notifications.websocket import ConnectionManager, WebSocketNotifier, ws_manager


class TestConnectionManager:
    """Test ConnectionManager functionality."""

    def setup_method(self):
        self.manager = ConnectionManager()

    def test_initial_state(self):
        """Should start with zero connections."""
        assert self.manager.total_connections == 0
        assert self.manager.connected_users == 0

    def test_stats_empty(self):
        """Should return correct stats when empty."""
        stats = self.manager.get_stats()
        assert stats["total_connections"] == 0
        assert stats["connected_users"] == 0
        assert stats["rooms"] == {}

    def test_join_room(self):
        """Should add user to room."""
        self.manager.join_room("user1", "job_alerts")
        assert "user1" in self.manager._rooms["job_alerts"]

    def test_leave_room(self):
        """Should remove user from room."""
        self.manager.join_room("user1", "job_alerts")
        self.manager.leave_room("user1", "job_alerts")
        assert "job_alerts" not in self.manager._rooms

    def test_get_user_rooms(self):
        """Should return rooms for a user."""
        self.manager.join_room("user1", "room_a")
        self.manager.join_room("user1", "room_b")
        rooms = self.manager.get_user_rooms("user1")
        assert "room_a" in rooms
        assert "room_b" in rooms

    def test_get_room_users(self):
        """Should return users in a room."""
        self.manager.join_room("user1", "room_a")
        self.manager.join_room("user2", "room_a")
        users = self.manager.get_room_users("room_a")
        assert "user1" in users
        assert "user2" in users

    def test_room_stats(self):
        """Should count room members in stats."""
        self.manager.join_room("user1", "room_a")
        self.manager.join_room("user2", "room_a")
        self.manager.join_room("user3", "room_b")
        stats = self.manager.get_stats()
        assert stats["rooms"]["room_a"] == 2
        assert stats["rooms"]["room_b"] == 1

    @pytest.mark.asyncio
    async def test_send_to_user_no_connections(self):
        """Should return 0 when user has no connections."""
        sent = await self.manager.send_to_user("user1", {"type": "test"})
        assert sent == 0

    @pytest.mark.asyncio
    async def test_send_to_user_with_mock(self):
        """Should send to user's connections."""
        mock_ws = AsyncMock()
        self.manager._connections["user1"] = [mock_ws]
        sent = await self.manager.send_to_user("user1", {"type": "test"})
        assert sent == 1
        mock_ws.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        """Should return 0 when no connections exist."""
        sent = await self.manager.broadcast({"type": "test"})
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_with_mock(self):
        """Should broadcast to all connected users."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        self.manager._connections["user1"] = [mock_ws1]
        self.manager._connections["user2"] = [mock_ws2]
        sent = await self.manager.broadcast({"type": "test"})
        assert sent == 2

    @pytest.mark.asyncio
    async def test_send_to_room(self):
        """Should send to all users in a room."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        self.manager._connections["user1"] = [mock_ws1]
        self.manager._connections["user2"] = [mock_ws2]
        self.manager.join_room("user1", "alerts")
        self.manager.join_room("user2", "alerts")
        sent = await self.manager.send_to_room("alerts", {"type": "alert"})
        assert sent == 2

    def test_disconnect_cleans_up(self):
        """Should clean up on disconnect."""
        mock_ws = MagicMock()
        self.manager._connections["user1"] = [mock_ws]
        self.manager._metadata[1] = {"user_id": "user1"}
        self.manager.disconnect(mock_ws, "user1", conn_id=1)
        assert "user1" not in self.manager._connections
        assert 1 not in self.manager._metadata

    def test_disconnect_removes_from_rooms(self):
        """Should remove user from rooms on disconnect."""
        self.manager.join_room("user1", "room_a")
        self.manager.join_room("user2", "room_a")
        mock_ws = MagicMock()
        self.manager._connections["user1"] = [mock_ws]
        self.manager.disconnect(mock_ws, "user1")
        assert "user1" not in self.manager._rooms.get("room_a", set())
        assert "user2" in self.manager._rooms.get("room_a", set())


class TestWebSocketNotifier:
    """Test WebSocketNotifier functionality."""

    def setup_method(self):
        self.notifier = WebSocketNotifier()

    def test_notifier_name(self):
        """Should have correct name."""
        assert self.notifier.name == "websocket"

    def test_notifier_enabled(self):
        """Should be enabled by default."""
        assert self.notifier.enabled is True

    @pytest.mark.asyncio
    async def test_send_broadcasts(self):
        """Should broadcast to all connections."""
        mock_ws = AsyncMock()
        ws_manager._connections["user1"] = [mock_ws]
        result = await self.notifier.send({
            "title": "Test Alert",
            "content": "Hello",
            "priority": "high",
        })
        assert result is True
        assert self.notifier._stats["sent"] == 1
        # Clean up
        ws_manager._connections.clear()

    @pytest.mark.asyncio
    async def test_send_safe_with_dict(self):
        """Should handle dict messages via send_safe."""
        result = await self.notifier.send_safe({
            "title": "Test",
            "content": "Content",
        })
        # May be False if no connections, but should not raise
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_send_safe_disabled(self):
        """Should return False when disabled."""
        self.notifier._enabled = False
        result = await self.notifier.send_safe({"title": "Test"})
        assert result is False

    def test_get_stats(self):
        """Should return stats dictionary."""
        stats = self.notifier.get_stats()
        assert "sent" in stats
        assert "failed" in stats
        assert "total_connections" in stats
