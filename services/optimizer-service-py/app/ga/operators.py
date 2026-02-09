from __future__ import annotations

"""
File: services/optimizer-service-py/app/ga/operators.py
Purpose: Genetic operators (init, selection, crossover, mutation).
Key responsibilities:
- Deterministic population initialization
- Tournament selection with stable tie-breaks
"""

from typing import Sequence
import random


def initialize_population(
    population_size: int,
    chromosome_len: int,
    robot_count: int,
    rng: random.Random,
) -> list[list[int]]:
    """Create the initial population of chromosomes."""
    if chromosome_len == 0:
        return [[]]
    return [
        [rng.randrange(robot_count) for _ in range(chromosome_len)]
        for _ in range(population_size)
    ]


def tournament_select(
    population: Sequence[list[int]],
    fitnesses: Sequence[float],
    rng: random.Random,
    k: int = 3,
) -> list[int]:
    """Select a parent using tournament selection."""
    indices = [rng.randrange(len(population)) for _ in range(k)]
    best_idx = min(indices, key=lambda idx: (fitnesses[idx], idx))
    return list(population[best_idx])


def crossover(parent_a: Sequence[int], parent_b: Sequence[int], rng: random.Random) -> tuple[list[int], list[int]]:
    """One-point crossover between two parents."""
    if len(parent_a) <= 1:
        return list(parent_a), list(parent_b)
    point = rng.randrange(1, len(parent_a))
    child_a = list(parent_a[:point]) + list(parent_b[point:])
    child_b = list(parent_b[:point]) + list(parent_a[point:])
    return child_a, child_b


def mutate(chromosome: list[int], robot_count: int, mutation_rate: float, rng: random.Random) -> list[int]:
    """Point mutation for a chromosome."""
    for idx in range(len(chromosome)):
        if rng.random() < mutation_rate:
            chromosome[idx] = rng.randrange(robot_count)
    return chromosome
