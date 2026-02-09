from __future__ import annotations

"""
File: services/dispatcher-worker-py/app/mq.py
Purpose: RabbitMQ connectivity and queue topology for dispatcher-worker.
Key responsibilities:
- Declare exchange and service queues.
- Publish job.assigned events.
"""

import json
from typing import Any

import aio_pika
from aio_pika import ExchangeType


async def connect(rabbit_url: str) -> aio_pika.RobustConnection:
    """Connect to RabbitMQ with robust reconnect behavior."""
    return await aio_pika.connect_robust(rabbit_url)


async def setup_topology(channel: aio_pika.abc.AbstractRobustChannel, exchange_name: str):
    """Declare exchange/queues and bind routing keys."""
    exchange = await channel.declare_exchange(exchange_name, ExchangeType.TOPIC, durable=True)

    queue_run_started = await channel.declare_queue("dispatcher.run_started", durable=True)
    queue_job_created = await channel.declare_queue("dispatcher.job_created", durable=True)
    queue_robot_updated = await channel.declare_queue("dispatcher.robot_updated", durable=True)

    await queue_run_started.bind(exchange, routing_key="run.started")
    await queue_job_created.bind(exchange, routing_key="job.created")
    await queue_robot_updated.bind(exchange, routing_key="robot.updated")

    return exchange, queue_run_started, queue_job_created, queue_robot_updated


async def publish_event(exchange: aio_pika.abc.AbstractExchange, routing_key: str, payload: dict[str, Any]) -> None:
    """Publish a JSON message to the configured exchange."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    msg = aio_pika.Message(
        body=body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await exchange.publish(msg, routing_key=routing_key)
