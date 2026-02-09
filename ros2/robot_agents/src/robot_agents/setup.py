from setuptools import setup

package_name = "robot_agents"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/robot_agents"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools", "aio-pika==9.5.4"],
    zip_safe=True,
    maintainer="amr-demo",
    maintainer_email="demo@example.com",
    description="ROS2 AMR telemetry bridge",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "agents_node = robot_agents.agents_node:main",
        ],
    },
)
