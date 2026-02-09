from __future__ import annotations

"""
File: services/optimizer-service-py/app/main.py
Purpose: FastAPI entrypoint for the deterministic GA optimizer.
Key responsibilities:
- Expose /health and /optimize endpoints.
- Delegate optimization to GA engine with env-configured parameters.
Key entrypoints:
- health()
- optimize()
Config/env vars:
- OPTIMIZER_HOST, OPTIMIZER_PORT
- SERVICE_TIME_S
- GA_POPULATION_SIZE, GA_GENERATIONS, GA_ELITE_SIZE
- GA_MUTATION_RATE, GA_CROSSOVER_RATE
"""

from fastapi import FastAPI

from app.ga.optimizer import optimize_assignments
from app.schemas import OptimizeRequest, OptimizeResponse
from app.settings import settings

app = FastAPI(title="optimizer-service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness check for the optimizer service."""
    return {"status": "ok"}


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest) -> OptimizeResponse:
    """Run deterministic GA optimization and return assignments + metadata."""
    assignments, meta = optimize_assignments(
        robots=req.robots,
        jobs=req.pending_jobs,
        seed=req.seed,
        service_time_s=settings.service_time_s,
        population_size=settings.population_size,
        generations=settings.generations,
        elite_size=settings.elite_size,
        crossover_rate=settings.crossover_rate,
        mutation_rate=settings.mutation_rate,
    )
    return OptimizeResponse(assignments=assignments, meta=meta)
