# Runbook

## Common Commands

```bash
docker compose ps
docker compose logs -f sim-runner
docker compose logs -f dispatcher-worker
docker compose logs -f viewer-service
```

## Health Endpoints

- fleet-api: `http://localhost:8000/health`
- optimizer-service: `http://localhost:8002/health`
- viewer-service: `http://localhost:8080/health`

## RabbitMQ Issues

Symptoms:

- no snapshots in UI
- no assignments

Checks:

1. RabbitMQ health: `docker compose ps rabbitmq`
2. Management UI: `http://localhost:15672`
3. Confirm exchange `amr.events` and queue bindings.

## MySQL Issues

Symptoms:

- runs fail at start
- metrics missing

Checks:

1. `docker compose logs mysql`
2. Validate `.env` credentials.
3. Connect with Adminer and verify tables exist.
4. If you pulled schema changes, apply migrations (or recreate DB volume):
   `docker compose exec -T mysql mysql -uamr -pamrpass amr_fleet < infra/db/migrations/002_add_run_size_overrides.sql`

Adminer:

- URL: `http://localhost:8081`
- Server: `mysql`
- User: `amr`
- Password: `amrpass`
- Database: `amr_fleet`

## WebSocket Issues

Symptoms:

- dashboard loads but no live movement

Checks:

1. `viewer-service` logs for MQ consumer errors.
2. Browser devtools WS frames on `/ws`.
3. Ensure `snapshot.tick` queue has consumers.

## ROS2 Issues

```bash
docker compose exec ros2-robot-agents bash
ros2 topic list
ros2 topic echo /robot_1/telemetry
```

If no topics:

- check `ros2-robot-agents` logs
- verify telemetry events in RabbitMQ

## Battery + Charging

- Robots stop moving at battery 0 and switch to `charging`.
- Battery increases at `CHARGE_RATE` until `CHARGE_RESUME_THRESHOLD`.
- Dispatcher filters out charging/low-battery robots from GA planning.

## Determinism Checks

- Use same `FLEET_SEED` and `FLEET_SCALE` for baseline and GA.
- Keep `GA_REPLAN_INTERVAL_S` constant across repeated GA runs.
- Compare `scenario_hash` in `runs` table.

## Telemetry Note

- Telemetry is emitted once per simulation second when `sim_time_s` increments.
- `TELEMETRY_HZ` is currently unused by the sim-runner.
