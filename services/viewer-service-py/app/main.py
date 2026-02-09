from __future__ import annotations

"""
File: services/viewer-service-py/app/main.py
Purpose: UI backend for the AMR Fleet Manager demo.
Key responsibilities:
- Serve static HTML/JS/CSS dashboard.
- Proxy API calls to fleet-api.
- Start MQ consumer for live snapshot streaming.
Key entrypoints:
- startup_event()
- /api/* endpoints
Config/env vars:
- FLEET_API_URL, FLEET_SCALE, FLEET_SEED, FLEET_MODE
- GA_REPLAN_INTERVAL_S, RABBITMQ_*
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Query, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.mq_consumer import MQConsumer
from app.settings import SCALE_MAP, settings
from app.ws import WSManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s viewer-service %(message)s")
logger = logging.getLogger("viewer-service")

app = FastAPI(title="viewer-service", version="1.0.0")
ws_manager = WSManager()
mq_consumer = MQConsumer(ws_manager)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    """Start the background RabbitMQ consumer on service startup."""
    asyncio.create_task(mq_consumer.start())


@app.get("/")
async def index() -> FileResponse:
    """Serve the dashboard HTML."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness/readiness endpoint."""
    return {"status": "ok"}


@app.get("/api/config")
async def config() -> dict[str, Any]:
    """Return defaults and scale map for the UI."""
    return {
        "defaults": {
            "scale": settings.fleet_scale,
            "seed": settings.fleet_seed,
            "mode": settings.fleet_mode,
            "ga_replan_interval_s": settings.ga_replan_interval_s,
        },
        "scale_map": SCALE_MAP,
    }


@app.post("/api/runs")
async def create_run(payload: dict[str, Any]) -> JSONResponse:
    """Proxy run creation to fleet-api."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{settings.fleet_api_url}/runs", json=payload)
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/api/runs/{run_id}/metrics")
async def run_metrics(run_id: str) -> JSONResponse:
    """Proxy metrics request to fleet-api."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.fleet_api_url}/runs/{run_id}/metrics")
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/api/runs/compare")
async def compare_runs(
    seed: int | None = Query(default=None),
    scale: str | None = Query(default=None),
    robots: int | None = Query(default=None),
    jobs: int | None = Query(default=None),
) -> JSONResponse:
    """Proxy comparison request to fleet-api."""
    query_seed = seed if seed is not None else settings.fleet_seed
    query_scale = scale if scale is not None else settings.fleet_scale
    params: dict[str, Any] = {"seed": query_seed, "scale": query_scale}
    if robots is not None:
        params["robots"] = robots
    if jobs is not None:
        params["jobs"] = jobs
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.fleet_api_url}/runs/compare",
            params=params,
        )
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming snapshot.tick events."""
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:  # noqa: BLE001
        await ws_manager.disconnect(websocket)
