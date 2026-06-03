#!/usr/bin/env python3
"""
Dynamic Obstacle Spawner for Gazebo Classic

Spawns walking people (Scrubs 3D model) and moves them along paths
using sinusoidal interpolation for smooth, realistic movement.
Nav2 detects them via lidar and avoids them in real-time.

Uses gazebo_msgs services:
  /spawn_entity         (gazebo_msgs/srv/SpawnEntity)
  /set_entity_state     (gazebo_msgs/srv/SetEntityState)
  /delete_entity        (gazebo_msgs/srv/DeleteEntity)

Usage:
    ros2 run robot_simulation obstacle_spawner.py
    ros2 run robot_simulation obstacle_spawner.py --ros-args -p scenario:=hospital
"""

import math
import signal
import time
import rclpy
from rclpy.node import Node
from gazebo_msgs.srv import SpawnEntity, SetEntityState, DeleteEntity
from gazebo_msgs.msg import EntityState
from geometry_msgs.msg import Pose, Point, Quaternion, PoseArray


# SDF template using the Scrubs mesh model
# - static=false so SetEntityState can move it
# - gravity=false so it doesn't fall through the floor
PERSON_SDF = """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="{name}">
    <static>false</static>
    <link name="body">
      <gravity>false</gravity>
      <pose>0 0 0 0 0 0</pose>
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


class WalkingPerson:
    """A person moving smoothly between two points
    using sinusoidal interpolation."""
    def __init__(self, name, point_a, point_b, duration=10.0):
        self.name = name
        self.point_a = point_a
        self.point_b = point_b
        self.duration = duration

    def get_position(self, t):
        """Sinusoidal interpolation between point_a and point_b."""
        phase = (math.sin(2.0 * math.pi * t / self.duration) + 1.0) / 2.0
        x = self.point_a[0] * (1.0 - phase) + self.point_b[0] * phase
        y = self.point_a[1] * (1.0 - phase) + self.point_b[1] * phase
        return x, y

    def get_yaw(self, t):
        """Calculate facing direction based on movement."""
        dt = 0.01
        x1, y1 = self.get_position(t)
        x2, y2 = self.get_position(t + dt)
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return 0.0
        return math.atan2(dy, dx)


SCENARIOS = {
    'hospital': [
        WalkingPerson('human_1',
                      point_a=(-4.586, -14.697),
                      point_b=(-5.937, -14.430),
                      duration=21.0),
        WalkingPerson('human_2',
                      point_a=(1.2, 13.7), 
                      point_b=(-2.5, 14.0),
                      duration=30.0),
        WalkingPerson('human_3',
                      point_a=(4.0, 1.0), 
                      point_b=(5.0, 2.0),
                      duration=22.0),
    ],
    'corridors': [
        WalkingPerson('human_1',
                      point_a=(-3.0, 0.0), point_b=(3.0, 0.0),
                      duration=12.0),
        WalkingPerson('human_2',
                      point_a=(0.0, -2.0), point_b=(0.0, 2.0),
                      duration=10.0),
    ],
}


class ObstacleSpawner(Node):
    def __init__(self):
        super().__init__('obstacle_spawner')

        # Parameters
        self.declare_parameter('scenario', 'hospital')
        scenario_name = self.get_parameter('scenario').value

        # Creating subscriber for people positions (for Crowd Monitor)
        self.people_pub = self.create_publisher(PoseArray, '/people_positions', 10)

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
        """Spawn all people using the Scrubs model."""
        for person in self.people:
            x, y = person.get_position(0)

            req = SpawnEntity.Request()
            req.name = person.name
            req.xml = PERSON_SDF.format(name=person.name)
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
            yaw = person.get_yaw(t)

            state = EntityState()
            state.name = person.name
            state.reference_frame = 'world'
            state.pose.position.x = float(x)
            state.pose.position.y = float(y)
            state.pose.position.z = 0.0
            # Convert yaw to quaternion (rotation around Z)
            state.pose.orientation.z = math.sin(yaw / 2.0)
            state.pose.orientation.w = math.cos(yaw / 2.0)

            req = SetEntityState.Request()
            req.state = state

            future = self.set_state_client.call_async(req)
            future.add_done_callback(self._check_response)

        # Publish people positions for AI intelligence layer
        people_msg = PoseArray()
        people_msg.header.stamp = self.get_clock().now().to_msg()
        people_msg.header.frame_id = 'map'
        for person in self.people:
            pose = Pose()
            x, y = person.get_position(t)
            pose.position.x = float(x)
            pose.position.y = float(y)
            pose.position.z = 0.85
            pose.orientation.w = 1.0
            people_msg.poses.append(pose)
        self.people_pub.publish(people_msg)

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