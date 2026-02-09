from __future__ import annotations

"""
File: services/sim-runner-py/app/sim/world.py
Purpose: Deterministic scenario generation for robots and jobs.
Key responsibilities:
- Use a seeded RNG to create robot positions/speeds and job locations.
- Compute a scenario hash for comparability across runs.
"""

import hashlib
import json
import random

from app.settings import SCALE_MAP, settings
from app.sim.entities import Job, Robot


def generate_scenario(
    seed: int,
    scale: str,
    world_size: int,
    robots_override: int | None = None,
    jobs_override: int | None = None,
) -> tuple[list[Robot], list[Job], str]:
    """Generate robots/jobs deterministically and return a scenario hash."""
    if scale not in SCALE_MAP:
        raise ValueError(f"invalid scale: {scale}")
    if (robots_override is None) != (jobs_override is None):
        raise ValueError("robots_override and jobs_override must be provided together")
    if robots_override is not None and robots_override <= 0:
        raise ValueError("robots_override must be > 0")
    if jobs_override is not None and jobs_override <= 0:
        raise ValueError("jobs_override must be > 0")

    cfg = SCALE_MAP[scale]
    robots_count = robots_override if robots_override is not None else cfg["robots"]
    jobs_count = jobs_override if jobs_override is not None else cfg["jobs"]
    rng = random.Random(seed)

    robots: list[Robot] = []
    for idx in range(1, robots_count + 1):
        robots.append(
            Robot(
                id=idx,
                x=round(rng.uniform(0, world_size), 3),
                y=round(rng.uniform(0, world_size), 3),
                speed=round(rng.uniform(settings.robot_speed_min, settings.robot_speed_max), 3),
                battery=100.0,
                state="idle",
            )
        )

    jobs: list[Job] = []
    for jdx in range(1, jobs_count + 1):
        pickup_x = round(rng.uniform(0, world_size), 3)
        pickup_y = round(rng.uniform(0, world_size), 3)
        dropoff_x = round(rng.uniform(0, world_size), 3)
        dropoff_y = round(rng.uniform(0, world_size), 3)
        deadline_ts = int(120 + jdx * 12 + rng.randint(0, 20))
        jobs.append(
            Job(
                id=f"job_{jdx}",
                pickup_x=pickup_x,
                pickup_y=pickup_y,
                dropoff_x=dropoff_x,
                dropoff_y=dropoff_y,
                deadline_ts=deadline_ts,
                priority=int(rng.randint(1, 5)),
                state="pending",
                created_sim_ts=0,
            )
        )

    payload = {
        "seed": seed,
        "scale": scale,
        "robots": [robot.__dict__ for robot in robots],
        "jobs": [
            {
                "id": job.id,
                "pickup_x": job.pickup_x,
                "pickup_y": job.pickup_y,
                "dropoff_x": job.dropoff_x,
                "dropoff_y": job.dropoff_y,
                "deadline_ts": job.deadline_ts,
                "priority": job.priority,
            }
            for job in jobs
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    scenario_hash = hashlib.sha256(encoded).hexdigest()
    return robots, jobs, scenario_hash
