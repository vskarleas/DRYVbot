#!/usr/bin/env python3
"""
ws_command_bridge.py — WebSocket bridge for remote room commands.

Allows a non-ROS computer on the network to:
  1. Send room commands  →  published to /room_command
  2. Receive navigation status updates (idle, navigating, arrived, error)
  3. Query available rooms from the registry

Protocol (JSON over WebSocket):

  Client → Server:
    {"type": "room_command", "room": "salle 101"}
    {"type": "list_rooms"}

  Server → Client:
    {"type": "status", "state": "idle"}
    {"type": "status", "state": "navigating", "target": "salle_101",
     "target_position": {"x": -8.1, "y": -6.62}}
    {"type": "status", "state": "arrived", "target": "salle_101",
     "robot_position": {"x": -8.09, "y": -6.60},
     "position_error_m": 0.023, "duration_s": 14.2}
    {"type": "status", "state": "aborted", "target": "salle_101"}
    {"type": "rooms", "rooms": {...}}
    {"type": "feedback", "text": "Navigating to salle 101 (x=-8.1, y=-6.62)"}
    {"type": "error", "message": "Room not found: xyz"}
    {"type": "ack", "command": "room_command", "room": "salle 101"}

WebSocket server listens on 0.0.0.0:<port> (default 9090).

Subscribes:
    /room_command_feedback              (std_msgs/String)
    /navigate_to_pose/_action/status    (action_msgs/GoalStatusArray)
    /bcr_bot/odom                       (nav_msgs/Odometry)
    /clock                              (rosgraph_msgs/Clock)

Publishes:
    /room_command                       (std_msgs/String)

Parameters:
    ws_port         (int)    — WebSocket server port (default 9090)
    room_registry   (str)    — path to room_registry.yaml
    odom_topic      (str)    — odometry topic
"""

import asyncio
import json
import math
import os
import signal
import sys
import threading
from datetime import datetime, timezone

import yaml
import rclpy
from rclpy.node import Node

from action_msgs.msg import GoalStatusArray
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String

from ament_index_python.packages import get_package_share_directory

try:
    import websockets
except ImportError:
    print(
        'websockets library not installed. Run:\n'
        '  pip install websockets --break-system-packages',
        file=sys.stderr,
    )
    sys.exit(1)


# Nav2 GoalStatus constants
STATUS_SUCCEEDED = 4
STATUS_ABORTED = 6
STATUS_CANCELED = 5


