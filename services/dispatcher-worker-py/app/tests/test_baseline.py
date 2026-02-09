from app.baseline import compute_baseline_assignments


def test_baseline_edf_nearest_assigns_once():
    robots = {
        1: {"id": 1, "x": 0.0, "y": 0.0, "state": "idle", "battery": 80.0},
        2: {"id": 2, "x": 10.0, "y": 10.0, "state": "idle", "battery": 80.0},
    }
    jobs = {
        "j1": {
            "id": "j1",
            "pickup_x": 1,
            "pickup_y": 1,
            "dropoff_x": 2,
            "dropoff_y": 2,
            "deadline_ts": 10,
            "priority": 3,
            "state": "pending",
        },
        "j2": {
            "id": "j2",
            "pickup_x": 9,
            "pickup_y": 9,
            "dropoff_x": 8,
            "dropoff_y": 8,
            "deadline_ts": 20,
            "priority": 2,
            "state": "pending",
        },
    }
    assignments = compute_baseline_assignments(robots, jobs, set(), blocked_robots=set(), battery_threshold=20)
    assert len(assignments) == 2
    assert assignments[0]["job_id"] == "j1"


def test_baseline_fallback_when_battery_low():
    robots = {
        1: {"id": 1, "x": 0.0, "y": 0.0, "state": "idle", "battery": 5.0},
    }
    jobs = {
        "job_1": {
            "id": "job_1",
            "pickup_x": 1.0,
            "pickup_y": 1.0,
            "dropoff_x": 2.0,
            "dropoff_y": 2.0,
            "deadline_ts": 10,
            "priority": 1,
            "state": "pending",
        },
    }
    assignments = compute_baseline_assignments(robots, jobs, set(), blocked_robots=set(), battery_threshold=20)
    assert len(assignments) == 1
    assert assignments[0]["robot_id"] == 1
