from __future__ import annotations

"""
File: services/optimizer-service-py/app/schemas.py
Purpose: Pydantic models for optimizer request/response contracts.
Key responsibilities:
- Validate incoming /optimize payloads.
- Define assignment and metadata schema.
Key entrypoints:
- OptimizeRequest, OptimizeResponse
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


RobotState = Literal["idle", "moving_to_pickup", "moving_to_dropoff", "charging"]
JobState = Literal["pending", "unassigned", "assigned", "in_progress", "completed", "failed"]


class Robot(BaseModel):
    """Robot state snapshot used by the optimizer."""
    id: int
    x: float
    y: float
    speed: float
    battery: float
    state: RobotState
    current_job_id: Optional[str] = None


class Job(BaseModel):
    """Job definition used by the optimizer."""
    id: str
    pickup_x: float
    pickup_y: float
    dropoff_x: float
    dropoff_y: float
    deadline_ts: int
    priority: int = Field(ge=1, le=5)
    state: JobState = "pending"


class OptimizeRequest(BaseModel):
    """Request body for /optimize."""
    run_id: str
    seed: int
    scale: str
    mode: Literal["baseline", "ga"]
    sim_time_s: int = 0
    robots: list[Robot]
    pending_jobs: list[Job]


class Assignment(BaseModel):
    """Optimizer assignment result for a single job."""
    job_id: str
    robot_id: int
    score: float


class OptimizeResponse(BaseModel):
    """Response payload from /optimize."""
    assignments: list[Assignment]
    meta: dict[str, object]
