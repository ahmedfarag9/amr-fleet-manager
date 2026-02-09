from __future__ import annotations

"""
File: services/sim-runner-py/app/sim/engine.py
Purpose: Deterministic simulation engine for robots and jobs.
Key responsibilities:
- Apply assignments and advance robots each tick.
- Emit robot.updated events on state changes and throttled position updates.
- Enforce charging behavior on battery depletion.
"""

from dataclasses import dataclass
from math import hypot
from typing import Callable

from app.sim.entities import Job, Robot, SimulationState


@dataclass
class Assignment:
    """Job assignment for a specific robot."""
    job_id: str
    robot_id: int


class SimulationEngine:
    """Simulation engine that advances robot/job state per tick."""
    def __init__(
        self,
        state: SimulationState,
        tick_hz: int,
        service_time_s: int,
        max_sim_seconds: int,
        robot_update_sink: Callable[[dict], None],
        emit_position_updates: bool = True,
        charge_rate: float = 5.0,
        charge_resume_threshold: float = 20.0,
    ) -> None:
        """Initialize the engine with simulation parameters."""
        self.state = state
        self.tick_hz = tick_hz
        self.dt = 1.0 / tick_hz
        self.service_time_s = float(service_time_s)
        self.max_sim_seconds = max_sim_seconds
        self.robot_update_sink = robot_update_sink
        self.emit_position_updates = emit_position_updates
        self.charge_rate = charge_rate
        self.charge_resume_threshold = charge_resume_threshold

        self.jobs_by_id = {job.id: job for job in state.jobs}
        self.robots_by_id = {robot.id: robot for robot in state.robots}

        self.last_emitted_state: dict[int, str] = {}
        self.last_position_emit_sim_s: dict[int, int] = {}
        self.dropoff_service_remaining: dict[int, float] = {}
        self.resume_state: dict[int, str] = {}

    def current_sim_time_s(self) -> int:
        """Return the current simulation time in whole seconds."""
        return self.state.tick // self.tick_hz

    def emit_initial_robot_updates(self) -> None:
        """Emit robot.updated for all robots at sim start."""
        sim_time_s = self.current_sim_time_s()
        for robot in sorted(self.state.robots, key=lambda r: r.id):
            self._emit_robot_updated(robot, sim_time_s=sim_time_s, force=True)

    def apply_assignment(self, assignment: Assignment) -> bool:
        """Apply a job assignment if the robot/job are eligible."""
        robot = self.robots_by_id.get(assignment.robot_id)
        job = self.jobs_by_id.get(assignment.job_id)
        if robot is None or job is None:
            return False
        if robot.state != "idle":
            return False
        if job.state not in {"pending", "unassigned"}:
            return False

        job.state = "assigned"
        job.assigned_robot_id = robot.id
        job.started_sim_ts = self.current_sim_time_s()

        robot.current_job_id = job.id
        robot.target_x = job.pickup_x
        robot.target_y = job.pickup_y
        robot.phase_remaining_s = 0.0
        robot.state = "moving_to_pickup"
        self._emit_robot_updated(robot, sim_time_s=self.current_sim_time_s(), force=True)
        return True

    def step(self) -> None:
        """Advance the simulation by one tick."""
        sim_time_s = self.current_sim_time_s()
        for robot in sorted(self.state.robots, key=lambda r: r.id):
            prev_state = robot.state
            self._advance_robot(robot)
            if robot.state != prev_state:
                self._emit_robot_updated(robot, sim_time_s=sim_time_s, force=True)
            elif self.emit_position_updates:
                self._emit_robot_updated(robot, sim_time_s=sim_time_s, force=False)

        self.state.tick += 1

    def should_stop(self) -> bool:
        """Return True if max time reached or all jobs are terminal."""
        if self.current_sim_time_s() >= self.max_sim_seconds:
            return True
        return all(job.state in {"completed", "failed"} for job in self.state.jobs)

    def finalize(self) -> None:
        """Mark any remaining active jobs as failed at end of sim."""
        sim_time_s = self.current_sim_time_s()
        for job in self.state.jobs:
            if job.state in {"pending", "unassigned", "assigned", "in_progress"}:
                job.state = "failed"
                job.completed_sim_ts = sim_time_s
                job.lateness_s = float(max(0, sim_time_s - job.deadline_ts))

    def snapshot(self) -> dict:
        """Return a serializable snapshot of current sim state."""
        sim_time_s = self.current_sim_time_s()
        return {
            "run_id": self.state.run_id,
            "mode": self.state.mode,
            "seed": self.state.seed,
            "scale": self.state.scale,
            "sim_time_s": sim_time_s,
            "robots": [
                {
                    "id": r.id,
                    "x": round(r.x, 3),
                    "y": round(r.y, 3),
                    "speed": r.speed,
                    "battery": round(r.battery, 3),
                    "state": r.state,
                    "current_job_id": r.current_job_id,
                }
                for r in sorted(self.state.robots, key=lambda item: item.id)
            ],
            "jobs": [
                {
                    "id": j.id,
                    "pickup_x": j.pickup_x,
                    "pickup_y": j.pickup_y,
                    "dropoff_x": j.dropoff_x,
                    "dropoff_y": j.dropoff_y,
                    "deadline_ts": j.deadline_ts,
                    "priority": j.priority,
                    "state": j.state,
                    "assigned_robot_id": j.assigned_robot_id,
                }
                for j in sorted(self.state.jobs, key=lambda item: item.id)
            ],
        }

    def _advance_robot(self, robot: Robot) -> None:
        """Advance a single robot for the current tick."""
        if robot.state == "charging":
            robot.battery = min(100.0, robot.battery + self.charge_rate * self.dt)
            if robot.battery >= self.charge_resume_threshold:
                robot.state = self.resume_state.pop(robot.id, "idle")
            return

        if robot.battery <= 0.0 and robot.state in {"moving_to_pickup", "moving_to_dropoff"}:
            self.resume_state[robot.id] = robot.state
            robot.state = "charging"
            return

        if robot.state not in {"moving_to_pickup", "moving_to_dropoff"}:
            return

        job = self.jobs_by_id.get(robot.current_job_id or "")
        if job is None:
            robot.state = "idle"
            robot.current_job_id = None
            robot.target_x = None
            robot.target_y = None
            robot.phase_remaining_s = 0.0
            return

        if robot.target_x is None or robot.target_y is None:
            robot.state = "idle"
            robot.current_job_id = None
            return

        dx = robot.target_x - robot.x
        dy = robot.target_y - robot.y
        distance_to_target = hypot(dx, dy)
        step_distance = robot.speed * self.dt

        if distance_to_target > 0:
            travel = min(distance_to_target, step_distance)
            ratio = travel / distance_to_target
            robot.x += dx * ratio
            robot.y += dy * ratio
            robot.distance_traveled += travel
            robot.battery = max(0.0, robot.battery - travel * 0.1)
            if robot.battery <= 0.0:
                self.resume_state[robot.id] = robot.state
                robot.state = "charging"
                return

        arrived = distance_to_target <= step_distance + 1e-9

        if not arrived:
            return

        if robot.state == "moving_to_pickup":
            if robot.phase_remaining_s <= 0:
                robot.phase_remaining_s = self.service_time_s
            robot.phase_remaining_s = max(0.0, robot.phase_remaining_s - self.dt)
            if robot.phase_remaining_s > 0:
                return
            job.state = "in_progress"
            robot.state = "moving_to_dropoff"
            robot.target_x = job.dropoff_x
            robot.target_y = job.dropoff_y
            robot.phase_remaining_s = 0.0
            return

        if robot.state == "moving_to_dropoff":
            remaining = self.dropoff_service_remaining.get(robot.id, self.service_time_s)
            remaining = max(0.0, remaining - self.dt)
            if remaining > 0:
                self.dropoff_service_remaining[robot.id] = remaining
                return
            self.dropoff_service_remaining.pop(robot.id, None)
            completion_time = self.current_sim_time_s()
            job.state = "completed"
            job.completed_sim_ts = completion_time
            job.lateness_s = float(max(0, completion_time - job.deadline_ts))
            robot.state = "idle"
            robot.current_job_id = None
            robot.target_x = None
            robot.target_y = None
            robot.phase_remaining_s = 0.0

    def _emit_robot_updated(self, robot: Robot, sim_time_s: int, force: bool) -> None:
        """Emit robot.updated events with throttling for position updates."""
        if force:
            payload = self._robot_payload(robot, sim_time_s)
            self.robot_update_sink(payload)
            self.last_emitted_state[robot.id] = robot.state
            self.last_position_emit_sim_s[robot.id] = sim_time_s
            return

        # Optional position update, throttled to <=1Hz per robot.
        last_emit = self.last_position_emit_sim_s.get(robot.id)
        if last_emit is not None and sim_time_s <= last_emit:
            return
        payload = self._robot_payload(robot, sim_time_s)
        self.robot_update_sink(payload)
        self.last_position_emit_sim_s[robot.id] = sim_time_s

    def _robot_payload(self, robot: Robot, sim_time_s: int) -> dict:
        """Build the robot.updated payload."""
        return {
            "robot_id": robot.id,
            "state": robot.state,
            "sim_time_s": int(sim_time_s),
            "x": round(robot.x, 3),
            "y": round(robot.y, 3),
            "speed": robot.speed,
            "battery": round(robot.battery, 3),
            "current_job_id": robot.current_job_id,
        }
