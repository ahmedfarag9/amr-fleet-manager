# DB Schema

Schema is initialized by `infra/db/init.sql` and migrations:

- `infra/db/migrations/001_add_mini_scale.sql` (adds the `mini` scale enum)
- `infra/db/migrations/002_add_run_size_overrides.sql` (adds per-run `robots_count` / `jobs_count`)

## Tables

### `runs`
- `id` VARCHAR(64) PRIMARY KEY
- `mode` ENUM('baseline','ga') NOT NULL
- `seed` INT NOT NULL
- `scale` ENUM('mini','small','demo','large') NOT NULL
- `robots_count` INT NULL
- `jobs_count` INT NULL
- `scenario_hash` VARCHAR(128) NOT NULL
- `status` ENUM('started','completed','failed') NOT NULL DEFAULT 'started'
- `error_message` TEXT NULL
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `started_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `completed_at` TIMESTAMP NULL

### `run_metrics`
- `run_id` VARCHAR(64) PRIMARY KEY (FK -> runs.id)
- `on_time_rate` DOUBLE NOT NULL
- `total_distance` DOUBLE NOT NULL
- `avg_completion_time` DOUBLE NOT NULL
- `max_lateness` DOUBLE NOT NULL
- `completed_jobs` INT NOT NULL
- `failed_jobs` INT NOT NULL
- `total_jobs` INT NOT NULL
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `jobs`
- `id` VARCHAR(64)
- `run_id` VARCHAR(64) (FK -> runs.id)
- `pickup_x`, `pickup_y`, `dropoff_x`, `dropoff_y` DOUBLE NOT NULL
- `deadline_ts` INT NOT NULL
- `priority` INT NOT NULL
- `state` ENUM('pending','unassigned','assigned','in_progress','completed','failed') NOT NULL
- `assigned_robot_id` INT NULL
- `created_sim_ts` INT NOT NULL
- `started_sim_ts` INT NULL
- `completed_sim_ts` INT NULL
- `lateness_s` DOUBLE NULL
- PRIMARY KEY (`id`, `run_id`)

### `telemetry`
- `id` BIGINT AUTO_INCREMENT PRIMARY KEY
- `run_id` VARCHAR(64) (FK -> runs.id)
- `robot_id` INT NOT NULL
- `sim_time_s` INT NOT NULL
- `x`, `y` DOUBLE NOT NULL
- `battery` DOUBLE NOT NULL
- `state` VARCHAR(32) NOT NULL
- `current_job_id` VARCHAR(64) NULL
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `run_events`
- `id` BIGINT AUTO_INCREMENT PRIMARY KEY
- `run_id` VARCHAR(64) (FK -> runs.id)
- `event_type` VARCHAR(64) NOT NULL
- `routing_key` VARCHAR(64) NOT NULL
- `payload_json` JSON NOT NULL
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

> Note: `run_events` is defined but not currently written by any service.

## Indexes

- `idx_telemetry_run_robot_ts` on `telemetry (run_id, robot_id, sim_time_s)`
- `idx_jobs_run_state_deadline` on `jobs (run_id, state, deadline_ts)`
- `idx_runs_status_created` on `runs (status, created_at)`
- `idx_run_metrics_created` on `run_metrics (created_at)`

## Ownership (Writes)

| Table | Writer(s) |
| --- | --- |
| `runs` | fleet-api-go (create), sim-runner (update scenario hash/status) |
| `run_metrics` | sim-runner |
| `jobs` | sim-runner |
| `telemetry` | sim-runner |
| `run_events` | none (reserved) |

## Migrations

- Initialization: `infra/db/init.sql` is executed automatically by the MySQL container.
- Scale enum update: `infra/db/migrations/001_add_mini_scale.sql` ensures `mini` is included in `runs.scale`.

## Example Queries

Latest metrics by mode for a fixed scenario:
```sql
SELECT r.mode, rm.*
FROM run_metrics rm
JOIN runs r ON r.id = rm.run_id
WHERE r.seed = 42 AND r.scale = 'demo' AND r.status = 'completed'
ORDER BY r.completed_at DESC, r.created_at DESC;
```

Jobs at risk:
```sql
SELECT id, deadline_ts, state
FROM jobs
WHERE run_id = 'RUN_ID' AND state IN ('pending','unassigned','assigned')
ORDER BY deadline_ts ASC;
```

Robot telemetry timeline:
```sql
SELECT sim_time_s, x, y, battery, state
FROM telemetry
WHERE run_id = 'RUN_ID' AND robot_id = 1
ORDER BY sim_time_s;
```
