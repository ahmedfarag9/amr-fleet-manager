# ROS2 Telemetry Commands

Use this checklist to inspect ROS2 telemetry topics published by the `ros2-robot-agents` bridge.

## 1) Start services and generate telemetry

```bash
docker compose up -d
```

Start a run from UI (`http://localhost:8080`) or with API:

```bash
curl -X POST http://localhost:8080/api/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"ga"}'
```

## 2) Open shell in ROS2 container

```bash
docker compose exec ros2-robot-agents bash
source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash
```

## 3) Inspect nodes and topics

```bash
ros2 node list
ros2 node info /robot_agents
ros2 topic list -t | grep telemetry
```

## 4) Stream telemetry

Live stream:

```bash
ros2 topic echo /robot_1/telemetry
```

One message only:

```bash
ros2 topic echo /robot_1/telemetry --once
```

Publish rate check:

```bash
ros2 topic hz /robot_1/telemetry
```

## 5) Quick check all robot telemetry topics

```bash
for t in $(ros2 topic list | grep '^/robot_[0-9]\+/telemetry$'); do
  echo "=== $t ==="
  ros2 topic echo "$t" --once
done
```

## 6) Non-GUI runtime visibility

If you want node activity/logs without GUI tools:

```bash
docker compose logs -f ros2-robot-agents
```

## Notes

- Topics are created on first telemetry message per robot.
- If no topics appear, make sure a simulation run is active and `telemetry.received` events are flowing.
- The default ROS2 image here is `ros:humble-ros-base`, so desktop GUI tools (like `rqt_graph`) are not installed by default.
