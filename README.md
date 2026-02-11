# AMR Fleet Manager

Deterministic (not random/stochastic - same result for same i/p), dockerized AMR (Autonomous Mobile Robot) fleet simulation monorepo with two dispatch modes on the same scenario:

- `baseline`: Earliest deadline first (EDF) or least time to go + nearest idle robot heuristic
- `ga`: deterministic Genetic Algorithm assignment planner

The stack is fully local and event-driven using RabbitMQ as the only bus.

## Quickstart

1. Copy env file:
```bash
cp .env.example .env
```
2. Start everything:
```bash
docker compose up --build
```
3. Open dashboard:
- Viewer: http://localhost:8080
- RabbitMQ Management: http://localhost:15672
- Fleet API: http://localhost:8000
- Optimizer API: http://localhost:8002
- Adminer (optional): http://localhost:8081

## Determinism Defaults

- `FLEET_SEED=42`
- `FLEET_SCALE=demo`
- `FLEET_MODE=baseline`
- `GA_REPLAN_INTERVAL_S=0` (periodic GA replanning OFF by default for operational reliability)

Enable periodic GA replanning by setting `GA_REPLAN_INTERVAL_S>0`.

Scale presets:

- `mini` = 5 robots, 5 jobs
- `small` = 5 robots, 25 jobs
- `demo` = 10 robots, 50 jobs
- `large` = 20 robots, 100 jobs

You can also override fleet size directly from `.env`:

- `FLEET_ROBOTS=<int>`
- `FLEET_JOBS=<int>`

If both are greater than zero, they override robot/job counts for all scales.

You can also pass run-scoped overrides from the UI/API request:

- `POST /api/runs` payload can include `robots` and `jobs`.
- This lets you change scenario size per run without editing `.env`.

Speed knobs:

- `ROBOT_SPEED_MIN`
- `ROBOT_SPEED_MAX`

These control the random speed range assigned to robots at scenario generation time.

## Core Flow

1. UI triggers run (`baseline` or `ga`) through viewer backend.
2. Viewer calls `fleet-api POST /runs`.
3. Fleet API stores run and publishes `run.started`.
4. Sim runner consumes `run.started`, generates deterministic scenario, publishes `job.created` and `robot.updated`.
5. Dispatcher consumes job/robot events and emits `job.assigned`.
6. Sim runner applies assignments, emits snapshots/telemetry/events, stores metrics, and publishes `run.completed`.

## Mandatory `robot.updated` Contract

Every `robot.updated` message includes required keys:

- `robot_id`
- `state`
- `sim_time_s` (integer simulation time from tick clock)

Emission policy:

- always on state transitions
- optional position updates throttled to `<=1 Hz` per robot

Consumer policy for malformed `robot.updated`:

- log warning
- ACK + drop
- no requeue

## Repo Docs

- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/EVENTS.md`
- `docs/OPTIMIZER.md`
- `docs/DB_SCHEMA.md`
- `docs/RUNBOOK.md`
- `docs/ros-commands.md`

## Helpful Commands

```bash
make up
make down
make logs
make demo-baseline
make demo-ga
```

## AMR Fleet Manager Visuals

- Sim Time: 110s is simulation clock (not wall clock).
- Brown squares = job pickup points (pending/uncompleted jobs).
- Gray X = job dropoff points.
- Robot circles with R# labels = robot positions.
- Battery bars under robots = current battery.
- Blue robot (R1) = non-idle robot (currently assigned/moving).
- Green robots = idle robots.
- Dashed line from R1 = current route visualization (robot -> pickup -> dropoff).
- A green square among pickups indicates a completed job marker in this UI.

## How It Works (End-to-End)

1. The UI triggers a run through `viewer-service` (`POST /api/runs`).
2. `viewer-service` proxies to `fleet-api` (`POST /runs`).
3. `fleet-api` persists the run and publishes `run.started` to RabbitMQ.
4. `sim-runner` generates a deterministic scenario from `(seed, scale)` and emits `job.created` + `robot.updated`.
5. `dispatcher-worker` emits `job.assigned` (baseline or GA) and enforces battery/charging guards.
6. `sim-runner` applies assignments, publishes `snapshot.tick` and `telemetry.received`, and writes metrics to MySQL.
7. `viewer-service` streams snapshots to the browser and polls metrics from `fleet-api`.

## Key Configuration Knobs

- Scenario control: `FLEET_SEED`, `FLEET_SCALE`
- Global overrides: `FLEET_ROBOTS`, `FLEET_JOBS` (both >0)
- GA controls: `GA_REPLAN_INTERVAL_S`, `GA_POPULATION_SIZE`, `GA_GENERATIONS`, `GA_ELITE_SIZE`, `GA_MUTATION_RATE`, `GA_CROSSOVER_RATE`
- Simulation: `SIM_TICK_HZ`, `WORLD_SIZE`, `MAX_SIM_SECONDS`, `SERVICE_TIME_S`
- Robot speeds: `ROBOT_SPEED_MIN`, `ROBOT_SPEED_MAX`
- Battery/charging: `BATTERY_THRESHOLD`, `CHARGE_RATE`, `CHARGE_RESUME_THRESHOLD`

For the full list, see `docs/CONFIG.md`.
