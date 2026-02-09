from __future__ import annotations

"""
File: services/sim-runner-py/app/sim/entities.py
Purpose: Core dataclasses and type aliases for simulation state.
"""

from dataclasses import dataclass, field
from typing import Literal


RobotState = Literal["idle", "moving_to_pickup", "moving_to_dropoff", "charging"]
JobState = Literal["pending", "unassigned", "assigned", "in_progress", "completed", "failed"]


@dataclass
class Robot:
    """Robot state tracked by the simulation engine."""
    id: int
    x: float
    y: float
    speed: float
    battery: float
    state: RobotState = "idle"
    current_job_id: str | None = None
    target_x: float | None = None
    target_y: float | None = None
    phase_remaining_s: float = 0.0
    distance_traveled: float = 0.0


@dataclass
class Job:
    """Job definition and lifecycle tracking for the simulation."""
    id: str
    pickup_x: float
    pickup_y: float
    dropoff_x: float
    dropoff_y: float
    deadline_ts: int
    priority: int
    state: JobState = "pending"
    assigned_robot_id: int | None = None
    created_sim_ts: int = 0
    started_sim_ts: int | None = None
    completed_sim_ts: int | None = None
    lateness_s: float = 0.0


@dataclass
class SimulationState:
    """Container for all simulation entities and counters."""
    run_id: str
    mode: str
    seed: int
    scale: str
    robots: list[Robot]
    jobs: list[Job]
    tick: int = 0
    total_ticks: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    job_completion_times: list[float] = field(default_factory=list)
    lateness_values: list[float] = field(default_factory=list)
