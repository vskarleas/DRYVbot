#!/usr/bin/env python3
"""
Obstacle Spawner - Dynamic people simulation

This node simulates people moving in the corridors by:
1. Spawning cylinder models in Gazebo as "people"
2. Moving them along predefined paths
3. Publishing their positions on /people_positions

In a real deployment, this information would come from
cameras or lidar detection. Here we have omniscient knowledge
of obstacle positions since we control the simulation.
"""

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, PoseArray
from gazebo_msgs.srv import SpawnEntity, DeleteEntity, SetEntityState
from gazebo_msgs.msg import EntityState
import time


# SDF template for a person (cylinder)
PERSON_SDF = """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="{name}">
    <static>false</static>
    <link name="link">
      <visual name="visual">
        <geometry>
          <cylinder>
            <radius>0.25</radius>
            <length>1.7</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>{r} {g} {b} 1</ambient>
          <diffuse>{r} {g} {b} 1</diffuse>
        </material>
      </visual>
      <collision name="collision">
        <geometry>
          <cylinder>
            <radius>0.25</radius>
            <length>1.7</length>
          </cylinder>
        </geometry>
      </collision>
      <inertial>
        <mass>70.0</mass>
      </inertial>
    </link>
  </model>
</sdf>"""


class PersonPath:
    """Defines a path that a person walks along, back and forth."""

    def __init__(self, name, waypoints, speed=0.3, color=(0.8, 0.2, 0.2)):
        """
        name: unique identifier for this person
        waypoints: list of (x, y) positions to walk between
        speed: movement speed in m/s
        color: (r, g, b) color of the cylinder
        """
        self.name = name
        self.waypoints = waypoints
        self.speed = speed
        self.color = color
        self.current_index = 0
        self.forward = True
        self.x = waypoints[0][0]
        self.y = waypoints[0][1]

    def update(self, dt):
        """Move the person along the path for dt seconds."""
        if len(self.waypoints) < 2:
            return

        target = self.waypoints[self.current_index]
        dx = target[0] - self.x
        dy = target[1] - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.1:
            # Reached waypoint, move to next
            if self.forward:
                self.current_index += 1
                if self.current_index >= len(self.waypoints):
                    self.current_index = len(self.waypoints) - 2
                    self.forward = False
            else:
                self.current_index -= 1
                if self.current_index < 0:
                    self.current_index = 1
                    self.forward = True
            return

        # Move toward target
        move_dist = self.speed * dt
        if move_dist > dist:
            move_dist = dist
        self.x += (dx / dist) * move_dist
        self.y += (dy / dist) * move_dist


class ObstacleSpawnerNode(Node):
    """Spawns and manages dynamic obstacles (people) in Gazebo."""

    def __init__(self):
        super().__init__('obstacle_spawner')

        # Parameters
        self.declare_parameter('update_rate', 10.0)  # Hz
        self.declare_parameter('spawn_delay', 8.0)  # seconds to wait before spawning
        self.declare_parameter('scenario', 'intersection')  # scenario name

        # Define people paths for different scenarios
        self.scenarios = {
            # Person walks across the north intersection
            'intersection': [
                PersonPath(
                    'person_1',
                    waypoints=[(-1.0, 0.0), (1.5, 0.0)],
                    speed=0.3,
                    color=(0.8, 0.2, 0.2)
                ),
            ],
            # Multiple people in the corridors
            'crowded': [
                PersonPath(
                    'person_1',
                    waypoints=[(-3.0, 0.0), (3.0, 0.0)],
                    speed=0.25,
                    color=(0.8, 0.2, 0.2)
                ),
                PersonPath(
                    'person_2',
                    waypoints=[(1.0, 2.0), (1.0, 5.0)],
                    speed=0.2,
                    color=(0.2, 0.2, 0.8)
                ),
            ],
            # Person blocking a corridor, forcing a detour
            'blocking': [
                PersonPath(
                    'person_1',
                    waypoints=[(3.0, 0.0), (3.0, 0.0)],  # stationary
                    speed=0.0,
                    color=(0.8, 0.2, 0.2)
                ),
            ],
        }

        # Publisher for people positions
        self.people_pub = self.create_publisher(PoseArray, '/people_positions', 10)

        # Gazebo services
        self.spawn_client = self.create_client(SpawnEntity, '/spawn_entity')
        self.set_state_pub = self.create_publisher(EntityState, '/gazebo/set_entity_state', 10)

        # State
        self.people = []
        self.spawned = False

        # Wait for spawn delay, then spawn
        spawn_delay = self.get_parameter('spawn_delay').value
        self.spawn_timer = self.create_timer(spawn_delay, self._spawn_people)

        # Update loop
        update_rate = self.get_parameter('update_rate').value
        self.dt = 1.0 / update_rate
        self.update_timer = self.create_timer(self.dt, self._update_loop)

        scenario = self.get_parameter('scenario').value
        self.get_logger().info(f'Obstacle Spawner started (scenario: {scenario})')
        self.get_logger().info(f'Will spawn people in {spawn_delay}s...')

    def _spawn_people(self):
        """Spawn all people for the current scenario."""
        if self.spawned:
            return
        self.spawned = True
        self.spawn_timer.cancel()  # Only spawn once

        scenario = self.get_parameter('scenario').value
        if scenario not in self.scenarios:
            self.get_logger().error(f'Unknown scenario: {scenario}')
            return

        self.people = self.scenarios[scenario]

        # Wait for spawn service
        if not self.spawn_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('Gazebo spawn service not available!')
            return

        for person in self.people:
            self._spawn_one(person)

        self.get_logger().info(f'Spawned {len(self.people)} people')

    def _spawn_one(self, person):
        """Spawn a single person cylinder in Gazebo."""
        request = SpawnEntity.Request()
        request.name = person.name
        request.xml = PERSON_SDF.format(
            name=person.name,
            r=person.color[0],
            g=person.color[1],
            b=person.color[2]
        )
        request.initial_pose = Pose()
        request.initial_pose.position.x = person.x
        request.initial_pose.position.y = person.y
        request.initial_pose.position.z = 0.85  # Half of cylinder height

        future = self.spawn_client.call_async(request)
        future.add_done_callback(
            lambda f, name=person.name: self._spawn_callback(f, name))

    def _spawn_callback(self, future, name):
        """Handle spawn service response."""
        try:
            response = future.result()
            if response.success:
                self.get_logger().info(f'Spawned {name}')
            else:
                self.get_logger().warn(f'Failed to spawn {name}: {response.status_message}')
        except Exception as e:
            self.get_logger().error(f'Spawn service call failed: {e}')

    def _update_loop(self):
        """Update people positions and publish."""
        if not self.spawned or not self.people:
            return

        # Update each person's position
        for person in self.people:
            person.update(self.dt)

            # Move the entity in Gazebo
            state = EntityState()
            state.name = person.name
            state.pose.position.x = person.x
            state.pose.position.y = person.y
            state.pose.position.z = 0.85
            state.reference_frame = 'world'
            self.set_state_pub.publish(state)

        # Publish all positions for the digital twin
        msg = PoseArray()
        msg.header.frame_id = 'odom'
        msg.header.stamp = self.get_clock().now().to_msg()
        for person in self.people:
            pose = Pose()
            pose.position.x = person.x
            pose.position.y = person.y
            pose.position.z = 0.0
            msg.poses.append(pose)

        self.people_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleSpawnerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()