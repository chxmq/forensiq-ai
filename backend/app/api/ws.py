"""WebSocket endpoints for real-time analysis & global activity streaming."""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.auth import verify_ws_token
from app.core.config import get_settings
from app.services.pipeline.ws_manager import GLOBAL_ROOM, manager

router = APIRouter()


@router.websocket("/ws/applications/{application_id}")
async def application_stream(
    websocket: WebSocket,
    application_id: str,
    token: str | None = Query(None),
) -> None:
    if get_settings().auth_enabled:
        verify_ws_token(token)
    await manager.connect(application_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "application_id": application_id})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(application_id, websocket)
    except Exception:  # noqa: BLE001
        await manager.disconnect(application_id, websocket)


@router.websocket("/ws/activity")
async def activity_stream(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    if get_settings().auth_enabled:
        verify_ws_token(token)
    await manager.connect(GLOBAL_ROOM, websocket)
    try:
        await websocket.send_json({"type": "connected", "room": "activity"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(GLOBAL_ROOM, websocket)
    except Exception:  # noqa: BLE001
        await manager.disconnect(GLOBAL_ROOM, websocket)
