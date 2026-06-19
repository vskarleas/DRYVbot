#!/usr/bin/env python3
"""
simulation_logger.py — Records navigation simulation data to JSON.

For each room command received, logs:
  - Departure: robot position + timestamp when the command was received
  - Target: room name, room ID, and theoretical coordinates from registry
  - Arrival: robot position + timestamp when Nav2 reports goal reached
  - Duration: time elapsed between departure and arrival
  - Position error: Euclidean distance between target and actual arrival

Output is a single JSON file per simulation run, saved under simulation_logs/.

Subscribes:
    /room_command                       (std_msgs/String)
    /bcr_bot/odom                       (nav_msgs/Odometry)
    /navigate_to_pose/_action/status    (action_msgs/GoalStatusArray)
    /room_command_feedback              (std_msgs/String)
    /clock                              (rosgraph_msgs/Clock)

Parameters:
    log_directory   (str)   — folder for simulation logs
    room_registry   (str)   — path to room_registry.yaml (empty = auto-resolve)
    odom_topic      (str)   — odometry topic
    goal_reached_distance_m (float) — fallback distance threshold
"""

import json
import math
import os
import signal
import sys
from datetime import datetime, timezone

import yaml
import rclpy
from rclpy.node import Node

from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String

from ament_index_python.packages import get_package_share_directory


# Nav2 GoalStatus constants
STATUS_SUCCEEDED = 4
STATUS_ABORTED = 6
STATUS_CANCELED = 5


