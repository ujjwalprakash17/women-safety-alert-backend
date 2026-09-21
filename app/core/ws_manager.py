import uuid

from starlette.websockets import WebSocket


class SosWsManager:
    """In-memory per-session WebSocket registry.

    Single dev process, no cross-process fan-out (no Redis pub/sub) — fine
    for this milestone; would need one if the backend ever runs as more than
    a single process/worker.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}

    async def connect(self, session_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(session_id, set()).add(websocket)

    def disconnect(self, session_id: uuid.UUID, websocket: WebSocket) -> None:
        conns = self._connections.get(session_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._connections.pop(session_id, None)

    async def broadcast(self, session_id: uuid.UUID, message: dict) -> None:
        conns = self._connections.get(session_id)
        if not conns:
            return
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def close_all(self, session_id: uuid.UUID, code: int = 1000) -> None:
        for ws in self._connections.pop(session_id, set()):
            try:
                await ws.close(code=code)
            except Exception:
                pass


sos_ws_manager = SosWsManager()
