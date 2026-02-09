"""
File: ros2/robot_agents/src/robot_agents/robot_agents/settings.py
Purpose: RabbitMQ connection settings for the ROS2 telemetry bridge.
"""

import os


def rabbit_url() -> str:
    """Return AMQP URL based on environment variables."""
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = os.getenv("RABBITMQ_PORT", "5672")
    user = os.getenv("RABBITMQ_USER", "amr")
    password = os.getenv("RABBITMQ_PASS", "amrpass")
    return f"amqp://{user}:{password}@{host}:{port}/"


EXCHANGE = "amr.events"
QUEUE = "ros2.telemetry"
ROUTING_KEY = "telemetry.received"
