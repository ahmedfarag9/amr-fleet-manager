from __future__ import annotations

"""
File: services/dispatcher-worker-py/app/planner_client.py
Purpose: HTTP client for optimizer-service GA planning.
Key responsibilities:
- Call /optimize with current robots + pending jobs.
- Normalize and sort assignment responses.
"""

import httpx


async def request_ga_plan(
    optimizer_url: str,
    run_id: str,
    seed: int,
    scale: str,
    sim_time_s: int,
    robots: list[dict],
    pending_jobs: list[dict],
) -> list[dict]:
    """Call optimizer-service and return normalized assignments."""
    payload = {
        "run_id": run_id,
        "seed": seed,
        "scale": scale,
        "mode": "ga",
        "sim_time_s": sim_time_s,
        "robots": robots,
        "pending_jobs": pending_jobs,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{optimizer_url}/optimize", json=payload)
        resp.raise_for_status()
        data = resp.json()
    assignments = data.get("assignments", [])
    normalized: list[dict] = []
    for item in assignments:
        normalized.append(
            {
                "job_id": str(item["job_id"]),
                "robot_id": int(item["robot_id"]),
                "reason": "ga_optimizer",
                "score": float(item.get("score", 0.0)),
            }
        )
    normalized.sort(key=lambda a: (a["job_id"], a["robot_id"]))
    return normalized
