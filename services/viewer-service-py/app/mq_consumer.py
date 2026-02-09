from __future__ import annotations

"""
File: services/viewer-service-py/app/mq_consumer.py
Purpose: RabbitMQ consumer for live snapshots and run completion.
Key responsibilities:
- Consume snapshot.tick and broadcast to WebSocket clients.
- Track latest run.completed payloads for UI use.
"""

import asyncio
import json
import logging
from typing import Any

import aio_pika
from aio_pika import ExchangeType

from app.settings import rabbit_url, settings
from app.ws import WSManager

logger = logging.getLogger("viewer-mq")


class MQConsumer:
    """RabbitMQ consumer that feeds live data to WS clients."""
    def __init__(self, ws_manager: WSManager) -> None:
        self.ws_manager = ws_manager
        self.latest_snapshot: dict[str, Any] | None = None
        self.last_completed: dict[str, Any] = {}

    async def start(self) -> None:
        """Connect to RabbitMQ, declare queues, and consume messages."""
        connection = await aio_pika.connect_robust(rabbit_url())
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=100)

        exchange = await channel.declare_exchange(settings.exchange_name, ExchangeType.TOPIC, durable=True)
        q_snapshot = await channel.declare_queue("viewer.snapshot", durable=True)
        q_completed = await channel.declare_queue("viewer.run_completed", durable=True)

        await q_snapshot.bind(exchange, routing_key="snapshot.tick")
        await q_completed.bind(exchange, routing_key="run.completed")

        await q_snapshot.consume(self._on_message)
        await q_completed.consume(self._on_message)
        logger.info("viewer mq consumer started")

    async def _on_message(self, message: aio_pika.IncomingMessage) -> None:
        """Handle snapshot.tick and run.completed messages."""
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("drop invalid JSON routing_key=%s", message.routing_key)
            await message.ack()
            return

        try:
            if message.routing_key == "snapshot.tick":
                self.latest_snapshot = payload
                await self.ws_manager.broadcast(payload)
            elif message.routing_key == "run.completed":
                run_id = str(payload.get("run_id", ""))
                if run_id:
                    self.last_completed[run_id] = payload
        except Exception as exc:  # noqa: BLE001
            logger.exception("mq message handling error: %s", exc)
        finally:
            await message.ack()
