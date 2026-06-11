#!/usr/bin/env python3
"""
Room Command Interpreter Node

Listens for text commands from Foxglove (published as String on /room_command)
and converts room names to Nav2 goal poses using a YAML room registry.

Subscribes:
    /room_command (std_msgs/String) — "Go to room 204", "salle urgences", etc.

Publishes:
    /goal_pose (geometry_msgs/PoseStamped) — Nav2-compatible navigation goal

The room registry maps human-readable names (with aliases) to map coordinates.
"""

import os
import re
import signal
import sys

import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped, Quaternion
from std_msgs.msg import String

import yaml


class RoomInterpreterNode(Node):

    def __init__(self):
        super().__init__('room_interpreter')

        # Parameters
        self.declare_parameter('registry_path', '')

        registry_path = self.get_parameter('registry_path').value

        # Resolve registry path
        if not registry_path or not os.path.isabs(registry_path):
            pkg_share = get_package_share_directory('digital_twin')
            if not registry_path:
                registry_path = os.path.join(
                    pkg_share, 'config', 'room_registry.yaml')
            else:
                registry_path = os.path.join(pkg_share, registry_path)

        # Load room registry
        self.rooms = self._load_registry(registry_path)
        self.get_logger().info(
            f"Loaded {len(self.rooms)} rooms from registry")

        # Build lookup index: alias -> room_data
        self.alias_index = {}
        for room_id, data in self.rooms.items():
            # Index by room_id itself
            self.alias_index[room_id.lower()] = data
            self.alias_index[room_id.lower().replace('_', ' ')] = data
            # Index by each alias
            for alias in data.get('aliases', []):
                self.alias_index[alias.lower()] = data

        self.get_logger().info(
            f"  {len(self.alias_index)} searchable aliases registered")

        # Subscriber
        self.create_subscription(
            String, '/room_command', self._command_callback, 10)

        # Publisher
        self.goal_pub = self.create_publisher(
            PoseStamped, '/goal_pose', 10)

        # Feedback publisher (so Foxglove can show status)
        self.feedback_pub = self.create_publisher(
            String, '/room_command_feedback', 10)

        self.get_logger().info("Room Interpreter ready. Listening on /room_command")

    def _load_registry(self, path):
        """Load room registry from YAML file."""
        if not os.path.exists(path):
            self.get_logger().warn(f"Registry not found: {path}")
            return {}

        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        return data.get('rooms', {})

    def _parse_command(self, text):
        """Extract room name from a text command.

        Handles patterns like:
            "Go to room 204"
            "Navigate to salle urgences"
            "salle_101"
            "room 204"
            "urgences"
        """
        text = text.strip().lower()

        # Remove common command prefixes
        prefixes = [
            r'^go\s+to\s+',
            r'^navigate\s+to\s+',
            r'^move\s+to\s+',
            r'^send\s+(?:the\s+)?robot\s+to\s+',
            r'^aller?\s+[aà]\s+(?:la\s+)?',
            r'^va\s+[aà]\s+(?:la\s+)?',
            r'^direction\s+',
        ]
        for prefix in prefixes:
            text = re.sub(prefix, '', text)

        # Remove articles
        text = re.sub(r'^(?:the|la|le|les|l\')\s+', '', text)

        return text.strip()

    def _find_room(self, query):
        """Find a room matching the query in the alias index.

        Uses exact match first, then substring match, then fuzzy.
        Returns room data dict or None.
        """
        query = query.lower().strip()

        # Exact match
        if query in self.alias_index:
            return self.alias_index[query]

        # Substring match (query contained in an alias or vice versa)
        for alias, data in self.alias_index.items():
            if query in alias or alias in query:
                return data

        # Partial word match
        query_words = set(query.split())
        best_match = None
        best_score = 0
        for alias, data in self.alias_index.items():
            alias_words = set(alias.split())
            overlap = len(query_words & alias_words)
            if overlap > best_score:
                best_score = overlap
                best_match = data

        if best_score > 0:
            return best_match

        return None

    def _command_callback(self, msg: String):
        """Process an incoming text command."""
        raw_text = msg.data
        self.get_logger().info(f"Received command: '{raw_text}'")

        # Parse the command
        room_query = self._parse_command(raw_text)
        self.get_logger().info(f"  Parsed room query: '{room_query}'")

        # Find the room
        room = self._find_room(room_query)

        if room is None:
            feedback = f"Room not found: '{room_query}'. Available rooms: " + \
                       ', '.join(self.rooms.keys())
            self.get_logger().warn(feedback)
            self._publish_feedback(feedback)
            return

        # Build and publish goal pose
        goal = PoseStamped()
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.header.frame_id = 'map'
        goal.pose.position.x = float(room['x'])
        goal.pose.position.y = float(room['y'])
        goal.pose.position.z = 0.0

        # Orientation (default: facing forward)
        ow = float(room.get('orientation_w', 1.0))
        oz = float(room.get('orientation_z', 0.0))
        goal.pose.orientation = Quaternion(x=0.0, y=0.0, z=oz, w=ow)

        self.goal_pub.publish(goal)

        room_name = room.get('display_name', room_query)
        feedback = f"Navigating to {room_name} (x={room['x']}, y={room['y']})"
        self.get_logger().info(f"  {feedback}")
        self._publish_feedback(feedback)

    def _publish_feedback(self, text):
        """Publish feedback message for Foxglove display."""
        msg = String()
        msg.data = text
        self.feedback_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RoomInterpreterNode()

    # ROS2 Humble shutdown: intercept SIGINT before ROS2 destroys the context
    def _shutdown(sig, frame):
        node.get_logger().info('Shutting down RoomInterpreter')
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        rclpy.spin(node)
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()