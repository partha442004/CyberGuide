"""
WebSocket Manager

Manages WebSocket connections for real-time job notifications.
Supports user-specific channels, room-based broadcasting, and connection lifecycle.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with user-based routing."""

    def __init__(self):
        # user_id -> list of WebSocket connections
        self._connections: Dict[str, List[WebSocket]] = {}
        # room_name -> set of user_ids
        self._rooms: Dict[str, Set[str]] = {}
        # connection metadata
        self._metadata: Dict[int, Dict[str, Any]] = {}
        self._connection_counter = 0

    @property
    def total_connections(self) -> int:
        """Total active connections."""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def connected_users(self) -> int:
        """Number of unique connected users."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket, user_id: str) -> int:
        """Accept a WebSocket connection and register it for a user."""
        await websocket.accept()
        self._connection_counter += 1
        conn_id = self._connection_counter

        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)

        self._metadata[conn_id] = {
            "user_id": user_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"WebSocket connected: user={user_id}, conn_id={conn_id}")
        return conn_id

    def disconnect(self, websocket: WebSocket, user_id: str, conn_id: Optional[int] = None):
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]
                # Remove user from all rooms
                for room_users in self._rooms.values():
                    room_users.discard(user_id)

        if conn_id and conn_id in self._metadata:
            del self._metadata[conn_id]

        logger.info(f"WebSocket disconnected: user={user_id}")

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """Send a message to all connections for a specific user. Returns number of sends."""
        connections = self._connections.get(user_id, [])
        sent = 0
        disconnected = []

        for ws in connections:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                disconnected.append(ws)

        # Clean up failed connections
        for ws in disconnected:
            self._connections[user_id] = [
                c for c in self._connections.get(user_id, []) if c != ws
            ]

        return sent

    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast a message to all connected users. Returns total sends."""
        total_sent = 0
        for user_id in list(self._connections.keys()):
            total_sent += await self.send_to_user(user_id, message)
        return total_sent

    async def send_to_room(self, room: str, message: Dict[str, Any]) -> int:
        """Send a message to all users in a room. Returns total sends."""
        user_ids = self._rooms.get(room, set())
        total_sent = 0
        for user_id in user_ids:
            total_sent += await self.send_to_user(user_id, message)
        return total_sent

    def join_room(self, user_id: str, room: str):
        """Add a user to a room."""
        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(user_id)
        logger.debug(f"User {user_id} joined room {room}")

    def leave_room(self, user_id: str, room: str):
        """Remove a user from a room."""
        if room in self._rooms:
            self._rooms[room].discard(user_id)
            if not self._rooms[room]:
                del self._rooms[room]
        logger.debug(f"User {user_id} left room {room}")

    def get_user_rooms(self, user_id: str) -> List[str]:
        """Get all rooms a user belongs to."""
        return [room for room, users in self._rooms.items() if user_id in users]

    def get_room_users(self, room: str) -> List[str]:
        """Get all users in a room."""
        return list(self._rooms.get(room, set()))

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": self.total_connections,
            "connected_users": self.connected_users,
            "rooms": {room: len(users) for room, users in self._rooms.items()},
        }


# Global connection manager
ws_manager = ConnectionManager()


class WebSocketNotifier:
    """
    WebSocket notification channel that integrates with the NotificationOrchestrator.
    Sends real-time notifications to connected WebSocket clients.
    """

    def __init__(self):
        self.name = "websocket"
        self._enabled = True
        self._stats = {"sent": 0, "failed": 0}

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, message: Dict[str, Any]) -> bool:
        """Broadcast notification to all connected users."""
        try:
            payload = {
                "type": "notification",
                "title": message.get("title", ""),
                "content": message.get("content", ""),
                "priority": message.get("priority", "medium"),
                "url": message.get("url"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            sent = await ws_manager.broadcast(payload)
            self._stats["sent"] += 1
            return sent > 0
        except Exception as e:
            logger.error(f"WebSocket notification error: {e}")
            self._stats["failed"] += 1
            return False

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send notification to a specific user."""
        try:
            payload = {
                "type": "notification",
                "title": message.get("title", ""),
                "content": message.get("content", ""),
                "priority": message.get("priority", "medium"),
                "url": message.get("url"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            sent = await ws_manager.send_to_user(user_id, payload)
            self._stats["sent"] += 1
            return sent > 0
        except Exception as e:
            logger.error(f"WebSocket notification to user {user_id} error: {e}")
            self._stats["failed"] += 1
            return False

    async def send_safe(self, message) -> bool:
        """Send with error handling (compatible with BaseNotifier interface)."""
        if not self._enabled:
            return False

        # Handle both dict and NotificationMessage objects
        if hasattr(message, "to_dict"):
            msg_dict = message.to_dict()
        elif isinstance(message, dict):
            msg_dict = message
        else:
            msg_dict = {"title": str(message), "content": ""}

        return await self.send(msg_dict)

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket notification stats."""
        return {
            **self._stats,
            **ws_manager.get_stats(),
        }
