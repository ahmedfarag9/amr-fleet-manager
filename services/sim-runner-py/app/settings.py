"""
File: services/sim-runner-py/app/settings.py
Purpose: Environment-backed configuration for sim-runner.
Key responsibilities:
- Parse RabbitMQ/MySQL settings.
- Define scale presets and simulation parameters.
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
    """Simulation configuration parsed from environment."""
    rabbit_host: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    rabbit_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbit_user: str = os.getenv("RABBITMQ_USER", "amr")
    rabbit_pass: str = os.getenv("RABBITMQ_PASS", "amrpass")
    mysql_host: str = os.getenv("MYSQL_HOST", "mysql")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "amr")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "amrpass")
    mysql_db: str = os.getenv("MYSQL_DB", "amr_fleet")
    exchange_name: str = "amr.events"
    fleet_scale: str = os.getenv("FLEET_SCALE", "demo")
    fleet_seed: int = int(os.getenv("FLEET_SEED", "42"))
    fleet_mode: str = os.getenv("FLEET_MODE", "baseline")
    sim_tick_hz: int = int(os.getenv("SIM_TICK_HZ", "5"))
    telemetry_hz: int = int(os.getenv("TELEMETRY_HZ", "1"))
    world_size: int = int(os.getenv("WORLD_SIZE", "100"))
    max_sim_seconds: int = int(os.getenv("MAX_SIM_SECONDS", "3600"))
    service_time_s: int = int(os.getenv("SERVICE_TIME_S", "5"))
    charge_rate: float = float(os.getenv("CHARGE_RATE", "5"))
    charge_resume_threshold: float = float(os.getenv("CHARGE_RESUME_THRESHOLD", "20"))
    robot_speed_min: float = float(os.getenv("ROBOT_SPEED_MIN", "1.0"))
    robot_speed_max: float = float(os.getenv("ROBOT_SPEED_MAX", "2.0"))


settings = Settings()


def rabbit_url() -> str:
    return f"amqp://{settings.rabbit_user}:{settings.rabbit_pass}@{settings.rabbit_host}:{settings.rabbit_port}/"
