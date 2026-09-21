import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException
from sqlalchemy import select

from app.core.security import get_current_user_ws
from app.core.ws_manager import sos_ws_manager
from app.db.session import async_session_maker
from app.models.sos_session import SosSession
from app.models.user import User

router = APIRouter(tags=["sos-ws"])


@router.websocket("/ws/sos/{session_id}")
async def sos_live_location(
    websocket: WebSocket,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user_ws),
) -> None:
    # Any authenticated user may watch any active session (no responder/KYC
    # tier exists yet — matches GET /sos/nearby's existing openness).
    async with async_session_maker() as db:
        result = await db.execute(select(SosSession).where(SosSession.id == session_id))
        session = result.scalar_one_or_none()

    if session is None:
        raise WebSocketException(code=4404, reason="SOS session not found")
    if session.status != "active":
        raise WebSocketException(code=4409, reason="SOS session is not active")

    await sos_ws_manager.connect(session_id, websocket)
    try:
        while True:
            # No client->server messages are expected; this purely awaits
            # disconnection (a closed socket raises WebSocketDisconnect here).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sos_ws_manager.disconnect(session_id, websocket)
