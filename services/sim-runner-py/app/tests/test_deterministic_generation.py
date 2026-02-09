from app.sim.world import generate_scenario


def test_scenario_generation_deterministic():
    robots_a, jobs_a, hash_a = generate_scenario(seed=42, scale="demo", world_size=100)
    robots_b, jobs_b, hash_b = generate_scenario(seed=42, scale="demo", world_size=100)

    assert hash_a == hash_b
    assert [r.__dict__ for r in robots_a] == [r.__dict__ for r in robots_b]
    assert [j.__dict__ for j in jobs_a] == [j.__dict__ for j in jobs_b]


def test_scenario_generation_changes_with_seed():
    _, _, hash_a = generate_scenario(seed=42, scale="demo", world_size=100)
    _, _, hash_b = generate_scenario(seed=43, scale="demo", world_size=100)
    assert hash_a != hash_b


def test_scenario_generation_with_explicit_counts():
    robots, jobs, _ = generate_scenario(seed=42, scale="demo", world_size=100, robots_override=7, jobs_override=11)
    assert len(robots) == 7
    assert len(jobs) == 11