class SimulationLogger(Node):

    def __init__(self):
        super().__init__('simulation_logger')

        # ── Parameters ──────────────────────────────────────────────────
        #
        # Default log directory: resolved relative to the colcon workspace
        # that contains this package, so it works on any machine.
        #   <ws>/install/digital_twin/share/digital_twin/
        #        ^^^^^ go up 4 levels to reach <ws>/
        #   → <ws>/simulation_logs/
        #
        # Can be overridden via parameter or logic_params.yaml.
        #
        pkg_share = get_package_share_directory('digital_twin')
        workspace_root = os.path.abspath(
            os.path.join(pkg_share, '..', '..', '..', '..')
        )
        default_log_dir = os.path.join(workspace_root, 'simulation_logs')

        self.declare_parameter('log_directory', default_log_dir)
        self.declare_parameter('room_registry', '')
        self.declare_parameter('odom_topic', '/bcr_bot/odom')
        self.declare_parameter('goal_reached_distance_m', 0.35)

        self.log_directory = self.get_parameter('log_directory').value
        registry_path = self.get_parameter('room_registry').value
        self.odom_topic = self.get_parameter('odom_topic').value
        self.goal_reached_distance = self.get_parameter(
            'goal_reached_distance_m'
        ).value

        # ── Resolve and load room registry ──────────────────────────────
        if not registry_path or not os.path.isabs(registry_path):
            if not registry_path:
                registry_path = os.path.join(
                    pkg_share, 'config', 'room_registry.yaml'
                )
            else:
                registry_path = os.path.join(pkg_share, registry_path)

        self.rooms = self._load_registry(registry_path)
        self.alias_index = self._build_alias_index(self.rooms)
        self.get_logger().info(
            f'Loaded {len(self.rooms)} rooms from registry'
        )

        # ── Prepare log directory and file ──────────────────────────────
        os.makedirs(self.log_directory, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.log_file = os.path.join(
            self.log_directory,
            f'simulation_{timestamp}.json',
        )

        # Simulation-level structure
        self.simulation_data = {
            'simulation_id': timestamp,
            'started_at': datetime.now(timezone.utc).isoformat(
                timespec='milliseconds'
            ).replace('+00:00', 'Z'),
            'records': [],
        }

        # ── Internal state ──────────────────────────────────────────────
        self.current_position = None       # dict {x, y, z}
        self.current_record = None         # in-progress navigation record
        self.last_clock = None
        self.record_counter = 0

        # ── Subscribers ─────────────────────────────────────────────────
        self.create_subscription(
            Odometry, self.odom_topic, self._odom_cb, 10
        )

        self.create_subscription(
            String, '/room_command', self._room_command_cb, 10
        )

        self.create_subscription(
            GoalStatusArray,
            '/navigate_to_pose/_action/status',
            self._nav_status_cb,
            10,
        )

        self.create_subscription(
            String, '/room_command_feedback', self._feedback_cb, 10
        )

        self.create_subscription(
            Clock, '/clock', self._clock_cb, 10
        )

        self.get_logger().info(
            f'SimulationLogger ready — logging to {self.log_file}'
        )

    # ════════════════════════ Registry helpers ══════════════════════════

    def _load_registry(self, path):
        if not os.path.exists(path):
            self.get_logger().warn(f'Registry not found: {path}')
            return {}
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return data.get('rooms', {})

    def _build_alias_index(self, rooms):
        """Build alias -> (room_id, room_data) index."""
        index = {}
        for room_id, data in rooms.items():
            index[room_id.lower()] = (room_id, data)
            index[room_id.lower().replace('_', ' ')] = (room_id, data)
            for alias in data.get('aliases', []):
                index[alias.lower()] = (room_id, data)
        return index

    def _resolve_room(self, raw_command):
        """Try to match a raw command string to a room registry entry.

        Uses the same parsing logic as room_interpreter.py so the logged
        room_id is always consistent with what Nav2 actually received.
        """
        import re

        text = raw_command.strip().lower()

        # Strip command prefixes (same list as room_interpreter)
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
        text = re.sub(r'^(?:the|la|le|les|l\')\s+', '', text)
        text = text.strip()

        # Exact match
        if text in self.alias_index:
            return self.alias_index[text]

        # Substring match
        for alias, entry in self.alias_index.items():
            if text in alias or alias in text:
                return entry

        # Partial word overlap
        query_words = set(text.split())
        best, best_score = None, 0
        for alias, entry in self.alias_index.items():
            overlap = len(query_words & set(alias.split()))
            if overlap > best_score:
                best_score = overlap
                best = entry

        if best_score > 0:
            return best

        return None

    # ════════════════════════ Time helpers ══════════════════════════════

    def _sim_time(self):
        """Return simulation time in seconds."""
        if self.last_clock is not None:
            stamp = self.last_clock.clock
            return float(stamp.sec) + float(stamp.nanosec) * 1e-9
        return self.get_clock().now().nanoseconds * 1e-9

    def _wall_time_iso(self):
        return datetime.now(timezone.utc).isoformat(
            timespec='milliseconds'
        ).replace('+00:00', 'Z')

    # ════════════════════════ ROS callbacks ═════════════════════════════

    def _clock_cb(self, msg):
        self.last_clock = msg

    def _odom_cb(self, msg):
        p = msg.pose.pose.position
        self.current_position = {
            'x': round(float(p.x), 4),
            'y': round(float(p.y), 4),
            'z': round(float(p.z), 4),
        }

    def _feedback_cb(self, msg):
        # Used for logging the human-readable feedback alongside records
        if self.current_record is not None:
            self.current_record['feedback'] = msg.data

    def _room_command_cb(self, msg):
        """A new room command has been issued."""
        raw_text = msg.data
        self.get_logger().info(
            f'[SimLogger] Room command received: "{raw_text}"'
        )

        # If a previous navigation was still in progress, close it as
        # interrupted before starting a new record.
        if self.current_record is not None:
            self._finalize_record('interrupted')

        # Resolve which room this command maps to
        resolved = self._resolve_room(raw_text)

        if resolved is None:
            self.get_logger().warn(
                f'[SimLogger] Could not resolve room for "{raw_text}" '
                '— skipping record'
            )
            return

        room_id, room_data = resolved

        self.record_counter += 1

        self.current_record = {
            'record_id': self.record_counter,
            'raw_command': raw_text,
            'room_id': room_id,
            'room_display_name': room_data.get(
                'display_name', room_id.replace('_', ' ')
            ),
            'target_position': {
                'x': float(room_data['x']),
                'y': float(room_data['y']),
            },
            'departure': {
                'wall_time': self._wall_time_iso(),
                'sim_time_s': round(self._sim_time(), 3),
                'robot_position': (
                    dict(self.current_position)
                    if self.current_position
                    else None
                ),
            },
            'arrival': None,
            'duration_s': None,
            'position_error_m': None,
            'status': 'in_progress',
            'feedback': None,
        }

        self.get_logger().info(
            f'[SimLogger] Record #{self.record_counter} started — '
            f'target: {room_id} '
            f'(x={room_data["x"]}, y={room_data["y"]})'
        )

    def _nav_status_cb(self, msg):
        """Monitor Nav2 goal status to detect arrival."""
        if self.current_record is None:
            return

        # GoalStatusArray contains a list of GoalStatus entries.
        # We care about the most recent one.
        if not msg.status_list:
            return

        latest = msg.status_list[-1]

        if latest.status == STATUS_SUCCEEDED:
            self._finalize_record('succeeded')

        elif latest.status == STATUS_ABORTED:
            self._finalize_record('aborted')

        elif latest.status == STATUS_CANCELED:
            self._finalize_record('canceled')

    # ════════════════════════ Record management ════════════════════════

    def _finalize_record(self, status):
        """Close the current navigation record and save to file."""
        if self.current_record is None:
            return

        arrival_time_s = self._sim_time()
        departure_time_s = self.current_record['departure']['sim_time_s']

        self.current_record['arrival'] = {
            'wall_time': self._wall_time_iso(),
            'sim_time_s': round(arrival_time_s, 3),
            'robot_position': (
                dict(self.current_position)
                if self.current_position
                else None
            ),
        }

        # Duration
        self.current_record['duration_s'] = round(
            arrival_time_s - departure_time_s, 3
        )

        # Position error (Euclidean distance between target and actual)
        if self.current_position is not None:
            target = self.current_record['target_position']
            dx = self.current_position['x'] - target['x']
            dy = self.current_position['y'] - target['y']
            self.current_record['position_error_m'] = round(
                math.sqrt(dx * dx + dy * dy), 4
            )

        self.current_record['status'] = status

        self.simulation_data['records'].append(self.current_record)
        self._save()

        self.get_logger().info(
            f'[SimLogger] Record #{self.current_record["record_id"]} '
            f'finalized — status={status}, '
            f'duration={self.current_record["duration_s"]}s, '
            f'error={self.current_record["position_error_m"]}m'
        )

        self.current_record = None

    def _save(self):
        """Write the full simulation JSON to disk."""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.simulation_data, f, indent=2,
                          ensure_ascii=False)
        except Exception as e:
            self.get_logger().error(
                f'[SimLogger] Failed to save log: {e}'
            )


# ═══════════════════════════════ Entry ══════════════════════════════════

def main(args=None):
    rclpy.init(args=args)
    node = SimulationLogger()

    def _shutdown(sig, frame):
        # Finalize any in-progress record before exiting
        if node.current_record is not None:
            node._finalize_record('shutdown')
        node.get_logger().info('SimulationLogger shutting down')
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    try:
        rclpy.spin(node)
    finally:
        if node.current_record is not None:
            node._finalize_record('shutdown')
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()