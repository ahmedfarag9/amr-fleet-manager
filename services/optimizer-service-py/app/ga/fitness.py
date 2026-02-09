from __future__ import annotations

"""
File: services/optimizer-service-py/app/ga/fitness.py
Purpose: Fitness evaluation for GA chromosomes.
Key responsibilities:
- Compute lateness, distance, priority, battery, and load penalties.
- Return total score and per-job scores.
"""

from dataclasses import dataclass
from math import hypot
from typing import Sequence

from app.schemas import Job, Robot


@dataclass
class FitnessResult:
    score: float
    job_scores: dict[str, float]


def _distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance helper."""
    return hypot(ax - bx, ay - by)


def sorted_jobs(jobs: Sequence[Job]) -> list[Job]:
    """Return jobs in deterministic order for GA evaluation."""
    return sorted(jobs, key=lambda j: (j.deadline_ts, -j.priority, j.id))


def evaluate_chromosome(
    chromosome: Sequence[int],
    robots: Sequence[Robot],
    jobs: Sequence[Job],
    service_time_s: int,
) -> FitnessResult:
    """Evaluate a chromosome and return total score + per-job contributions."""
    if not jobs:
        return FitnessResult(score=0.0, job_scores={})
    if not robots:
        return FitnessResult(score=1e9, job_scores={job.id: 1e9 for job in jobs})

    ordered_jobs = sorted_jobs(jobs)

    robot_time = [0.0 for _ in robots]
    robot_pos = [(r.x, r.y) for r in robots]
    robot_battery = [r.battery for r in robots]
    robot_job_count = [0 for _ in robots]

    total_score = 0.0
    job_scores: dict[str, float] = {}

    for idx, job in enumerate(ordered_jobs):
        assigned_robot_idx = chromosome[idx] % len(robots)
        rx, ry = robot_pos[assigned_robot_idx]
        travel_to_pickup = _distance(rx, ry, job.pickup_x, job.pickup_y)
        travel_to_dropoff = _distance(job.pickup_x, job.pickup_y, job.dropoff_x, job.dropoff_y)
        distance = travel_to_pickup + travel_to_dropoff
        speed = max(robots[assigned_robot_idx].speed, 0.1)
        travel_time = distance / speed

        completion_time = robot_time[assigned_robot_idx] + travel_time + 2 * service_time_s
        lateness = max(0.0, completion_time - job.deadline_ts)

        battery_after = robot_battery[assigned_robot_idx] - distance * 0.1
        battery_penalty = 0.0
        if battery_after < 0:
            battery_penalty = 500.0 + abs(battery_after) * 100.0
        elif battery_after < 10:
            battery_penalty = 200.0

        load_penalty = float(robot_job_count[assigned_robot_idx] ** 2) * 30.0

        job_penalty = (
            lateness * 1000.0
            + distance * 2.0
            + (6 - job.priority) * 3.0
            + battery_penalty
            + load_penalty
        )
        total_score += job_penalty
        job_scores[job.id] = job_penalty

        robot_time[assigned_robot_idx] = completion_time
        robot_pos[assigned_robot_idx] = (job.dropoff_x, job.dropoff_y)
        robot_battery[assigned_robot_idx] = max(0.0, battery_after)
        robot_job_count[assigned_robot_idx] += 1

    return FitnessResult(score=total_score, job_scores=job_scores)
