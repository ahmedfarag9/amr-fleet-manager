# API

Ports are defined in `docker-compose.yml` and `.env.example`:

- fleet-api-go: `8000`
- optimizer-service: `8002`
- viewer-service: `8080`

## fleet-api-go (Go, port 8000)

### GET /health
Health check for DB connectivity.

### POST /runs
Create a new simulation run and publish `run.started`.

Request:
```json
{
  "mode": "baseline",
  "seed": 42,
  "scale": "demo",
  "robots": 10,
  "jobs": 50
}
```

Response:
```json
{
  "run_id": "uuid",
  "mode": "baseline",
  "seed": 42,
  "scale": "demo",
  "robots": 10,
  "jobs": 50,
  "status": "started"
}
```

### GET /runs/{id}
Fetch run metadata.

### GET /runs/{id}/metrics
Fetch metrics for a completed run.

### GET /runs/compare?seed=42&scale=demo[&robots=10&jobs=50]
Fetch latest completed baseline + GA metrics for a scenario.

### Example: start a run
```bash
curl -sS -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"mode":"baseline","seed":42,"scale":"demo","robots":10,"jobs":50}' | jq
```

### Example: get metrics
```bash
curl -sS http://localhost:8000/runs/<RUN_ID>/metrics | jq
```

## optimizer-service-py (FastAPI, port 8002)

### GET /health
Simple readiness endpoint.

### POST /optimize
Deterministic GA optimization endpoint.

Request (shape):
```json
{
  "run_id": "uuid",
  "seed": 42,
  "scale": "demo",
  "mode": "ga",
  "sim_time_s": 0,
  "robots": [
    {"id": 1, "x": 0, "y": 0, "speed": 1.0, "battery": 100, "state": "idle"}
  ],
  "pending_jobs": [
    {"id": "job_1", "pickup_x": 1, "pickup_y": 1, "dropoff_x": 2, "dropoff_y": 2, "deadline_ts": 100, "priority": 3, "state": "pending"}
  ]
}
```

Response (shape):
```json
{
  "assignments": [
    {"job_id": "job_1", "robot_id": 1, "score": 123.4}
  ],
  "meta": {"best_score": 123.4, "generations": 80, "population_size": 64, "seed": 42}
}
```

### Example: optimize
```bash
curl -sS -X POST http://localhost:8002/optimize \
  -H 'Content-Type: application/json' \
  -d '{"run_id":"demo","seed":42,"scale":"demo","mode":"ga","sim_time_s":0,"robots":[],"pending_jobs":[]}' | jq
```

## viewer-service-py (FastAPI + UI, port 8080)

### GET /
Dashboard UI (HTML + JS + Canvas).

### GET /health
Readiness endpoint.

### GET /api/config
Returns default mode/seed/scale and the computed scale map.

### POST /api/runs
Proxy to `fleet-api-go POST /runs`.
Supports optional run-scoped overrides: `robots`, `jobs`.

### GET /api/runs/{id}/metrics
Proxy to `fleet-api-go GET /runs/{id}/metrics`.

### GET /api/runs/compare
Proxy to `fleet-api-go GET /runs/compare`.

### WS /ws
WebSocket stream of `snapshot.tick` events.

### Example: start a run via viewer
```bash
curl -sS -X POST http://localhost:8080/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"mode":"ga"}' | jq
```
