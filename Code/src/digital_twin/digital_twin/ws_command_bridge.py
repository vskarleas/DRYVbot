#!/usr/bin/env python3
"""WebSocket bridge for remote room commands."""

import asyncio
import json
import math
import os
import signal
import sys
import threading

import yaml
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

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


STATUS_SUCCEEDED = 4
STATUS_ABORTED = 6
STATUS_CANCELED = 5


class WsCommandBridge(Node):

	def __init__(self):
		super().__init__('ws_command_bridge')

		self.declare_parameter('ws_port', 9090)
		self.declare_parameter('room_registry', '')
		self.declare_parameter('odom_topic', '/bcr_bot/odom')

		self.ws_port = int(self.get_parameter('ws_port').value)
		registry_path = self.get_parameter('room_registry').value
		self.odom_topic = self.get_parameter('odom_topic').value

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

		self.current_position = None
		self.last_clock = None
		self.nav_state = 'idle'
		self.current_target_id = None
		self.current_target_data = None
		self.nav_start_sim_time = None

		self.ws_clients = set()
		self.ws_loop = None

		self.cmd_pub = self.create_publisher(String, '/room_command', 10)

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

		clock_qos = QoSProfile(
			depth=10,
			reliability=ReliabilityPolicy.BEST_EFFORT,
			durability=DurabilityPolicy.VOLATILE,
		)
		self.create_subscription(Clock, '/clock', self._clock_cb, clock_qos)

		self.ws_thread = threading.Thread(
			target=self._run_ws_server, daemon=True
		)
		self.ws_thread.start()

		self.get_logger().info(
			f'WsCommandBridge ready - WebSocket on port {self.ws_port}'
		)

	def _load_registry(self, path):
		if not os.path.exists(path):
			self.get_logger().warn(f'Registry not found: {path}')
			return {}
		with open(path, 'r', encoding='utf-8') as f:
			data = yaml.safe_load(f) or {}
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
		text = re.sub(r"^(?:the|la|le|les|l')\s+", '', text)
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

	def _sim_time(self):
		if self.last_clock is not None:
			stamp = self.last_clock.clock
			return float(stamp.sec) + float(stamp.nanosec) * 1e-9
		return self.get_clock().now().nanoseconds * 1e-9

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
				duration = round(self._sim_time() - self.nav_start_sim_time, 3)

			self.nav_state = 'arrived'
			self._broadcast({
				'type': 'status',
				'state': 'arrived',
				'target': self.current_target_id,
				'robot_position': self.current_position,
				'position_error_m': error,
				'duration_s': duration,
			})

			self.nav_state = 'idle'
			self.current_target_id = None
			self.current_target_data = None
			self.nav_start_sim_time = None

		elif latest.status in (STATUS_ABORTED, STATUS_CANCELED):
			state_str = 'aborted' if latest.status == STATUS_ABORTED else 'canceled'
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

	def _run_ws_server(self):
		"""Run the asyncio WebSocket server in a dedicated thread."""
		self.ws_loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self.ws_loop)
		self.ws_loop.create_task(self._ws_server_main())
		self.ws_loop.run_forever()

	async def _ws_server_main(self):
		async with websockets.serve(
			self._ws_handler,
			'0.0.0.0',
			self.ws_port,
		):
			self.get_logger().info(
				f'WebSocket server listening on ws://0.0.0.0:{self.ws_port}'
			)
			await asyncio.Future()

	async def _ws_handler(self, websocket, path=None):
		self.ws_clients.add(websocket)
		client_addr = websocket.remote_address
		self.get_logger().info(f'WS client connected: {client_addr}')

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

			resolved = self._resolve_room(room_text)
			if resolved is None:
				await websocket.send(json.dumps({
					'type': 'error',
					'message': f'Room not found: "{room_text}". Available: {list(self.rooms.keys())}',
				}))
				return

			room_id, room_data = resolved

			self.nav_state = 'navigating'
			self.current_target_id = room_id
			self.current_target_data = room_data
			self.nav_start_sim_time = self._sim_time()

			cmd_msg = String()
			cmd_msg.data = room_text
			self.cmd_pub.publish(cmd_msg)

			self.get_logger().info(
				f'[WsBridge] Command from WS: "{room_text}" -> {room_id}'
			)

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
				'message': f'Unknown message type: "{msg_type}". Valid types: room_command, list_rooms, get_status',
			}))

	def _broadcast(self, payload):
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
