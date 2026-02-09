from __future__ import annotations

"""
File: services/sim-runner-py/app/sim/metrics.py
Purpose: Compute aggregate run metrics from job and robot state.
Key responsibilities:
- On-time rate, distance, completion time, lateness totals.
"""

from app.sim.entities import Job, Robot


def compute_metrics(jobs: list[Job], robots: list[Robot]) -> dict[str, float | int]:
    """Compute run-level metrics used by the UI and API."""
    total_jobs = len(jobs)
    completed_jobs = sum(1 for j in jobs if j.state == "completed")
    failed_jobs = sum(1 for j in jobs if j.state == "failed")
    on_time = sum(1 for j in jobs if j.state == "completed" and (j.completed_sim_ts or 0) <= j.deadline_ts)
    on_time_rate = (on_time / total_jobs * 100.0) if total_jobs else 0.0

    completion_times = [float(j.completed_sim_ts or 0) for j in jobs if j.state == "completed"]
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0.0

    lateness_values = [float(j.lateness_s) for j in jobs if j.state == "completed"]
    max_lateness = max(lateness_values) if lateness_values else 0.0

    total_distance = sum(r.distance_traveled for r in robots)

    return {
        "on_time_rate": round(on_time_rate, 6),
        "total_distance": round(total_distance, 6),
        "avg_completion_time": round(avg_completion_time, 6),
        "max_lateness": round(max_lateness, 6),
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "total_jobs": total_jobs,
    }
