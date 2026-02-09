from app.ga.optimizer import optimize_assignments
from app.schemas import Job, Robot


def test_optimizer_deterministic_for_seed():
    robots = [
        Robot(id=1, x=0, y=0, speed=1.5, battery=100, state="idle"),
        Robot(id=2, x=10, y=10, speed=1.2, battery=100, state="idle"),
    ]
    jobs = [
        Job(
            id="job-1",
            pickup_x=1,
            pickup_y=1,
            dropoff_x=5,
            dropoff_y=5,
            deadline_ts=120,
            priority=5,
            state="pending",
        ),
        Job(
            id="job-2",
            pickup_x=3,
            pickup_y=7,
            dropoff_x=8,
            dropoff_y=1,
            deadline_ts=160,
            priority=4,
            state="pending",
        ),
    ]

    result_a, meta_a = optimize_assignments(
        robots=robots,
        jobs=jobs,
        seed=42,
        service_time_s=5,
        population_size=32,
        generations=30,
        elite_size=2,
        crossover_rate=0.9,
        mutation_rate=0.1,
    )
    result_b, meta_b = optimize_assignments(
        robots=robots,
        jobs=jobs,
        seed=42,
        service_time_s=5,
        population_size=32,
        generations=30,
        elite_size=2,
        crossover_rate=0.9,
        mutation_rate=0.1,
    )

    assert [a.model_dump() for a in result_a] == [a.model_dump() for a in result_b]
    assert meta_a == meta_b
