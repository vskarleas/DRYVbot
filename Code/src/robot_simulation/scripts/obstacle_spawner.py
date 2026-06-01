#!/usr/bin/env python3
"""
Dynamic Obstacle Spawner for Gazebo Classic

Spawns human-sized cylinders and moves them along paths using
sinusoidal interpolation for smooth, realistic movement.
Nav2 detects them via lidar and avoids them in real-time.

Uses gazebo_msgs services:
  /spawn_entity         (gazebo_msgs/srv/SpawnEntity)
  /set_entity_state     (gazebo_msgs/srv/SetEntityState)

Usage:
    ros2 run robot_simulation obstacle_spawner.py
    ros2 run robot_simulation obstacle_spawner.py --ros-args -p scenario:=hospital
"""

import math
import os
import signal
import time
import rclpy
from rclpy.node import Node
from gazebo_msgs.srv import SpawnEntity, SetEntityState, DeleteEntity
from gazebo_msgs.msg import EntityState
from geometry_msgs.msg import Pose, Point, Quaternion


def load_sdf_template(package_name='robot_simulation'):
    """
    Load human_cylinder.sdf from the package's models directory.
    Falls back to inline SDF if the file is not found.
    """
    try:
        from ament_index_python.packages import get_package_share_directory
        pkg_share = get_package_share_directory(package_name)
        sdf_path = os.path.join(pkg_share, 'models', 'human_cylinder.sdf')
        with open(sdf_path, 'r') as f:
            content = f.read()
            return content
    except Exception:
        return HUMAN_SDF_FALLBACK


# Fallback inline SDF if the external file is not found
HUMAN_SDF_FALLBACK = """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="human_cylinder">
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
          <ambient>0.1 0.1 0.9 1</ambient>
          <diffuse>0.1 0.1 0.9 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>"""


def customize_sdf(sdf_template, name, color):
    """
    Take the base SDF template and customize it for a specific person:
    - Replace the model name
    - Inject the per-person color
    """
    sdf = sdf_template

    # Replace model name
    sdf = sdf.replace(
        'name="human_cylinder"',
        f'name="{name}"')

    # Replace color (the base SDF uses 0.1 0.1 0.9 as default blue)
    r, g, b = color
    color_str = f'{r} {g} {b} 1'
    sdf = sdf.replace('0.1 0.1 0.9 1', color_str)

    return sdf


class WalkingPerson:
    """A person moving smoothly between two points
    using sinusoidal interpolation."""
    def __init__(self, name, point_a, point_b, duration=10.0,
                 color=(0.1, 0.1, 0.9)):
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


SCENARIOS = {
    'hospital': [
        WalkingPerson('human_1',
                      point_a=(-4.586, -9.685),
                      point_b=(-5.937, -9.431),
                      duration=21.0, color=(0.1, 0.1, 0.9)),
        WalkingPerson('human_2',
                      point_a=(1.2, 9.7), 
                      point_b=(-2.5, 14.0),
                      duration=50.0, color=(0.9, 0.1, 0.1)),
        WalkingPerson('human_3',
                      point_a=(4.0, 1.0), 
                      point_b=(5.0, 2.0),
                      duration=22.0, color=(0.1, 0.9, 0.1)),
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

        # Load SDF template once
        self.sdf_template = load_sdf_template()

        # Parameters
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

        # ===== Gazebo Classic services =====
        self.spawn_client = self.create_client(
            SpawnEntity, '/spawn_entity')
        self.set_state_client = self.create_client(
            SetEntityState, '/set_entity_state')
        self.delete_client = self.create_client(
            DeleteEntity, '/delete_entity')

        # Wait for Gazebo services
        self.get_logger().info('Waiting for Gazebo services...')
        if not self.spawn_client.wait_for_service(timeout_sec=30.0):
            self.get_logger().error('/spawn_entity service not available!')
            return
        if not self.set_state_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error('/set_entity_state service not available!')
            return
        self.get_logger().info('Gazebo services ready!')

        # Spawn all people
        self.spawn_people()

        # Start movement at 10 Hz
        self.start_time = time.time()
        self.timer = self.create_timer(0.1, self.update_cb)
        self.get_logger().info('Movement started (10 Hz)')

    def spawn_people(self):
        """Spawn all people as colored cylinders."""
        for person in self.people:
            x, y = person.get_position(0)

            # Build per-person SDF from template
            sdf_xml = customize_sdf(
                self.sdf_template, person.name, person.color)

            req = SpawnEntity.Request()
            req.name = person.name
            req.xml = sdf_xml
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

            # Use call_async but add a callback to catch errors
            future = self.set_state_client.call_async(req)
            future.add_done_callback(self._check_response)

    def _check_response(self, future):
        """Log any errors from SetEntityState calls."""
        try:
            result = future.result()
            if result is not None and not result.success:
                self.get_logger().warn(
                    f'SetEntityState failed: {result.status_message}',
                    throttle_duration_sec=5.0)
        except Exception as e:
            self.get_logger().error(
                f'SetEntityState error: {e}',
                throttle_duration_sec=5.0)

    def cleanup(self):
        """Delete all spawned people from Gazebo."""
        if not hasattr(self, 'people'):
            return

        self.get_logger().info('Cleaning up: deleting spawned obstacles...')

        # Stop the movement timer
        if hasattr(self, 'timer'):
            self.timer.cancel()

        for person in self.people:
            req = DeleteEntity.Request()
            req.name = person.name

            future = self.delete_client.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

            if future.result() is not None and future.result().success:
                self.get_logger().info(f'  Deleted {person.name}')
            else:
                self.get_logger().warn(f'  Failed to delete {person.name}')

        self.get_logger().info('Cleanup complete.')


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleSpawner()

    # Catch SIGINT ourselves before ROS destroys the context
    shutdown_requested = False

    def signal_handler(sig, frame):
        nonlocal shutdown_requested
        if not shutdown_requested:
            shutdown_requested = True
            node.cleanup()
            raise SystemExit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        rclpy.spin(node)
    except SystemExit:
        pass

    node.destroy_node()

    try:
        rclpy.shutdown()
    except Exception:
        pass


if __name__ == '__main__':
    main()