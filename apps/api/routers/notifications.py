"""
MOD-07: Push Notifications — SSE + WebSocket
Live-Updates für Bill Status Änderungen.

- SSE (Browser-native)
- WebSocket (Mobile App)
- In-Memory Pub/Sub (Beta) → Redis (Produktion)

@ai-anchor MOD07_NOTIFICATIONS
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/notifications", tags=["MOD-07 Notifications"])


class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    async def publish(self, event: dict):
        payload = json.dumps({**event, "timestamp": datetime.now(timezone.utc).isoformat()})
        dead = []
        for q in self._subscribers:
            try:
                await q.put(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


event_bus = EventBus()


async def publish_bill_event(event_type: str, bill_id: str, data: dict = {}):
    """Öffentlich — von parliament.py aufgerufen."""
    await event_bus.publish({"type": event_type, "bill_id": bill_id, **data})


async def publish_vote_milestone(bill_id: str, total_votes: int):
    """Milestone bei 100/500/1000/5000 Stimmen."""
    if total_votes in [100, 500, 1000, 5000, 10000]:
        await publish_bill_event("bill.vote_milestone", bill_id, {
            "milestone": total_votes,
            "message_el": f"{total_votes} ψήφοι για το νομοσχέδιο!",
        })


from fastapi.responses import StreamingResponse


@router.get("/stream")
async def event_stream(
    request: Request,
    bill_id: Optional[str] = Query(None),
):
    """SSE Stream. Browser: new EventSource('/api/v1/notifications/stream')"""
    queue = event_bus.subscribe()

    async def generate() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'connected', 'subscribers': event_bus.subscriber_count})}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = json.loads(payload)
                    if bill_id and data.get("bill_id") != bill_id:
                        continue
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, bill_id: Optional[str] = Query(None)):
    """WebSocket für Mobile App."""
    await websocket.accept()
    queue = event_bus.subscribe()
    try:
        await websocket.send_json({"type": "connected", "subscribers": event_bus.subscriber_count})
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                data = json.loads(payload)
                if bill_id and data.get("bill_id") != bill_id:
                    continue
                await websocket.send_text(payload)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)


@router.post("/test/publish")
async def test_publish(
    event_type: str = Query("bill.status_changed"),
    bill_id: str = Query("GR-2025-0001"),
    admin_key: str = Query(...),
):
    """DEV: Test Event publishen."""
    import os
    if admin_key != os.environ.get("ADMIN_KEY", "dev-admin-key"):
        raise HTTPException(403, "Ungültiger Admin-Key")

    await publish_bill_event(event_type, bill_id, {"message_el": f"Test: {event_type}", "source": "admin_test"})
    return {"published": True, "event_type": event_type, "subscribers": event_bus.subscriber_count}


@router.get("/status")
async def notifications_status():
    return {
        "module": "MOD-07 Push Notifications", "status": "active",
        "subscribers": event_bus.subscriber_count,
        "transport": ["SSE", "WebSocket"],
        "backend": "In-Memory (Beta)",
        "events": ["bill.status_changed", "bill.vote_milestone", "bill.window_24h", "bill.parliament_voted"],
        "usage": {
            "browser": "new EventSource('/api/v1/notifications/stream')",
            "mobile": "new WebSocket('wss://api.ekklesia.gr/api/v1/notifications/ws')",
        },
    }
