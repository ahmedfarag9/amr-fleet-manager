from __future__ import annotations

"""
File: services/dispatcher-worker-py/app/main.py
Purpose: RabbitMQ consumer that emits job assignments (baseline or GA).
Key responsibilities:
- Maintain per-run in-memory state from job/robot events.
- Run baseline heuristic or call optimizer-service for GA plans.
- Emit job.assigned events with idempotency safeguards.
Key entrypoints:
- DispatcherWorker.run()
Config/env vars:
- RABBITMQ_*, FLEET_SCALE, FLEET_SEED, FLEET_MODE
- GA_REPLAN_INTERVAL_S, BATTERY_THRESHOLD, OPTIMIZER_URL
"""

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import aio_pika

from app.baseline import compute_baseline_assignments
from app.mq import connect, publish_event, setup_topology
from app.planner_client import request_ga_plan
from app.settings import rabbit_url, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s dispatcher-worker %(message)s",
)
logger = logging.getLogger("dispatcher-worker")


@dataclass
class RunState:
    """In-memory dispatcher state for a single run."""
    run_id: str
    mode: str
    seed: int
    scale: str
    robots: dict[int, dict[str, Any]] = field(default_factory=dict)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    assigned_jobs: set[str] = field(default_factory=set)
    pending_assignments: dict[int, str] = field(default_factory=dict)
    planned_queues: dict[int, list[str]] = field(default_factory=dict)
    optimizer_in_flight: bool = False
    next_periodic_replan_sim_s: int | None = None
    last_baseline_dispatch_sim_s: int | None = None
    baseline_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    assign_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class DispatcherWorker:
    """RabbitMQ worker for dispatching jobs based on robot/job events."""
    def __init__(self) -> None:
        self.states: dict[str, RunState] = {}
        self.exchange: aio_pika.abc.AbstractExchange | None = None

    async def run(self) -> None:
        """Connect to RabbitMQ, declare queues, and start consuming events."""
        connection = await connect(rabbit_url())
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=50)

        exchange, q_run_started, q_job_created, q_robot_updated = await setup_topology(channel, settings.exchange_name)
        self.exchange = exchange

        await q_run_started.consume(self._on_message)
        await q_job_created.consume(self._on_message)
        await q_robot_updated.consume(self._on_message)

        logger.info("dispatcher worker started")
        await asyncio.Future()

    async def _on_message(self, message: aio_pika.IncomingMessage) -> None:
        """Dispatch incoming events by routing key with safe ACK behavior."""
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("dropping invalid JSON message routing_key=%s", message.routing_key)
            await message.ack()
            return

        try:
            routing_key = message.routing_key
            if routing_key == "run.started":
                await self._handle_run_started(payload)
            elif routing_key == "job.created":
                await self._handle_job_created(payload)
            elif routing_key == "robot.updated":
                await self._handle_robot_updated(payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("handler error routing_key=%s err=%s", message.routing_key, exc)
        finally:
            await message.ack()

    async def _handle_run_started(self, event: dict[str, Any]) -> None:
        """Initialize state for a new run and trigger GA start replans."""
        run_id = str(event.get("run_id", ""))
        if not run_id:
            logger.warning("run.started missing run_id")
            return
        mode = str(event.get("mode", settings.fleet_mode))
        seed = int(event.get("seed", settings.fleet_seed))
        scale = str(event.get("scale", settings.fleet_scale))

        state = RunState(
            run_id=run_id,
            mode=mode,
            seed=seed,
            scale=scale,
            next_periodic_replan_sim_s=settings.ga_replan_interval_s if settings.ga_replan_interval_s > 0 else None,
        )
        self.states[run_id] = state
        logger.info("run started run_id=%s mode=%s seed=%s scale=%s", run_id, mode, seed, scale)

        if mode == "ga":
            await self._replan_ga(state, sim_time_s=0, reason="run_start")

    async def _handle_job_created(self, event: dict[str, Any]) -> None:
        """Ingest job.created events into in-memory state."""
        run_id = str(event.get("run_id", ""))
        state = self.states.get(run_id)
        if state is None:
            return

        job_id = str(event.get("job_id", ""))
        if not job_id:
            logger.warning("job.created missing job_id run_id=%s", run_id)
            return

        state.jobs[job_id] = {
            "id": job_id,
            "pickup_x": float(event.get("pickup_x", 0.0)),
            "pickup_y": float(event.get("pickup_y", 0.0)),
            "dropoff_x": float(event.get("dropoff_x", 0.0)),
            "dropoff_y": float(event.get("dropoff_y", 0.0)),
            "deadline_ts": int(event.get("deadline_ts", 0)),
            "priority": int(event.get("priority", 1)),
            "state": str(event.get("state", "pending")),
        }

        sim_time_s = int(event.get("sim_time_s", 0))
        # Baseline assignments are triggered by robot.updated events to avoid
        # over-assigning during the job.created burst.

    async def _handle_robot_updated(self, event: dict[str, Any]) -> None:
        """Ingest robot.updated events and trigger dispatch/replan logic."""
        run_id = str(event.get("run_id", ""))
        state = self.states.get(run_id)
        if state is None:
            return

        required = ("robot_id", "state", "sim_time_s")
        missing = [k for k in required if k not in event]
        if missing:
            logger.warning(
                "dropping malformed robot.updated run_id=%s missing=%s payload=%s",
                run_id,
                ",".join(missing),
                event,
            )
            return

        try:
            robot_id = int(event["robot_id"])
            new_state = str(event["state"])
            sim_time_s = int(event["sim_time_s"])
        except (TypeError, ValueError):
            logger.warning("dropping malformed robot.updated run_id=%s payload=%s", run_id, event)
            return

        pending_job_id = state.pending_assignments.get(robot_id)
        if pending_job_id:
            current_job_id = event.get("current_job_id")
            if current_job_id == pending_job_id or new_state != "idle":
                state.pending_assignments.pop(robot_id, None)
            elif new_state == "idle" and not current_job_id:
                logger.debug(
                    "ignoring idle robot.updated while assignment pending run_id=%s robot_id=%s job_id=%s",
                    run_id,
                    robot_id,
                    pending_job_id,
                )
                return

        prev_state = None
        if robot_id in state.robots:
            prev_state = state.robots[robot_id].get("state")

        state.robots[robot_id] = {
            "id": robot_id,
            "x": float(event.get("x", state.robots.get(robot_id, {}).get("x", 0.0))),
            "y": float(event.get("y", state.robots.get(robot_id, {}).get("y", 0.0))),
            "speed": float(event.get("speed", state.robots.get(robot_id, {}).get("speed", 1.0))),
            "battery": float(event.get("battery", state.robots.get(robot_id, {}).get("battery", 100.0))),
            "state": new_state,
            "current_job_id": event.get("current_job_id"),
            "sim_time_s": sim_time_s,
        }

        if new_state == "charging" or float(state.robots[robot_id].get("battery", 0.0)) < settings.battery_threshold:
            if state.planned_queues.get(robot_id):
                state.planned_queues[robot_id] = []
            state.pending_assignments.pop(robot_id, None)

        if state.mode == "baseline":
            await self._dispatch_baseline_once_per_tick(state, sim_time_s=sim_time_s)
            return

        # GA mode
        robot_ok = new_state == "idle" and float(state.robots[robot_id].get("battery", 0.0)) >= settings.battery_threshold
        await self._emit_planned_for_idle_robot(state, robot_id=robot_id, sim_time_s=sim_time_s)

        if (
            settings.ga_replan_interval_s > 0
            and state.next_periodic_replan_sim_s is not None
            and sim_time_s >= state.next_periodic_replan_sim_s
            and self._has_pending_jobs(state)
            and not state.optimizer_in_flight
        ):
            await self._replan_ga(state, sim_time_s=sim_time_s, reason="periodic")
            while state.next_periodic_replan_sim_s is not None and state.next_periodic_replan_sim_s <= sim_time_s:
                state.next_periodic_replan_sim_s += settings.ga_replan_interval_s

        transitioned_to_idle = prev_state != "idle" and new_state == "idle"
        queue_empty = len(state.planned_queues.get(robot_id, [])) == 0
        if (
            transitioned_to_idle
            and queue_empty
            and self._has_pending_jobs(state)
            and not state.optimizer_in_flight
        ):
            await self._replan_ga(state, sim_time_s=sim_time_s, reason="idle_gap")

        if (
            not robot_ok
            and self._has_pending_jobs(state)
            and not state.optimizer_in_flight
            and state.planned_queues.get(robot_id)
        ):
            await self._replan_ga(state, sim_time_s=sim_time_s, reason="battery_guard")

    def _pending_jobs(self, state: RunState) -> list[dict[str, Any]]:
        """Return deterministically ordered pending jobs for dispatch."""
        pending: list[dict[str, Any]] = []
        for job in state.jobs.values():
            job_state = str(job.get("state", "pending"))
            if job_state not in {"pending", "unassigned"}:
                continue
            if job["id"] in state.assigned_jobs:
                continue
            pending.append(job)
        pending.sort(key=lambda j: (int(j.get("deadline_ts", 0)), -int(j.get("priority", 1)), j["id"]))
        return pending

    def _has_pending_jobs(self, state: RunState) -> bool:
        """True if there are any pending/unassigned jobs."""
        return len(self._pending_jobs(state)) > 0

    async def _dispatch_baseline(self, state: RunState, sim_time_s: int) -> None:
        """Run baseline heuristic and emit assignments."""
        assignments = compute_baseline_assignments(
            robots=state.robots,
            jobs=state.jobs,
            already_assigned=state.assigned_jobs,
            blocked_robots=set(state.pending_assignments.keys()),
            battery_threshold=settings.battery_threshold,
        )
        for assignment in assignments:
            await self._emit_assignment(state, assignment["job_id"], assignment["robot_id"], sim_time_s, assignment["reason"])

    async def _dispatch_baseline_once_per_tick(self, state: RunState, sim_time_s: int) -> None:
        """Ensure baseline runs at most once per sim_time_s to avoid flooding."""
        if state.last_baseline_dispatch_sim_s == sim_time_s:
            return
        async with state.baseline_lock:
            if state.last_baseline_dispatch_sim_s == sim_time_s:
                return
            state.last_baseline_dispatch_sim_s = sim_time_s
            await self._dispatch_baseline(state, sim_time_s=sim_time_s)

    async def _replan_ga(self, state: RunState, sim_time_s: int, reason: str) -> None:
        """Call optimizer-service to compute GA plan and update queues."""
        async with state.lock:
            if state.optimizer_in_flight:
                return
            state.optimizer_in_flight = True
        try:
            pending = self._pending_jobs(state)
            if not pending:
                return
            robots = [
                r
                for r in state.robots.values()
                if r.get("state") != "charging" and float(r.get("battery", 0.0)) >= settings.battery_threshold
            ]
            robots = sorted(robots, key=lambda r: int(r["id"]))
            if not robots:
                return

            plan = await request_ga_plan(
                optimizer_url=settings.optimizer_url,
                run_id=state.run_id,
                seed=state.seed,
                scale=state.scale,
                sim_time_s=sim_time_s,
                robots=robots,
                pending_jobs=pending,
            )

            new_queues: dict[int, list[str]] = {int(r["id"]): [] for r in robots}
            for item in plan:
                job_id = item["job_id"]
                robot_id = int(item["robot_id"])
                if job_id in state.assigned_jobs:
                    continue
                if job_id not in state.jobs:
                    continue
                if state.jobs[job_id].get("state") not in {"pending", "unassigned"}:
                    continue
                if robot_id not in new_queues:
                    continue
                if job_id not in new_queues[robot_id]:
                    new_queues[robot_id].append(job_id)

            state.planned_queues = new_queues
            logger.info(
                "ga replan run_id=%s reason=%s sim_time_s=%s pending=%s",
                state.run_id,
                reason,
                sim_time_s,
                len(pending),
            )
            await self._emit_planned_for_idle_robots(state, sim_time_s=sim_time_s)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ga replan failed run_id=%s reason=%s err=%s", state.run_id, reason, exc)
        finally:
            state.optimizer_in_flight = False

    async def _emit_planned_for_idle_robots(self, state: RunState, sim_time_s: int) -> None:
        """Emit assignments for any idle robots with queued GA plans."""
        for robot_id in sorted(state.robots.keys()):
            await self._emit_planned_for_idle_robot(state, robot_id=robot_id, sim_time_s=sim_time_s)

    async def _emit_planned_for_idle_robot(self, state: RunState, robot_id: int, sim_time_s: int) -> None:
        """Assign the next planned job to a specific idle robot."""
        robot = state.robots.get(robot_id)
        if not robot or robot.get("state") != "idle":
            return
        if float(robot.get("battery", 0.0)) < settings.battery_threshold:
            return
        queue = state.planned_queues.get(robot_id, [])
        while queue:
            job_id = queue.pop(0)
            job = state.jobs.get(job_id)
            if job is None:
                continue
            if job_id in state.assigned_jobs:
                continue
            if job.get("state") not in {"pending", "unassigned"}:
                continue
            await self._emit_assignment(state, job_id=job_id, robot_id=robot_id, sim_time_s=sim_time_s, reason="ga_planned")
            break

    async def _emit_assignment(self, state: RunState, job_id: str, robot_id: int, sim_time_s: int, reason: str) -> None:
        """Publish a job.assigned event with idempotency checks."""
        if self.exchange is None:
            return

        async with state.assign_lock:
            if job_id in state.assigned_jobs:
                return

            job = state.jobs.get(job_id)
            if not job:
                return
            if job.get("state") not in {"pending", "unassigned"}:
                return

            event_id_source = f"{state.run_id}:{job_id}:{robot_id}:{sim_time_s}"
            event_id = hashlib.sha1(event_id_source.encode("utf-8")).hexdigest()

            payload = {
                "event_id": event_id,
                "event_type": "job.assigned",
                "run_id": state.run_id,
                "mode": state.mode,
                "seed": state.seed,
                "scale": state.scale,
                "sim_time_s": int(sim_time_s),
                "job_id": job_id,
                "robot_id": int(robot_id),
                "reason": reason,
                "idempotency_key": f"{state.run_id}:{job_id}",
                "ts_utc": datetime.now(timezone.utc).isoformat(),
            }
            await publish_event(self.exchange, "job.assigned", payload)
            state.assigned_jobs.add(job_id)
            state.jobs[job_id]["state"] = "assigned"
            robot = state.robots.get(robot_id)
            if robot is not None:
                robot["state"] = "moving_to_pickup"
                robot["current_job_id"] = job_id
            state.pending_assignments[robot_id] = job_id
            logger.info(
                "assignment emitted run_id=%s mode=%s job_id=%s robot_id=%s reason=%s",
                state.run_id,
                state.mode,
                job_id,
                robot_id,
                reason,
            )


async def main() -> None:
    worker = DispatcherWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
