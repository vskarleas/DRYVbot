#!/usr/bin/env python3
"""
Spawns human-sized cylinders and moves them along paths using
sinusoidal interpolation for smooth, realistic movement.
Nav2 detects them via lidar and avoids them in real-time.

Usage:
    ros2 run robot_simulation obstacle_spawner.py
    ros2 run robot_simulation obstacle_spawner.py --ros-args -p scenario:=hospital
"""

import math
import time
import rclpy
from rclpy.node import Node
from gazebo_msgs.srv import SpawnEntity, SetEntityState
from gazebo_msgs.msg import EntityState
from geometry_msgs.msg import Pose, Point, Quaternion


# Human cylinder SDF - blue cylinder with no gravity
HUMAN_SDF = """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="{name}">
    <static>false</static>
    <link name="body">
      <gravity>false</gravity>
      <collision name="collision">
        <pose>0 0 0.85 0 0 0</pose>
        <geometry>
          <cylinder>
            <radius>0.28</radius>
            <length>1.70</length>
          </cylinder>
        </geometry>
      </collision>
      <visual name="visual">
        <pose>0 0 0.85 0 0 0</pose>
        <geometry>
          <cylinder>
            <radius>0.28</radius>
            <length>1.70</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>{r} {g} {b} 1</ambient>
          <diffuse>{r} {g} {b} 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>"""


class WalkingPerson:
    """A person moving smoothly between two points using sinusoidal interpolation."""
    def __init__(self, name, point_a, point_b, duration=10.0, color=(0.1, 0.1, 0.9)):
        self.name = name
        self.point_a = point_a
        self.point_b = point_b
        self.duration = duration
        self.color = color

    def get_position(self, t):
        """Sinusoidal interpolation between point_a and point_b."""
        phase = (math.sin(2.0 * math.pi * t / self.duration) + 1.0) / 2.0
        x = self.point_a[0] * (1.0 - phase) + self.point_b[0] * phase
        y = self.point_a[1] * (1.0 - phase) + self.point_b[1] * phase
        return x, y


# ============= SCENARIO DEFINITIONS =============
# Each person: name, point_a (x,y), point_b (x,y), duration (seconds), color (r,g,b)

SCENARIOS = {
    'hospital': [
        WalkingPerson('human_1',
                      point_a=(-8.0, 5.0), point_b=(-2.0, 5.0),
                      duration=12.0, color=(0.1, 0.1, 0.9)),
        WalkingPerson('human_2',
                      point_a=(0.0, 2.0), point_b=(0.0, 8.0),
                      duration=15.0, color=(0.9, 0.1, 0.1)),
        WalkingPerson('human_3',
                      point_a=(-5.0, 0.0), point_b=(-2.0, 5.0),
                      duration=10.0, color=(0.1, 0.9, 0.1)),
    ],
    'corridors': [
        WalkingPerson('human_1',
                      point_a=(-3.0, 0.0), point_b=(3.0, 0.0),
                      duration=12.0, color=(0.1, 0.1, 0.9)),
        WalkingPerson('human_2',
                      point_a=(0.0, -2.0), point_b=(0.0, 2.0),
                      duration=10.0, color=(0.9, 0.1, 0.1)),
    ],
}


class ObstacleSpawner(Node):
    def __init__(self):
        super().__init__('obstacle_spawner')

        self.declare_parameter('scenario', 'hospital')
        scenario_name = self.get_parameter('scenario').value

        if scenario_name not in SCENARIOS:
            self.get_logger().error(
                f'Unknown scenario: {scenario_name}. '
                f'Available: {list(SCENARIOS.keys())}')
            return

        self.people = SCENARIOS[scenario_name]
        self.get_logger().info(
            f'Obstacle spawner: scenario={scenario_name}, '
            f'{len(self.people)} people')

        # Service clients
        self.spawn_client = self.create_client(SpawnEntity, '/spawn_entity')
        self.set_state_client = self.create_client(
            SetEntityState, '/set_entity_state')

        # Wait for Gazebo services
        self.get_logger().info('Waiting for Gazebo services...')
        self.spawn_client.wait_for_service(timeout_sec=30.0)
        self.set_state_client.wait_for_service(timeout_sec=30.0)
        self.get_logger().info('Gazebo ready. Spawning people...')

        # Spawn all people
        self.spawn_people()

        # Start movement
        self.start_time = time.time()
        self.timer = self.create_timer(0.1, self.update_cb)  # 10 Hz

    def spawn_people(self):
        """Spawn all people as colored cylinders."""
        for person in self.people:
            x, y = person.get_position(0)
            req = SpawnEntity.Request()
            req.name = person.name
            req.xml = HUMAN_SDF.format(
                name=person.name,
                r=person.color[0],
                g=person.color[1],
                b=person.color[2])
            req.initial_pose = Pose(
                position=Point(x=x, y=y, z=0.0),
                orientation=Quaternion(w=1.0))

            future = self.spawn_client.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

            if future.result() is not None and future.result().success:
                self.get_logger().info(
                    f'  Spawned {person.name} at ({x:.1f}, {y:.1f})')
            else:
                self.get_logger().warn(f'  Failed to spawn {person.name}')

    def update_cb(self):
        """Move all people using sinusoidal interpolation."""
        t = time.time() - self.start_time

        for person in self.people:
            x, y = person.get_position(t)

            state = EntityState()
            state.name = person.name
            state.reference_frame = 'world'
            state.pose.position.x = float(x)
            state.pose.position.y = float(y)
            state.pose.position.z = 0.0
            state.pose.orientation.w = 1.0

            req = SetEntityState.Request()
            req.state = state
            self.set_state_client.call_async(req)


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleSpawner()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()