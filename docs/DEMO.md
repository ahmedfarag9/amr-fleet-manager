# 5-7 Minute Interview Demo Script

## 0:00 - 0:45 Setup

```bash
cp .env.example .env
docker compose up --build
```

Say:

- "This is a deterministic AMR fleet manager demo. Same seed and scale produce comparable baseline and GA runs."
- "All events flow through RabbitMQ topic exchange `amr.events`."

## 0:45 - 2:00 Show UI + config

Open http://localhost:8080 and point out:

- Scale, seed, and `GA_REPLAN_INTERVAL_S` from `/api/config`
- Run buttons: Baseline and GA
- Live canvas + metrics + compare table

Say:

- "Periodic GA replanning is OFF by default (`GA_REPLAN_INTERVAL_S=0`) for demo safety."
- "Robots charge when battery hits 0 and resume at `CHARGE_RESUME_THRESHOLD`."

## 2:00 - 3:15 Baseline run

Click **Run Baseline**.

Say:

- "Fleet API persists the run and emits `run.started`."
- "Sim runner generates deterministic jobs/robots and publishes snapshots every sim tick."
- "Dispatcher applies EDF + nearest-robot baseline assignments."

Wait for metrics panel.

## 3:15 - 4:30 GA run

Click **Run GA**.

Say:

- "GA optimizer computes deterministic assignments with fixed seed."
- "GA replans at run start and only on guarded idle-gap trigger unless periodic replanning is enabled."

Wait for metrics panel and click **Compare Last Two**.

## 4:30 - 5:30 RabbitMQ + DB checks

RabbitMQ UI: http://localhost:15672

Say:

- "Queues are separated per consumer role, all bound to `amr.events`."

Optional DB check via Adminer: http://localhost:8081

- Server: `mysql`
- User: `amr`
- Password: `amrpass`
- Database: `amr_fleet`

Show `runs`, `run_metrics`, `jobs`, `telemetry`.

## 5:30 - 6:45 ROS2 bridge

```bash
docker compose exec ros2-robot-agents bash
ros2 topic list
ros2 topic echo /robot_1/telemetry
```

Say:

- "ROS2 node consumes `telemetry.received` and republishes per-robot topics as `std_msgs/String` JSON."

## 6:45 - 7:00 Close

Say:

- "The deterministic contract is enforced by seeded random, stable tie-breakers, simulation-time logic, and strict exact-equality determinism tests."
- "Telemetry is emitted once per sim second; `TELEMETRY_HZ` is currently unused."
