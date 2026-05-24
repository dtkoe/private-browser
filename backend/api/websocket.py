from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.services.event_bus import bus


def build_ws_router(token: str) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def ws(websocket: WebSocket, t: str = Query(default="")):
        if t != token:
            await websocket.close(code=4401, reason="bad token")
            return
        await websocket.accept()
        q = bus.subscribe()
        try:
            while True:
                event = await q.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            bus.unsubscribe(q)

    return router
