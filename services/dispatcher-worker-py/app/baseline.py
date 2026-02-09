from __future__ import annotations

"""
File: services/dispatcher-worker-py/app/baseline.py
Purpose: Baseline dispatch heuristic (EDF + nearest idle robot).
Key responsibilities:
- Select pending jobs by deadline/priority.
- Assign to nearest eligible idle robots.
"""

from math import hypot


def _distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance helper."""
    return hypot(ax - bx, ay - by)


def compute_baseline_assignments(
    robots: dict[int, dict],
    jobs: dict[str, dict],
    already_assigned: set[str],
    blocked_robots: set[int],
    battery_threshold: float,
) -> list[dict]:
    """Compute EDF + nearest-robot assignments for idle robots."""
    pending_jobs = [
        j
        for j in jobs.values()
        if j.get("state") in {"pending", "unassigned"} and j["id"] not in already_assigned
    ]
    idle_robots = [
        r
        for r in robots.values()
        if r.get("state") == "idle"
        and int(r.get("id", 0)) not in blocked_robots
        and float(r.get("battery", 0.0)) >= battery_threshold
    ]
    if not idle_robots and pending_jobs:
        # Demo-safe fallback: avoid stalling when all idle robots are below the threshold.
        idle_robots = [
            r
            for r in robots.values()
            if r.get("state") == "idle" and int(r.get("id", 0)) not in blocked_robots
        ]

    pending_jobs.sort(key=lambda j: (int(j.get("deadline_ts", 0)), -int(j.get("priority", 1)), j["id"]))
    idle_robots.sort(key=lambda r: int(r["id"]))

    assignments: list[dict] = []
    used_robots: set[int] = set()

    for job in pending_jobs:
        best_robot = None
        best_distance = float("inf")
        for robot in idle_robots:
            robot_id = int(robot["id"])
            if robot_id in used_robots:
                continue
            d = _distance(float(robot["x"]), float(robot["y"]), float(job["pickup_x"]), float(job["pickup_y"]))
            if d < best_distance or (d == best_distance and robot_id < int(best_robot["id"])):
                best_distance = d
                best_robot = robot
        if best_robot is None:
            continue
        used_robots.add(int(best_robot["id"]))
        assignments.append({
            "job_id": job["id"],
            "robot_id": int(best_robot["id"]),
            "reason": "baseline_edf_nearest",
        })

    assignments.sort(key=lambda a: (a["job_id"], a["robot_id"]))
    return assignments
