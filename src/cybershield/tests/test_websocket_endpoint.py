"""
Tests for the WebSocket API endpoint (``api/v1/websocket.py``).

Drives ``websocket_endpoint`` directly with a fake WebSocket that scripts the
client messages, so every message-type branch and the disconnect path are
covered without a live connection.
"""

import json
from typing import Any, cast

import pytest

from cybershield.api.v1.websocket import websocket_endpoint
from cybershield.notifications.websocket import ws_manager


class FakeWebSocket:
    """Minimal stand-in for FastAPI's WebSocket.

    When the scripted message queue is exhausted, ``receive_text`` raises
    ``WebSocketDisconnect`` — exactly what FastAPI raises when a client
    disconnects — so the endpoint's disconnect path runs naturally.
    """

    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, data):
        self.sent.append(data)

    async def receive_text(self) -> str:
        from fastapi import WebSocketDisconnect

        if not self._messages:
            raise WebSocketDisconnect()
        return cast(str, self._messages.pop(0))


@pytest.fixture(autouse=True)
def _clean_manager():
    """Reset the shared connection manager around each test."""
    ws_manager._connections.clear()
    ws_manager._rooms.clear()
    ws_manager._metadata.clear()
    ws_manager._connection_counter = 0
    yield


def _run_endpoint(ws, user_id: str):
    """Invoke the endpoint with the fake websocket (typed as WebSocket)."""
    return websocket_endpoint(cast(Any, ws), user_id)


@pytest.mark.asyncio
async def test_welcome_message_sent_on_connect():
    ws = FakeWebSocket(messages=[])
    await _run_endpoint(ws, "user-1")
    assert ws.sent[0]["type"] == "connected"
    assert ws.sent[0]["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_ping_returns_pong():
    ws = FakeWebSocket(messages=[json.dumps({"type": "ping"})])
    await _run_endpoint(ws, "user-1")
    types = [m["type"] for m in ws.sent]
    assert "connected" in types
    assert "pong" in types


@pytest.mark.asyncio
async def test_subscribe_joins_room():
    ws = FakeWebSocket(messages=[json.dumps({"type": "subscribe", "room": "job_alerts"})])
    await _run_endpoint(ws, "user-1")
    sent_types = [m["type"] for m in ws.sent]
    assert "subscribed" in sent_types
    # The room was created by join_room (the user is later removed when the
    # scripted queue ends and the endpoint's disconnect path runs).
    assert "job_alerts" in ws_manager._rooms


@pytest.mark.asyncio
async def test_unsubscribe_leaves_room():
    ws = FakeWebSocket(
        messages=[
            json.dumps({"type": "subscribe", "room": "job_alerts"}),
            json.dumps({"type": "unsubscribe", "room": "job_alerts"}),
        ]
    )
    await _run_endpoint(ws, "user-1")
    assert "job_alerts" not in ws_manager._rooms
    assert any(m["type"] == "unsubscribed" for m in ws.sent)


@pytest.mark.asyncio
async def test_rooms_reports_user_rooms():
    ws = FakeWebSocket(
        messages=[
            json.dumps({"type": "subscribe", "room": "room_a"}),
            json.dumps({"type": "rooms"}),
        ]
    )
    await _run_endpoint(ws, "user-1")
    rooms_msg = next(m for m in ws.sent if m["type"] == "rooms")
    assert rooms_msg["rooms"] == ["room_a"]


@pytest.mark.asyncio
async def test_unknown_message_type_returns_error():
    ws = FakeWebSocket(messages=[json.dumps({"type": "bogus"})])
    await _run_endpoint(ws, "user-1")
    assert any(m["type"] == "error" for m in ws.sent)


@pytest.mark.asyncio
async def test_invalid_json_returns_error():
    ws = FakeWebSocket(messages=["not-json{"])
    await _run_endpoint(ws, "user-1")
    error = next(m for m in ws.sent if m["type"] == "error")
    assert error["message"] == "Invalid JSON"


@pytest.mark.asyncio
async def test_disconnect_cleans_up_connection():
    # Empty message queue -> receive_text raises WebSocketDisconnect on the
    # first read, after connect() has already registered the connection.
    d_ws = FakeWebSocket(messages=[])
    await _run_endpoint(d_ws, "user-2")
    # The connection was registered then cleaned up on disconnect.
    assert "user-2" not in ws_manager._connections
