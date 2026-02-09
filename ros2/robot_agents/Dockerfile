FROM ros:humble-ros-base

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

COPY src ./src
RUN pip3 install --no-cache-dir aio-pika==9.5.4
RUN /bin/bash -lc 'source /opt/ros/humble/setup.bash && colcon build --symlink-install'

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
