#!/bin/bash
# Entrypoint for the ROS2 telemetry bridge container.
# Sources ROS2 environment and runs the robot_agents node.
set -e
source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash
exec ros2 run robot_agents agents_node
