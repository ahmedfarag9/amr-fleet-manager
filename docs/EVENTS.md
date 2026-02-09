# Events

Exchange: `amr.events` (topic, durable)

## Routing Keys

- `run.started`
- `run.completed`
- `job.created`
- `job.assigned`
- `job.completed`
- `job.failed`
- `robot.updated`
- `telemetry.received`
- `snapshot.tick`

## Producers / Consumers

| Routing Key | Producers | Consumers |
| --- | --- | --- |
| `run.started` | fleet-api-go | sim-runner, dispatcher-worker |
| `run.completed` | sim-runner | viewer-service |
| `job.created` | sim-runner | dispatcher-worker |
| `job.assigned` | dispatcher-worker | sim-runner |
| `job.completed` | sim-runner | (optional external) |
| `job.failed` | sim-runner | (optional external) |
| `robot.updated` | sim-runner | dispatcher-worker |
| `telemetry.received` | sim-runner | ros2-robot-agents |
| `snapshot.tick` | sim-runner | viewer-service |

## Common Envelope Fields

Most events include:

- `event_id`
- `event_type`
- `run_id`
- `mode`
- `seed`
- `scale`
- `sim_time_s`
- `ts_utc`

## `run.started`

Optional per-run size overrides:

- `robots` (int, optional)
- `jobs` (int, optional)

When both are present, sim-runner uses them for that run instead of scale defaults.

## `robot.updated` (Mandatory Contract)

Required keys (must exist on every message):

- `robot_id` (int)
- `state` (string)
- `sim_time_s` (int from simulation clock)

Optional:

- `x`, `y`, `speed`, `battery`, `current_job_id`

Example:
```json
{
  "event_id": "...",
  "event_type": "robot.updated",
  "run_id": "run-1",
  "mode": "ga",
  "seed": 42,
  "scale": "demo",
  "robot_id": 1,
  "state": "idle",
  "sim_time_s": 12,
  "x": 20.5,
  "y": 33.1,
  "battery": 91.2,
  "current_job_id": null,
  "ts_utc": "2026-01-01T00:00:00Z"
}
```

Malformed handling (consumer-side):

- missing required keys -> log + ACK-drop
- no requeue

## `job.assigned`

```json
{
  "event_id": "...",
  "event_type": "job.assigned",
  "run_id": "run-1",
  "job_id": "job_17",
  "robot_id": 2,
  "sim_time_s": 9,
  "reason": "baseline_edf_nearest",
  "idempotency_key": "run-1:job_17"
}
```

## `snapshot.tick`

- Emitted once per simulation tick.
- Tick cadence is `SIM_TICK_HZ` (no separate snapshot rate).

```json
{
  "event_type": "snapshot.tick",
  "run_id": "run-1",
  "sim_time_s": 21,
  "snapshot": {
    "robots": [],
    "jobs": []
  }
}
```

## `telemetry.received`

- Emitted once per simulation second (`sim_time_s` changes).
- `TELEMETRY_HZ` is not currently used by the sim-runner.

```json
{
  "event_type": "telemetry.received",
  "run_id": "run-1",
  "sim_time_s": 21,
  "robot_id": 1,
  "state": "moving_to_dropoff",
  "x": 19.1,
  "y": 24.6,
  "battery": 87.3
}
```
