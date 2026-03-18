"""WebSocket endpoint for real-time progress updates."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.logging_config import get_logger
from app.services.progress import progress_bus

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/progress")
async def ws_progress(websocket: WebSocket) -> None:
    """Stream progress events to the client.

    Protocol:
    1. Client connects
    2. Client sends ``{"request_id": "..."}``
    3. Server pushes ``ProgressEvent`` JSON messages
    4. Connection closes when *complete* event is sent
       or the client disconnects.
    """
    await websocket.accept()
    request_id: str | None = None
    try:
        # Wait for the subscribe message
        data = await websocket.receive_json()
        request_id = data.get("request_id")
        if not request_id:
            await websocket.close(code=4000, reason="Missing request_id")
            return

        queue = progress_bus.subscribe(request_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send a heartbeat to keep the connection alive
                    await websocket.send_json(
                        {"stage": "heartbeat", "progress": -1, "message": ""}
                    )
                    continue

                await websocket.send_json(event.to_dict())

                if event.stage == "complete":
                    break
        finally:
            progress_bus.unsubscribe(request_id)
    except WebSocketDisconnect:
        logger.debug("WS client disconnected: %s", request_id)
        if request_id:
            progress_bus.unsubscribe(request_id)
    except Exception:
        logger.exception("WS error for %s", request_id)
        if request_id:
            progress_bus.unsubscribe(request_id)
