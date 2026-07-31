"""
WebSocket API Endpoints

Provides WebSocket connections for real-time job notifications.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from cybershield.notifications.websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
):
    """
    WebSocket endpoint for real-time notifications.

    Connect with: ws://localhost:8000/api/v1/ws/{user_id}?token=xxx

    Messages received:
    - {"type": "notification", "title": "...", "content": "...", "priority": "high"}
    - {"type": "ping"} -> responds with {"type": "pong"}

    Client can send:
    - {"type": "ping"} -> server responds with {"type": "pong"}
    - {"type": "subscribe", "room": "job_alerts"} -> join a room
    - {"type": "unsubscribe", "room": "job_alerts"} -> leave a room
    """
    conn_id = await ws_manager.connect(websocket, user_id)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected to CyberGuide notifications",
            "user_id": user_id,
            "connection_id": conn_id,
        })

        # Listen for messages from client
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "subscribe":
                    room = message.get("room")
                    if room:
                        ws_manager.join_room(user_id, room)
                        await websocket.send_json({
                            "type": "subscribed",
                            "room": room,
                        })

                elif msg_type == "unsubscribe":
                    room = message.get("room")
                    if room:
                        ws_manager.leave_room(user_id, room)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "room": room,
                        })

                elif msg_type == "rooms":
                    rooms = ws_manager.get_user_rooms(user_id)
                    await websocket.send_json({
                        "type": "rooms",
                        "rooms": rooms,
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id, conn_id)
        logger.info(f"WebSocket client disconnected: user={user_id}")
    except Exception as e:
        ws_manager.disconnect(websocket, user_id, conn_id)
        logger.error(f"WebSocket error for user {user_id}: {e}")