class WsCommandBridge(Node):

    def __init__(self):
        super().__init__('ws_command_bridge')

        # ── Parameters ──────────────────────────────────────────────────
        self.declare_parameter('ws_port', 9090)
        self.declare_parameter('room_registry', '')
        self.declare_parameter('odom_topic', '/bcr_bot/odom')

        self.ws_port = int(self.get_parameter('ws_port').value)
        registry_path = self.get_parameter('room_registry').value
        self.odom_topic = self.get_parameter('odom_topic').value

        # ── Load room registry ──────────────────────────────────────────
        if not registry_path or not os.path.isabs(registry_path):
            pkg_share = get_package_share_directory('digital_twin')
            if not registry_path:
                registry_path = os.path.join(
                    pkg_share, 'config', 'room_registry.yaml'
                )
            else:
                registry_path = os.path.join(pkg_share, registry_path)

        self.rooms = self._load_registry(registry_path)
        self.alias_index = self._build_alias_index(self.rooms)

        # ── State ───────────────────────────────────────────────────────
        self.current_position = None
        self.last_clock = None
        self.nav_state = 'idle'        # idle | navigating | arrived | aborted
        self.current_target_id = None
        self.current_target_data = None
        self.nav_start_sim_time = None

        # Connected WebSocket clients
        self.ws_clients = set()
        self.ws_loop = None

        # ── ROS publishers ──────────────────────────────────────────────
        self.cmd_pub = self.create_publisher(String, '/room_command', 10)

        # ── ROS subscribers ─────────────────────────────────────────────
        self.create_subscription(
            Odometry, self.odom_topic, self._odom_cb, 10
        )
        self.create_subscription(
            String, '/room_command_feedback', self._feedback_cb, 10
        )
        self.create_subscription(
            GoalStatusArray,
            '/navigate_to_pose/_action/status',
            self._nav_status_cb,
            10,
        )
        self.create_subscription(Clock, '/clock', self._clock_cb, 10)

        # ── Start WebSocket server in background thread ─────────────────
        self.ws_thread = threading.Thread(
            target=self._run_ws_server, daemon=True
        )
        self.ws_thread.start()

        self.get_logger().info(
            f'WsCommandBridge ready — WebSocket on port {self.ws_port}'
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
        index = {}
        for room_id, data in rooms.items():
            index[room_id.lower()] = (room_id, data)
            index[room_id.lower().replace('_', ' ')] = (room_id, data)
            for alias in data.get('aliases', []):
                index[alias.lower()] = (room_id, data)
        return index

    def _resolve_room(self, text):
        """Match a command string to a room entry. Returns (id, data) or None."""
        import re

        text = text.strip().lower()
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

        if text in self.alias_index:
            return self.alias_index[text]

        for alias, entry in self.alias_index.items():
            if text in alias or alias in text:
                return entry

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
        if self.last_clock is not None:
            stamp = self.last_clock.clock
            return float(stamp.sec) + float(stamp.nanosec) * 1e-9
        return self.get_clock().now().nanoseconds * 1e-9

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
        self._broadcast({
            'type': 'feedback',
            'text': msg.data,
        })

    def _nav_status_cb(self, msg):
        if not msg.status_list or self.nav_state != 'navigating':
            return

        latest = msg.status_list[-1]

        if latest.status == STATUS_SUCCEEDED:
            error = None
            if (
                self.current_position is not None
                and self.current_target_data is not None
            ):
                dx = self.current_position['x'] - float(
                    self.current_target_data['x']
                )
                dy = self.current_position['y'] - float(
                    self.current_target_data['y']
                )
                error = round(math.sqrt(dx * dx + dy * dy), 4)

            duration = None
            if self.nav_start_sim_time is not None:
                duration = round(
                    self._sim_time() - self.nav_start_sim_time, 3
                )

            self.nav_state = 'arrived'
            self._broadcast({
                'type': 'status',
                'state': 'arrived',
                'target': self.current_target_id,
                'robot_position': self.current_position,
                'position_error_m': error,
                'duration_s': duration,
            })

            # Reset for next command
            self.nav_state = 'idle'
            self.current_target_id = None
            self.current_target_data = None
            self.nav_start_sim_time = None

        elif latest.status in (STATUS_ABORTED, STATUS_CANCELED):
            state_str = (
                'aborted' if latest.status == STATUS_ABORTED else 'canceled'
            )
            self.nav_state = state_str
            self._broadcast({
                'type': 'status',
                'state': state_str,
                'target': self.current_target_id,
            })
            self.nav_state = 'idle'
            self.current_target_id = None
            self.current_target_data = None
            self.nav_start_sim_time = None

    # ════════════════════════ WebSocket server ══════════════════════════

    def _run_ws_server(self):
        """Run the asyncio WebSocket server in a dedicated thread."""
        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)

        start_server = websockets.serve(
            self._ws_handler,
            '0.0.0.0',
            self.ws_port,
        )

        self.ws_loop.run_until_complete(start_server)
        self.get_logger().info(
            f'WebSocket server listening on ws://0.0.0.0:{self.ws_port}'
        )
        self.ws_loop.run_forever()

    async def _ws_handler(self, websocket, path=None):
        """Handle a single WebSocket client connection."""
        self.ws_clients.add(websocket)
        client_addr = websocket.remote_address
        self.get_logger().info(f'WS client connected: {client_addr}')

        # Send current state on connect
        await websocket.send(json.dumps({
            'type': 'status',
            'state': self.nav_state,
            'target': self.current_target_id,
        }))

        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.ws_clients.discard(websocket)
            self.get_logger().info(f'WS client disconnected: {client_addr}')

    async def _handle_message(self, websocket, raw):
        """Parse and act on an incoming WebSocket message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Invalid JSON',
            }))
            return

        msg_type = data.get('type', '')

        if msg_type == 'room_command':
            room_text = data.get('room', '').strip()
            if not room_text:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': 'Missing "room" field',
                }))
                return

            # Validate against registry before publishing
            resolved = self._resolve_room(room_text)
            if resolved is None:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': f'Room not found: "{room_text}". '
                               f'Available: {list(self.rooms.keys())}',
                }))
                return

            room_id, room_data = resolved

            # Update internal navigation state
            self.nav_state = 'navigating'
            self.current_target_id = room_id
            self.current_target_data = room_data
            self.nav_start_sim_time = self._sim_time()

            # Publish to /room_command so room_interpreter picks it up
            cmd_msg = String()
            cmd_msg.data = room_text
            self.cmd_pub.publish(cmd_msg)

            self.get_logger().info(
                f'[WsBridge] Command from WS: "{room_text}" → {room_id}'
            )

            # Acknowledge to the client
            await websocket.send(json.dumps({
                'type': 'ack',
                'command': 'room_command',
                'room': room_text,
                'resolved_room_id': room_id,
                'target_position': {
                    'x': float(room_data['x']),
                    'y': float(room_data['y']),
                },
            }))

            # Broadcast navigating status to all clients
            self._broadcast({
                'type': 'status',
                'state': 'navigating',
                'target': room_id,
                'target_position': {
                    'x': float(room_data['x']),
                    'y': float(room_data['y']),
                },
            })

        elif msg_type == 'list_rooms':
            rooms_payload = {}
            for room_id, data in self.rooms.items():
                rooms_payload[room_id] = {
                    'x': data['x'],
                    'y': data['y'],
                    'aliases': data.get('aliases', []),
                }
            await websocket.send(json.dumps({
                'type': 'rooms',
                'rooms': rooms_payload,
            }))

        elif msg_type == 'get_status':
            await websocket.send(json.dumps({
                'type': 'status',
                'state': self.nav_state,
                'target': self.current_target_id,
                'robot_position': self.current_position,
            }))

        else:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Unknown message type: "{msg_type}". '
                           'Valid types: room_command, list_rooms, get_status',
            }))

    def _broadcast(self, payload):
        """Send a JSON payload to all connected WebSocket clients."""
        if not self.ws_clients or self.ws_loop is None:
            return

        message = json.dumps(payload)

        async def _send_all():
            disconnected = set()
            for ws in self.ws_clients:
                try:
                    await ws.send(message)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(ws)
            self.ws_clients -= disconnected

        asyncio.run_coroutine_threadsafe(_send_all(), self.ws_loop)


# ═══════════════════════════════ Entry ══════════════════════════════════

def main(args=None):
    rclpy.init(args=args)
    node = WsCommandBridge()

    def _shutdown(sig, frame):
        node.get_logger().info('WsCommandBridge shutting down')
        if node.ws_loop is not None:
            node.ws_loop.call_soon_threadsafe(node.ws_loop.stop)
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    try:
        rclpy.spin(node)
    finally:
        if node.ws_loop is not None:
            node.ws_loop.call_soon_threadsafe(node.ws_loop.stop)
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()