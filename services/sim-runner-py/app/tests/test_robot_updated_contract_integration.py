from app.sim.engine import Assignment, SimulationEngine
from app.sim.entities import Job, Robot, SimulationState


def test_robot_updated_required_fields_and_sim_time_monotonic():
    robot = Robot(id=1, x=0.0, y=0.0, speed=1.0, battery=100.0, state="idle")
    job = Job(
        id="job_1",
        pickup_x=1.0,
        pickup_y=0.0,
        dropoff_x=2.0,
        dropoff_y=0.0,
        deadline_ts=200,
        priority=3,
        state="pending",
    )
    state = SimulationState(
        run_id="run-test",
        mode="baseline",
        seed=42,
        scale="small",
        robots=[robot],
        jobs=[job],
    )

    events: list[dict] = []
    engine = SimulationEngine(
        state=state,
        tick_hz=5,
        service_time_s=1,
        max_sim_seconds=20,
        robot_update_sink=events.append,
        emit_position_updates=True,
        charge_rate=5.0,
        charge_resume_threshold=20.0,
    )

    engine.emit_initial_robot_updates()
    engine.apply_assignment(Assignment(job_id="job_1", robot_id=1))
    for _ in range(30):
        engine.step()

    assert events, "expected robot.updated events"

    sim_values = []
    for event in events:
        assert "robot_id" in event
        assert "state" in event
        assert "sim_time_s" in event
        assert isinstance(event["sim_time_s"], int)
        sim_values.append(event["sim_time_s"])

    assert sim_values == sorted(sim_values)
