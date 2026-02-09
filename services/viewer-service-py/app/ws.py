from __future__ import annotations

"""
File: services/viewer-service-py/app/ws.py
Purpose: WebSocket connection manager for broadcast to UI clients.
"""

import asyncio
import json
from fastapi import WebSocket


class WSManager:
    """Manage WebSocket clients and broadcast messages."""
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and track a new WebSocket client."""
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected client."""
        async with self._lock:
            self.clients.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        """Send a JSON payload to all connected clients."""
        data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        stale: list[WebSocket] = []
        async with self._lock:
            clients = list(self.clients)
        for client in clients:
            try:
                await client.send_text(data)
            except Exception:  # noqa: BLE001
                stale.append(client)
        if stale:
            async with self._lock:
                for client in stale:
                    self.clients.discard(client)
