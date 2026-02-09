from __future__ import annotations

"""
File: ros2/robot_agents/src/robot_agents/robot_agents/agents_node.py
Purpose: ROS2 node that bridges RabbitMQ telemetry to ROS topics.
Node: robot_agents
Publishers:
- /robot_{id}/telemetry (std_msgs/String, JSON payload)
Subscriptions:
- RabbitMQ queue bound to routing key `telemetry.received`
Lifecycle:
- Starts a background consumer thread
- Publishes latest telemetry at 1 Hz per robot
"""

import asyncio
import json
import threading
import time
from typing import Dict

import aio_pika
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robot_agents.settings import EXCHANGE, QUEUE, ROUTING_KEY, rabbit_url


class AgentsNode(Node):
    """ROS2 node that republishes AMR telemetry into per-robot topics."""
    def __init__(self) -> None:
        super().__init__("robot_agents")
        self.telemetry_publishers: Dict[int, rclpy.publisher.Publisher] = {}
        self.latest_payload: Dict[int, dict] = {}
        self._lock = threading.Lock()

        self.create_timer(1.0, self.publish_latest)
        self._consumer_thread = threading.Thread(target=self._run_consumer_loop, daemon=True)
        self._consumer_thread.start()
        self.get_logger().info("robot_agents node started")

    def publisher_for(self, robot_id: int):
        """Create (or return) the ROS2 publisher for a robot."""
        if robot_id not in self.telemetry_publishers:
            topic = f"/robot_{robot_id}/telemetry"
            self.telemetry_publishers[robot_id] = self.create_publisher(String, topic, 10)
            self.get_logger().info(f"created publisher topic={topic}")
        return self.telemetry_publishers[robot_id]

    def publish_latest(self) -> None:
        """Publish the most recent telemetry for each robot."""
        with self._lock:
            items = sorted(self.latest_payload.items(), key=lambda row: row[0])
        for robot_id, payload in items:
            msg = String()
            msg.data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            self.publisher_for(robot_id).publish(msg)

    def _run_consumer_loop(self) -> None:
        """Run the async RabbitMQ consumer loop in a background thread."""
        asyncio.run(self.consume_loop())

    async def consume_loop(self) -> None:
        """Consume telemetry.received events and cache the latest payload."""
        while rclpy.ok():
            try:
                connection = await aio_pika.connect_robust(rabbit_url())
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=50)
                exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
                queue = await channel.declare_queue(QUEUE, durable=True)
                await queue.bind(exchange, routing_key=ROUTING_KEY)

                async with queue.iterator() as iterator:
                    async for message in iterator:
                        async with message.process(requeue=False):
                            try:
                                payload = json.loads(message.body.decode("utf-8"))
                            except json.JSONDecodeError:
                                self.get_logger().warning("dropping invalid telemetry JSON")
                                continue

                            robot_id_raw = payload.get("robot_id")
                            if robot_id_raw is None:
                                self.get_logger().warning("dropping telemetry without robot_id")
                                continue
                            robot_id = int(robot_id_raw)
                            with self._lock:
                                self.latest_payload[robot_id] = payload
            except Exception as exc:  # noqa: BLE001
                self.get_logger().warning(f"consumer reconnect due to error: {exc}")
                await asyncio.sleep(2.0)


def main() -> None:
    rclpy.init()
    node = AgentsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
