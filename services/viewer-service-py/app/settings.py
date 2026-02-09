"""
File: services/viewer-service-py/app/settings.py
Purpose: Environment-backed configuration for viewer-service.
Key responsibilities:
- Parse fleet defaults and RabbitMQ settings.
- Build scale presets (with optional overrides).
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
    """Viewer configuration parsed from environment."""
    fleet_api_url: str = os.getenv("FLEET_API_URL", "http://fleet-api:8000")
    rabbit_host: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    rabbit_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbit_user: str = os.getenv("RABBITMQ_USER", "amr")
    rabbit_pass: str = os.getenv("RABBITMQ_PASS", "amrpass")
    exchange_name: str = "amr.events"
    fleet_scale: str = os.getenv("FLEET_SCALE", "demo")
    fleet_seed: int = int(os.getenv("FLEET_SEED", "42"))
    fleet_mode: str = os.getenv("FLEET_MODE", "baseline")
    ga_replan_interval_s: int = int(os.getenv("GA_REPLAN_INTERVAL_S", "0"))


settings = Settings()


def rabbit_url() -> str:
    return f"amqp://{settings.rabbit_user}:{settings.rabbit_pass}@{settings.rabbit_host}:{settings.rabbit_port}/"
