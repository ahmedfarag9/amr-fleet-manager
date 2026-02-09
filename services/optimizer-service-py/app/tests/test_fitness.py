from app.ga.fitness import evaluate_chromosome
from app.schemas import Job, Robot


def test_fitness_penalizes_lateness():
    robots = [Robot(id=1, x=0, y=0, speed=1.0, battery=100, state="idle")]
    early_job = Job(
        id="job-early",
        pickup_x=0,
        pickup_y=0,
        dropoff_x=1,
        dropoff_y=0,
        deadline_ts=100,
        priority=3,
        state="pending",
    )
    late_job = Job(
        id="job-late",
        pickup_x=0,
        pickup_y=0,
        dropoff_x=100,
        dropoff_y=0,
        deadline_ts=1,
        priority=3,
        state="pending",
    )

    fit_early = evaluate_chromosome([0], robots, [early_job], service_time_s=5)
    fit_late = evaluate_chromosome([0], robots, [late_job], service_time_s=5)

    assert fit_late.score > fit_early.score
