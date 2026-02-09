# Configuration Reference

This document lists environment variables referenced in code, their purpose, and which services use them. Example values are from `.env.example` or code defaults.

## Fleet / Scenario

- `FLEET_SCALE` (fleet-api-go, sim-runner, dispatcher-worker, viewer-service)
  - Default: `demo`
  - Values: `mini|small|demo|large`
- `FLEET_SEED` (fleet-api-go, sim-runner, dispatcher-worker, viewer-service)
  - Default: `42`
- `FLEET_MODE` (fleet-api-go, sim-runner, dispatcher-worker, viewer-service)
  - Default: `baseline`
- `FLEET_ROBOTS` (fleet-api-go, sim-runner, dispatcher-worker, viewer-service, optimizer-service)
  - Default: `0`
  - If both `FLEET_ROBOTS` and `FLEET_JOBS` > 0, they override scale sizes.
- `FLEET_JOBS` (fleet-api-go, sim-runner, dispatcher-worker, viewer-service, optimizer-service)
  - Default: `0`

### Run-scoped API overrides (not env vars)

- `POST /runs` and `POST /api/runs` accept optional `robots` + `jobs`.
- If provided together, those values override scale counts for that run only.
- `GET /runs/compare` can be filtered with matching `robots` + `jobs`.

## GA / Optimizer

- `GA_REPLAN_INTERVAL_S` (fleet-api-go, sim-runner, dispatcher-worker, viewer-service)
  - Default: `0` (periodic replanning disabled)
- `GA_POPULATION_SIZE` (optimizer-service)
  - Default: `64`
- `GA_GENERATIONS` (optimizer-service)
  - Default: `80`
- `GA_ELITE_SIZE` (optimizer-service)
  - Default: `4`
- `GA_MUTATION_RATE` (optimizer-service)
  - Default: `0.10`
- `GA_CROSSOVER_RATE` (optimizer-service)
  - Default: `0.90`

## Simulation + Physics

- `SIM_TICK_HZ` (sim-runner)
  - Default: `5`
- `TELEMETRY_HZ` (sim-runner)
  - Default: `1`
  - Note: currently unused; telemetry emits once per `sim_time_s`.
- `WORLD_SIZE` (sim-runner)
  - Default: `100`
- `MAX_SIM_SECONDS` (sim-runner)
  - Default: `3600`
- `SERVICE_TIME_S` (sim-runner, optimizer-service)
  - Default: `5`
- `ROBOT_SPEED_MIN` / `ROBOT_SPEED_MAX` (sim-runner)
  - Default: `1.0` / `2.0`
- `BATTERY_THRESHOLD` (dispatcher-worker)
  - Default: `20`
- `CHARGE_RATE` (sim-runner)
  - Default: `5`
- `CHARGE_RESUME_THRESHOLD` (sim-runner)
  - Default: `20`

## Connectivity

- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`
  - Used by: fleet-api-go, sim-runner, dispatcher-worker
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASS`
  - Used by: fleet-api-go, sim-runner, dispatcher-worker, viewer-service, ros2-robot-agents
- `FLEET_API_URL`
  - Used by: viewer-service (default `http://fleet-api:8000`)
- `OPTIMIZER_URL`
  - Used by: dispatcher-worker (default `http://optimizer-service:8002`)
- `OPTIMIZER_HOST`
  - Used by: optimizer-service (default `0.0.0.0`)

## Ports

- `FLEET_API_PORT` (fleet-api-go)
- `OPTIMIZER_PORT` (optimizer-service)
- `VIEWER_PORT` (viewer-service)

## Service Names (docker-compose)

- `mysql`
- `rabbitmq`
- `fleet-api`
- `optimizer-service`
- `dispatcher-worker`
- `sim-runner`
- `viewer-service`
- `ros2-robot-agents`
- `adminer`
