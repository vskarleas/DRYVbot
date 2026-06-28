#!/usr/bin/env python3
"""Spawn the hospital's permanent humans and expose all people on one topic.

The moving scenario publishes its people on ``/scenario_people_positions``.
This node adds the permanent humans below and republishes the combined list on
``/people_positions`` so the dynamic map continues to consume a single topic.
"""

import copy
import signal

import rclpy
from gazebo_msgs.srv import DeleteEntity, SpawnEntity
from geometry_msgs.msg import Point, Pose, PoseArray, Quaternion
from rclpy.node import Node


PERSON_SDF = """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="{name}">
    <static>true</static>
    <link name="body">
      <gravity>false</gravity>
      <visual name="visual">
        <geometry>
          <mesh>
            <uri>model://Scrubs/meshes/scrubs.obj</uri>
          </mesh>
        </geometry>
      </visual>
      <collision name="collision">
        <geometry>
          <mesh>
            <uri>model://Scrubs/meshes/Scrubs_Col.obj</uri>
          </mesh>
        </geometry>
      </collision>
    </link>
  </model>
</sdf>"""


# z was not provided for humans 3 to 7, so the same floor-level value as
# human 2 is used for them.
FIXED_HUMANS = (
    ("fixed_human_1", -1.31, -11.611, -0.0014326),
    ("fixed_human_2", 1.16, -11.41, -0.00143),
    ("fixed_human_3", -2.76, -10.67, -0.00143),
    ("fixed_human_4", 2.6379, -10.7022, -0.00143),
    ("fixed_human_5", 11.0741, 2.2342, -0.00143),
    ("fixed_human_6", 9.27, 1.92, -0.00143),
    ("fixed_human_7", 8.68, -1.32, -0.00143),
)


class FixedObstacles(Node):
    """Keep permanent humans in Gazebo and in the dynamic-map input."""

    def __init__(self):
        super().__init__("obstacles_fixes")

        self.scenario_poses = []
        self.spawned_names = []
        self.people_pub = self.create_publisher(
            PoseArray, "/people_positions", 10
        )
        self.create_subscription(
            PoseArray,
            "/scenario_people_positions",
            self._on_scenario_people,
            10,
        )

        self.spawn_client = self.create_client(SpawnEntity, "/spawn_entity")
        self.delete_client = self.create_client(DeleteEntity, "/delete_entity")

        self.create_timer(0.2, self._publish_combined_people)
        self._spawn_fixed_humans()

    @staticmethod
    def _fixed_pose(x, y, z):
        return Pose(
            position=Point(x=float(x), y=float(y), z=float(z)),
            orientation=Quaternion(w=1.0),
        )

    def _spawn_fixed_humans(self):
        self.get_logger().info("Waiting for Gazebo spawn service...")
        if not self.spawn_client.wait_for_service(timeout_sec=30.0):
            self.get_logger().error(
                "/spawn_entity is unavailable; fixed humans were not spawned"
            )
            return

        for name, x, y, z in FIXED_HUMANS:
            request = SpawnEntity.Request()
            request.name = name
            request.xml = PERSON_SDF.format(name=name)
            request.initial_pose = self._fixed_pose(x, y, z)

            future = self.spawn_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
            result = future.result() if future.done() else None

            if result is not None and result.success:
                self.spawned_names.append(name)
                self.get_logger().info(
                    f"Spawned {name} at ({x}, {y}, {z})"
                )
            else:
                reason = result.status_message if result is not None else "timeout"
                self.get_logger().warning(
                    f"Could not spawn {name}: {reason}"
                )

        self.get_logger().info(
            f"Fixed hospital humans ready: {len(self.spawned_names)}/"
            f"{len(FIXED_HUMANS)} spawned"
        )

    def _on_scenario_people(self, message):
        self.scenario_poses = [copy.deepcopy(pose) for pose in message.poses]

    def _publish_combined_people(self):
        message = PoseArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "map"
        message.poses = [
            self._fixed_pose(x, y, z)
            for _name, x, y, z in FIXED_HUMANS
        ]
        message.poses.extend(copy.deepcopy(self.scenario_poses))
        self.people_pub.publish(message)

    def cleanup(self):
        if not self.spawned_names:
            return
        if not self.delete_client.wait_for_service(timeout_sec=2.0):
            return

        for name in self.spawned_names:
            request = DeleteEntity.Request()
            request.name = name
            self.delete_client.call_async(request)


def main(args=None):
    rclpy.init(args=args)
    node = FixedObstacles()

    def _shutdown(_signal, _frame):
        node.cleanup()
        if rclpy.ok():
            rclpy.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        rclpy.spin(node)
    finally:
        node.cleanup()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
