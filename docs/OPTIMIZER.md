# Optimizer

## Deterministic GA Model

- Chromosome: vector of robot indices, one gene per ordered pending job.
- Job ordering: `(deadline_ts, -priority, job_id)`.
- Robot ordering: `robot_id` ascending.
- Seeded RNG only (`random.Random(seed)`), no unseeded randomness.

## Fitness (minimize)

Per assigned job penalty combines:

- **lateness penalty**: `lateness * 1000`
- **distance penalty**: `distance * 2`
- **priority penalty**: `(6 - priority) * 3`
- **battery penalty**:
  - `< 0` battery: `500 + abs(battery_after) * 100`
  - `< 10` battery: `200`
- **load-balance penalty**: `robot_job_count^2 * 30` (discourages all jobs on one robot)

## Constraints / Gating

- Dispatcher filters out robots that are `charging` or below `BATTERY_THRESHOLD` before calling the optimizer.
- Optimizer still scores battery violations but only sees eligible robots from the dispatcher.

## Operators

- Tournament selection (stable tie-break)
- One-point crossover
- Point mutation
- Elitism

## Replanning Policy

- Initial optimize at run start in GA mode.
- Periodic replanning default is disabled for demo reliability:
  - `.env.example` sets `GA_REPLAN_INTERVAL_S=0`.
- Enable periodic replanning by setting `GA_REPLAN_INTERVAL_S>0`; cadence uses `sim_time_s`.
- Idle-gap replan only when:
  - robot transitions into `idle`
  - that robot planned queue is empty
  - pending jobs exist (`pending|unassigned`)
  - no optimizer call is in-flight

## Configuration

From `.env` / `.env.example`:

- `GA_POPULATION_SIZE`
- `GA_GENERATIONS`
- `GA_ELITE_SIZE`
- `GA_MUTATION_RATE`
- `GA_CROSSOVER_RATE`
- `SERVICE_TIME_S`

## Run Optimizer Standalone

```bash
curl -sS -X POST http://localhost:8002/optimize \
  -H 'Content-Type: application/json' \
  -d '{"run_id":"demo","seed":42,"scale":"demo","mode":"ga","sim_time_s":0,"robots":[],"pending_jobs":[]}' | jq
```

## Determinism Guarantees

- Stable sorting before and after optimization.
- Simulation-time triggers only, never wall-clock logic.
- Tests assert exact equality for deterministic outputs/metrics.
