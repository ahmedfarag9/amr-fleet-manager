from __future__ import annotations

"""
File: services/sim-runner-py/app/main.py
Purpose: Simulation runner that consumes run.started and executes deterministic runs.
Key responsibilities:
- Generate deterministic scenarios and publish job/robot events.
- Apply job assignments and emit snapshots/telemetry.
- Persist jobs, telemetry, and metrics to MySQL.
Key entrypoints:
- SimRunner.run()
Config/env vars:
- FLEET_* (seed/scale/mode), SIM_TICK_HZ, WORLD_SIZE
- SERVICE_TIME_S, MAX_SIM_SECONDS, ROBOT_SPEED_* , CHARGE_*
- RABBITMQ_* , MYSQL_*
"""

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any

import aio_pika

from app import db
from app.mq import connect, publish_event, setup_topology
from app.settings import rabbit_url, settings
from app.sim.engine import Assignment, SimulationEngine
from app.sim.entities import SimulationState
from app.sim.metrics import compute_metrics
from app.sim.world import generate_scenario

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s sim-runner %(message)s")
logger = logging.getLogger("sim-runner")


class SimRunner:
    """RabbitMQ-driven simulation runner for AMR scenarios."""
    def __init__(self) -> None:
        self.exchange: aio_pika.abc.AbstractExchange | None = None
        self.assignment_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self.run_tasks: dict[str, asyncio.Task] = {}

    async def run(self) -> None:
        """Connect to RabbitMQ, declare queues, and begin consuming."""
        connection = await connect(rabbit_url())
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=200)

        exchange, q_run_started, q_job_assigned = await setup_topology(channel, settings.exchange_name)
        self.exchange = exchange

        await q_run_started.consume(self._on_run_started)
        await q_job_assigned.consume(self._on_job_assigned)

        logger.info("sim-runner started")
        await asyncio.Future()

    async def _on_run_started(self, message: aio_pika.IncomingMessage) -> None:
        """Handle run.started by creating a simulation task."""
        try:
            event = json.loads(message.body.decode("utf-8"))
            run_id = str(event.get("run_id", ""))
            if not run_id:
                logger.warning("run.started missing run_id")
                return
            if run_id in self.run_tasks:
                logger.warning("run already active run_id=%s", run_id)
                return

            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            self.assignment_queues[run_id] = queue
            task = asyncio.create_task(self._simulate_run(event, queue))
            self.run_tasks[run_id] = task
            task.add_done_callback(lambda _task, rid=run_id: self._cleanup_run(rid))
        except Exception as exc:  # noqa: BLE001
            logger.exception("run.started handler error: %s", exc)
        finally:
            await message.ack()

    async def _on_job_assigned(self, message: aio_pika.IncomingMessage) -> None:
        """Queue job.assigned messages for deterministic processing."""
        try:
            event = json.loads(message.body.decode("utf-8"))
            run_id = str(event.get("run_id", ""))
            queue = self.assignment_queues.get(run_id)
            if queue is None:
                return
            await queue.put(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("job.assigned handler error: %s", exc)
        finally:
            await message.ack()

    def _cleanup_run(self, run_id: str) -> None:
        """Remove run state when a simulation completes."""
        self.assignment_queues.pop(run_id, None)
        self.run_tasks.pop(run_id, None)

    async def _simulate_run(self, event: dict[str, Any], assignment_queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Run a deterministic simulation loop for a single run."""
        run_id = str(event["run_id"])
        mode = str(event.get("mode", settings.fleet_mode))
        seed = int(event.get("seed", settings.fleet_seed))
        scale = str(event.get("scale", settings.fleet_scale))
        robots_override = event.get("robots")
        jobs_override = event.get("jobs")
        if robots_override is not None:
            robots_override = int(robots_override)
        if jobs_override is not None:
            jobs_override = int(jobs_override)
        logger.info(
            "sim started run_id=%s mode=%s seed=%s scale=%s robots=%s jobs=%s",
            run_id,
            mode,
            seed,
            scale,
            robots_override,
            jobs_override,
        )

        try:
            robots, jobs, scenario_hash = generate_scenario(
                seed=seed,
                scale=scale,
                world_size=settings.world_size,
                robots_override=robots_override,
                jobs_override=jobs_override,
            )
            db.update_run_scenario_hash(run_id, scenario_hash)

            state = SimulationState(run_id=run_id, mode=mode, seed=seed, scale=scale, robots=robots, jobs=jobs)

            robot_events: list[dict[str, Any]] = []

            def robot_update_sink(payload: dict[str, Any]) -> None:
                robot_events.append(payload)

            engine = SimulationEngine(
                state=state,
                tick_hz=settings.sim_tick_hz,
                service_time_s=settings.service_time_s,
                max_sim_seconds=settings.max_sim_seconds,
                robot_update_sink=robot_update_sink,
                emit_position_updates=True,
                charge_rate=settings.charge_rate,
                charge_resume_threshold=settings.charge_resume_threshold,
            )

            # Publish generated jobs at sim start.
            for job in sorted(jobs, key=lambda item: item.id):
                payload = {
                    "event_id": self._event_id(run_id, "job.created", job.id, 0),
                    "event_type": "job.created",
                    "run_id": run_id,
                    "mode": mode,
                    "seed": seed,
                    "scale": scale,
                    "sim_time_s": 0,
                    "job_id": job.id,
                    "pickup_x": job.pickup_x,
                    "pickup_y": job.pickup_y,
                    "dropoff_x": job.dropoff_x,
                    "dropoff_y": job.dropoff_y,
                    "deadline_ts": job.deadline_ts,
                    "priority": job.priority,
                    "state": job.state,
                    "ts_utc": datetime.now(timezone.utc).isoformat(),
                }
                await publish_event(self.exchange, "job.created", payload)
                db.upsert_job(run_id, asdict(job))

            engine.emit_initial_robot_updates()
            await self._flush_robot_updates(run_id, mode, seed, scale, robot_events)

            last_telemetry_sim_s = -1
            previous_job_states = {job.id: job.state for job in jobs}

            while not engine.should_stop():
                current_sim_time_s = engine.current_sim_time_s()

                # Drain all assignment messages available for deterministic processing at this sim tick.
                while not assignment_queue.empty():
                    assignment_event = assignment_queue.get_nowait()
                    assignment = Assignment(
                        job_id=str(assignment_event.get("job_id", "")),
                        robot_id=int(assignment_event.get("robot_id", 0)),
                    )
                    applied = engine.apply_assignment(assignment)
                    if applied:
                        job = next(j for j in jobs if j.id == assignment.job_id)
                        db.upsert_job(run_id, asdict(job))

                engine.step()
                sim_time_s = engine.current_sim_time_s()

                await self._flush_robot_updates(run_id, mode, seed, scale, robot_events)

                await publish_event(
                    self.exchange,
                    "snapshot.tick",
                    {
                        "event_id": self._event_id(run_id, "snapshot.tick", "snapshot", sim_time_s),
                        "event_type": "snapshot.tick",
                        "run_id": run_id,
                        "mode": mode,
                        "seed": seed,
                        "scale": scale,
                        "sim_time_s": int(sim_time_s),
                        "snapshot": engine.snapshot(),
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )

                telemetry_rows: list[dict[str, Any]] = []
                if sim_time_s != last_telemetry_sim_s:
                    for robot in sorted(robots, key=lambda r: r.id):
                        telemetry_payload = {
                            "event_id": self._event_id(run_id, "telemetry.received", f"r{robot.id}", sim_time_s),
                            "event_type": "telemetry.received",
                            "run_id": run_id,
                            "mode": mode,
                            "seed": seed,
                            "scale": scale,
                            "sim_time_s": int(sim_time_s),
                            "robot_id": robot.id,
                            "state": robot.state,
                            "x": round(robot.x, 3),
                            "y": round(robot.y, 3),
                            "battery": round(robot.battery, 3),
                            "current_job_id": robot.current_job_id,
                            "ts_utc": datetime.now(timezone.utc).isoformat(),
                        }
                        await publish_event(self.exchange, "telemetry.received", telemetry_payload)
                        telemetry_rows.append(telemetry_payload)
                    last_telemetry_sim_s = sim_time_s

                db.insert_telemetry_batch(run_id, telemetry_rows)

                for job in jobs:
                    if previous_job_states.get(job.id) != job.state:
                        previous_job_states[job.id] = job.state
                        db.upsert_job(run_id, asdict(job))
                        if job.state == "completed":
                            await publish_event(
                                self.exchange,
                                "job.completed",
                                {
                                    "event_id": self._event_id(run_id, "job.completed", job.id, sim_time_s),
                                    "event_type": "job.completed",
                                    "run_id": run_id,
                                    "mode": mode,
                                    "seed": seed,
                                    "scale": scale,
                                    "sim_time_s": int(sim_time_s),
                                    "job_id": job.id,
                                    "robot_id": job.assigned_robot_id,
                                    "lateness_s": job.lateness_s,
                                    "ts_utc": datetime.now(timezone.utc).isoformat(),
                                },
                            )

                await asyncio.sleep(1.0 / settings.sim_tick_hz)

            engine.finalize()
            for job in jobs:
                db.upsert_job(run_id, asdict(job))
                if job.state == "failed":
                    await publish_event(
                        self.exchange,
                        "job.failed",
                        {
                            "event_id": self._event_id(run_id, "job.failed", job.id, engine.current_sim_time_s()),
                            "event_type": "job.failed",
                            "run_id": run_id,
                            "mode": mode,
                            "seed": seed,
                            "scale": scale,
                            "sim_time_s": int(engine.current_sim_time_s()),
                            "job_id": job.id,
                            "robot_id": job.assigned_robot_id,
                            "lateness_s": job.lateness_s,
                            "ts_utc": datetime.now(timezone.utc).isoformat(),
                        },
                    )

            metrics = compute_metrics(jobs, robots)
            db.insert_metrics(run_id, metrics)
            db.complete_run(run_id, "completed")

            logger.info("run completed run_id=%s metrics=%s", run_id, metrics)
            await publish_event(
                self.exchange,
                "run.completed",
                {
                    "event_id": self._event_id(run_id, "run.completed", "run", engine.current_sim_time_s()),
                    "event_type": "run.completed",
                    "run_id": run_id,
                    "mode": mode,
                    "seed": seed,
                    "scale": scale,
                    "sim_time_s": int(engine.current_sim_time_s()),
                    "scenario_hash": scenario_hash,
                    "metrics": metrics,
                    "ts_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("run failed run_id=%s err=%s", run_id, exc)
            db.complete_run(run_id, "failed", error_message=str(exc))
            if self.exchange is not None:
                await publish_event(
                    self.exchange,
                    "run.completed",
                    {
                        "event_id": self._event_id(run_id, "run.completed", "run", 0),
                        "event_type": "run.completed",
                        "run_id": run_id,
                        "mode": mode,
                        "seed": seed,
                        "scale": scale,
                        "sim_time_s": 0,
                        "status": "failed",
                        "error": str(exc),
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )

    async def _flush_robot_updates(
        self,
        run_id: str,
        mode: str,
        seed: int,
        scale: str,
        robot_events: list[dict[str, Any]],
    ) -> None:
        """Publish buffered robot.updated events to RabbitMQ."""
        if not robot_events:
            return
        if self.exchange is None:
            return

        while robot_events:
            item = robot_events.pop(0)
            payload = {
                "event_id": self._event_id(run_id, "robot.updated", f"robot_{item['robot_id']}", int(item["sim_time_s"])),
                "event_type": "robot.updated",
                "run_id": run_id,
                "mode": mode,
                "seed": seed,
                "scale": scale,
                # Required deterministic fields:
                "robot_id": int(item["robot_id"]),
                "state": item["state"],
                "sim_time_s": int(item["sim_time_s"]),
                "x": item["x"],
                "y": item["y"],
                "speed": item["speed"],
                "battery": item["battery"],
                "current_job_id": item.get("current_job_id"),
                "ts_utc": datetime.now(timezone.utc).isoformat(),
            }
            await publish_event(self.exchange, "robot.updated", payload)

    @staticmethod
    def _event_id(run_id: str, event_type: str, entity_id: str, sim_time_s: int) -> str:
        raw = f"{run_id}:{event_type}:{entity_id}:{sim_time_s}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def main() -> None:
    runner = SimRunner()
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
