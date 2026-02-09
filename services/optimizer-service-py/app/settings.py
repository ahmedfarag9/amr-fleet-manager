"""
File: services/optimizer-service-py/app/settings.py
Purpose: Environment-backed configuration for the optimizer service.
Key responsibilities:
- Parse GA parameters and service settings.
- Build scale presets (including optional overrides).
"""

from dataclasses import dataclass
import os

DEFAULT_SCALE_MAP = {
    "mini": {"robots": 5, "jobs": 5},
    "small": {"robots": 5, "jobs": 25},
    "demo": {"robots": 10, "jobs": 50},
    "large": {"robots": 20, "jobs": 100},
}


def _int_env(name: str, default: int = 0) -> int:
    """Parse an integer env var with a fallback."""
    raw = os.getenv(name, "")
    if raw == "":
        return default
    return int(raw)


def _build_scale_map() -> dict[str, dict[str, int]]:
    """Return the scale map with optional global overrides."""
    scale_map = {key: value.copy() for key, value in DEFAULT_SCALE_MAP.items()}
    robots = _int_env("FLEET_ROBOTS", 0)
    jobs = _int_env("FLEET_JOBS", 0)
    if robots > 0 and jobs > 0:
        for key in scale_map:
            scale_map[key] = {"robots": robots, "jobs": jobs}
    return scale_map


SCALE_MAP = _build_scale_map()


@dataclass(frozen=True)
class Settings:
    """Optimizer configuration parsed from environment."""
    host: str = os.getenv("OPTIMIZER_HOST", "0.0.0.0")
    port: int = int(os.getenv("OPTIMIZER_PORT", "8002"))
    service_time_s: int = int(os.getenv("SERVICE_TIME_S", "5"))
    population_size: int = int(os.getenv("GA_POPULATION_SIZE", "64"))
    generations: int = int(os.getenv("GA_GENERATIONS", "80"))
    elite_size: int = int(os.getenv("GA_ELITE_SIZE", "4"))
    mutation_rate: float = float(os.getenv("GA_MUTATION_RATE", "0.10"))
    crossover_rate: float = float(os.getenv("GA_CROSSOVER_RATE", "0.90"))


settings = Settings()
