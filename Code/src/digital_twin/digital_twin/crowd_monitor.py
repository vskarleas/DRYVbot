#!/usr/bin/env python3
"""
crowd_monitor.py — Dynamic map overlay for Nav2 crowd-aware replanning.

Reads the static map from map_server (/map), tracks moving humans via
/people_positions (PoseArray from obstacle_spawner), computes a Gaussian
density field around each person, and publishes two grids:

  /map_dynamic   — static map + crowd zones stamped as walls (OccupancyGrid 100)
                   → Nav2 global_costmap static_layer subscribes here
  /crowd_density — density-only overlay for Foxglove visualisation
"""

import signal
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseArray


class CrowdMonitor(Node):

    def __init__(self):
        super().__init__('crowd_monitor')

        # ── Parameters ──────────────────────────────────────────────────
        self.declare_parameter('publish_rate', 2.0)
        self.declare_parameter('gaussian_sigma', 1.4)    # metres
        self.declare_parameter('density_scale', 100.0)    # peak value per person
        self.declare_parameter('lethal_threshold', 25)    # 0-100 ; above → wall

        self.rate       = self.get_parameter('publish_rate').value
        self.sigma      = self.get_parameter('gaussian_sigma').value
        self.scale      = self.get_parameter('density_scale').value
        self.lethal_thr = self.get_parameter('lethal_threshold').value

        # ── Internal state ──────────────────────────────────────────────
        self.static_map_msg = None          # latest OccupancyGrid from /map
        self.static_grid    = None          # (H, W) int8 numpy copy
        self.human_positions: list = []     # [(x, y), …] world frame

        # ── QoS ─────────────────────────────────────────────────────────
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        # ── Subscribers ─────────────────────────────────────────────────
        self.create_subscription(
            OccupancyGrid, '/map', self._on_map, map_qos)
        self.create_subscription(
            PoseArray, '/people_positions', self._on_people, 10)

        # ── Publishers ──────────────────────────────────────────────────
        self.map_pub = self.create_publisher(
            OccupancyGrid, '/map_dynamic', map_qos)
        self.density_pub = self.create_publisher(
            OccupancyGrid, '/crowd_density', 10)

        # ── Periodic update ─────────────────────────────────────────────
        self.create_timer(1.0 / self.rate, self._tick)

        self.get_logger().info(
            f'CrowdMonitor ready — sigma={self.sigma}m, '
            f'rate={self.rate}Hz, lethal_threshold={self.lethal_thr}')

    # ═══════════════════════════ Callbacks ═══════════════════════════════

    def _on_map(self, msg: OccupancyGrid):
        """Cache the static map published by map_server."""
        self.static_map_msg = msg
        self.static_grid = np.array(msg.data, dtype=np.int8).reshape(
            msg.info.height, msg.info.width)
        self.get_logger().info(
            f'Static map: {msg.info.width}×{msg.info.height}, '
            f'res={msg.info.resolution}m/px')

    def _on_people(self, msg: PoseArray):
        """Extract human positions from obstacle_spawner PoseArray."""
        self.human_positions = [
            (pose.position.x, pose.position.y)
            for pose in msg.poses
        ]

    # ═══════════════════════════ Main loop ══════════════════════════════

    def _tick(self):
        if self.static_map_msg is None:
            return

        info = self.static_map_msg.info
        h, w = info.height, info.width
        res   = info.resolution
        ox    = info.origin.position.x
        oy    = info.origin.position.y

        # ── Gaussian density field ──────────────────────────────────────
        density = np.zeros((h, w), dtype=np.float64)
        sigma_px  = self.sigma / res
        radius_px = int(np.ceil(3.0 * sigma_px))

        for wx, wy in self.human_positions:
            col = int((wx - ox) / res)
            row = int((wy - oy) / res)

            r0, r1 = max(0, row - radius_px), min(h, row + radius_px + 1)
            c0, c1 = max(0, col - radius_px), min(w, col + radius_px + 1)
            if r0 >= r1 or c0 >= c1:
                continue

            rr, cc = np.meshgrid(
                np.arange(r0, r1), np.arange(c0, c1), indexing='ij')
            d2 = ((rr - row) ** 2 + (cc - col) ** 2).astype(np.float64)
            density[r0:r1, c0:c1] += np.exp(-d2 / (2.0 * sigma_px ** 2))

        # Scale so one person's centre = density_scale (default 100)
        density_scaled = (density * self.scale).clip(0, 100)

        stamp = self.get_clock().now().to_msg()

        # ── 1. Publish density visualisation for Foxglove ───────────────
        vis_msg = OccupancyGrid()
        vis_msg.header.stamp    = stamp
        vis_msg.header.frame_id = 'map'
        vis_msg.info            = info
        vis_msg.data = density_scaled.astype(np.int8).flatten().tolist()
        self.density_pub.publish(vis_msg)

        # ── 2. Publish combined map for Nav2 ────────────────────────────
        combined = self.static_grid.copy().astype(np.int16)
        # Stamp crowd zones as walls (100 = occupied)
        crowd_wall = density_scaled >= self.lethal_thr
        combined[crowd_wall] = 100
        combined = combined.clip(-1, 100).astype(np.int8)

        dyn_msg = OccupancyGrid()
        dyn_msg.header.stamp    = stamp
        dyn_msg.header.frame_id = 'map'
        dyn_msg.info            = info
        dyn_msg.data = combined.flatten().tolist()
        self.map_pub.publish(dyn_msg)


# ═══════════════════════════════ Entry ══════════════════════════════════

def main(args=None):
    rclpy.init(args=args)
    node = CrowdMonitor()

    def _shutdown(sig, frame):
        node.get_logger().info('Shutting down CrowdMonitor')
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