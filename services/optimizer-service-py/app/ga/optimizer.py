from __future__ import annotations

"""
File: services/optimizer-service-py/app/ga/optimizer.py
Purpose: Deterministic GA loop to produce job-to-robot assignments.
Key responsibilities:
- Initialize population
- Evaluate fitness
- Apply selection/crossover/mutation
- Return stable assignment ordering
"""

import random
from typing import Sequence

from app.ga.fitness import evaluate_chromosome, sorted_jobs
from app.ga.operators import crossover, initialize_population, mutate, tournament_select
from app.schemas import Assignment, Job, Robot


def optimize_assignments(
    robots: Sequence[Robot],
    jobs: Sequence[Job],
    seed: int,
    service_time_s: int,
    population_size: int,
    generations: int,
    elite_size: int,
    crossover_rate: float,
    mutation_rate: float,
) -> tuple[list[Assignment], dict[str, object]]:
    """Run the GA optimizer and return assignments + metadata."""
    ordered_robots = sorted(robots, key=lambda r: r.id)
    ordered_jobs = sorted_jobs(jobs)

    if not ordered_jobs or not ordered_robots:
        return [], {"best_score": 0.0, "generations": 0}

    rng = random.Random(seed)
    chromosome_len = len(ordered_jobs)

    population = initialize_population(population_size, chromosome_len, len(ordered_robots), rng)

    best_chromosome: list[int] | None = None
    best_score = float("inf")
    best_job_scores: dict[str, float] = {}

    for _ in range(generations):
        evaluated: list[tuple[float, int, list[int], dict[str, float]]] = []
        for idx, chromosome in enumerate(population):
            fit = evaluate_chromosome(chromosome, ordered_robots, ordered_jobs, service_time_s)
            evaluated.append((fit.score, idx, chromosome, fit.job_scores))
            if fit.score < best_score:
                best_score = fit.score
                best_chromosome = list(chromosome)
                best_job_scores = fit.job_scores

        evaluated.sort(key=lambda row: (row[0], row[1]))
        next_population: list[list[int]] = [list(row[2]) for row in evaluated[:elite_size]]
        fitnesses = [row[0] for row in evaluated]
        sorted_population = [list(row[2]) for row in evaluated]

        while len(next_population) < population_size:
            parent_a = tournament_select(sorted_population, fitnesses, rng)
            parent_b = tournament_select(sorted_population, fitnesses, rng)

            if rng.random() < crossover_rate:
                child_a, child_b = crossover(parent_a, parent_b, rng)
            else:
                child_a, child_b = list(parent_a), list(parent_b)

            next_population.append(mutate(child_a, len(ordered_robots), mutation_rate, rng))
            if len(next_population) < population_size:
                next_population.append(mutate(child_b, len(ordered_robots), mutation_rate, rng))

        population = next_population

    if best_chromosome is None:
        best_chromosome = [0 for _ in ordered_jobs]
        best_fit = evaluate_chromosome(best_chromosome, ordered_robots, ordered_jobs, service_time_s)
        best_score = best_fit.score
        best_job_scores = best_fit.job_scores

    assignments: list[Assignment] = []
    for idx, job in enumerate(ordered_jobs):
        robot = ordered_robots[best_chromosome[idx] % len(ordered_robots)]
        assignments.append(
            Assignment(
                job_id=job.id,
                robot_id=robot.id,
                score=float(best_job_scores.get(job.id, 0.0)),
            )
        )

    assignments.sort(key=lambda a: (a.job_id, a.robot_id))
    meta = {
        "best_score": best_score,
        "generations": generations,
        "population_size": population_size,
        "seed": seed,
    }
    return assignments, meta
