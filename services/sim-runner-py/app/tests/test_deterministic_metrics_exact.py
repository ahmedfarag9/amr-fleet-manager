from collections import defaultdict

from app.sim.engine import Assignment, SimulationEngine
from app.sim.entities import SimulationState
from app.sim.metrics import compute_metrics
from app.sim.world import generate_scenario


def _pending_jobs(state: SimulationState):
    jobs = [j for j in state.jobs if j.state in {"pending", "unassigned"}]
    jobs.sort(key=lambda j: (j.deadline_ts, -j.priority, j.id))
    return jobs


def _idle_robots(state: SimulationState):
    robots = [r for r in state.robots if r.state == "idle"]
    robots.sort(key=lambda r: r.id)
    return robots


def _replan_ga(state: SimulationState, planned: dict[int, list[str]]):
    pending = _pending_jobs(state)
    robots = sorted(state.robots, key=lambda r: r.id)
    if not pending or not robots:
        return
    new_planned: dict[int, list[str]] = {r.id: [] for r in robots}
    for idx, job in enumerate(pending):
        robot = robots[idx % len(robots)]
        new_planned[robot.id].append(job.id)
    planned.clear()
    planned.update(new_planned)


def _run_once(mode: str, seed: int, ga_replan_interval_s: int) -> dict:
    robots, jobs, _ = generate_scenario(seed=seed, scale="small", world_size=100)
    state = SimulationState(run_id="run", mode=mode, seed=seed, scale="small", robots=robots, jobs=jobs)

    engine = SimulationEngine(
        state=state,
        tick_hz=5,
        service_time_s=2,
        max_sim_seconds=240,
        robot_update_sink=lambda _: None,
        emit_position_updates=False,
        charge_rate=5.0,
        charge_resume_threshold=20.0,
    )

    planned = defaultdict(list)
    next_periodic = ga_replan_interval_s if ga_replan_interval_s > 0 else None

    engine.emit_initial_robot_updates()
    if mode == "ga":
        _replan_ga(state, planned)

    while not engine.should_stop():
        sim_time = engine.current_sim_time_s()

        if mode == "baseline":
            pending = _pending_jobs(state)
            for robot, job in zip(_idle_robots(state), pending):
                engine.apply_assignment(Assignment(job_id=job.id, robot_id=robot.id))
        else:
            if next_periodic is not None and sim_time >= next_periodic and _pending_jobs(state):
                _replan_ga(state, planned)
                while next_periodic <= sim_time:
                    next_periodic += ga_replan_interval_s

            for robot in _idle_robots(state):
                queue = planned.get(robot.id, [])
                if queue:
                    job_id = queue.pop(0)
                    engine.apply_assignment(Assignment(job_id=job_id, robot_id=robot.id))
                    continue
                if _pending_jobs(state):
                    _replan_ga(state, planned)
                    queue = planned.get(robot.id, [])
                    if queue:
                        job_id = queue.pop(0)
                        engine.apply_assignment(Assignment(job_id=job_id, robot_id=robot.id))

        engine.step()

    engine.finalize()
    return compute_metrics(state.jobs, state.robots)


def test_baseline_metrics_exact_match_for_same_seed():
    metrics_a = _run_once(mode="baseline", seed=42, ga_replan_interval_s=0)
    metrics_b = _run_once(mode="baseline", seed=42, ga_replan_interval_s=0)
    assert metrics_a == metrics_b


def test_ga_metrics_exact_match_for_same_seed_and_replan_interval():
    metrics_a = _run_once(mode="ga", seed=42, ga_replan_interval_s=30)
    metrics_b = _run_once(mode="ga", seed=42, ga_replan_interval_s=30)
    assert metrics_a == metrics_b
