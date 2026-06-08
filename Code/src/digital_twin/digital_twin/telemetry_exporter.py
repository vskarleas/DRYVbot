#!/usr/bin/env python3

import os
import json
import math
import urllib.request
import urllib.error
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import Twist, PoseStamped, PoseArray
from rosgraph_msgs.msg import Clock


class TelemetryExporter(Node):
    def __init__(self):
        super().__init__('telemetry_exporter')

        # =========================
        # Parameters
        # =========================
        self.declare_parameter('target_url', 'https://proj-sys880.calme2me.com/api/data')
        self.declare_parameter('send_frequency_hz', 1.0)

        self.declare_parameter('save_to_file', True)
        self.declare_parameter(
            'log_file_path',
            '/home/bakalem/Documents/CloudTwin/Code/telemetry_logs/telemetry_data.jsonl'
        )

        self.declare_parameter('frame_id', 'map')

        self.declare_parameter('odom_topic', '/bcr_bot/odom')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('plan_topic', '/plan')
        self.declare_parameter('goal_topic', '/goal_pose')
        self.declare_parameter('obstacles_topic', '/people_positions')
        self.declare_parameter('clock_topic', '/clock')

        self.declare_parameter('trajectory_history_size', 100)
        self.declare_parameter('max_plan_points', 150)

        self.declare_parameter('obstacle_on_path_threshold_m', 0.75)
        self.declare_parameter('base_path_weight', 1.0)
        self.declare_parameter('obstacle_weight_increment', 0.25)

        self.target_url = self.get_parameter('target_url').value
        self.send_frequency_hz = float(self.get_parameter('send_frequency_hz').value)
        
        self.save_to_file = bool(self.get_parameter('save_to_file').value)
        self.log_file_path = self.get_parameter('log_file_path').value

        if self.target_url and not self.target_url.startswith(('http://', 'https://')):
            self.target_url = 'https://' + self.target_url

        if self.save_to_file and self.log_file_path:
            log_dir = os.path.dirname(os.path.expanduser(self.log_file_path))
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

        self.frame_id = self.get_parameter('frame_id').value

        self.odom_topic = self.get_parameter('odom_topic').value
        self.cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        self.plan_topic = self.get_parameter('plan_topic').value
        self.goal_topic = self.get_parameter('goal_topic').value
        self.obstacles_topic = self.get_parameter('obstacles_topic').value
        self.clock_topic = self.get_parameter('clock_topic').value

        self.trajectory_history_size = int(
            self.get_parameter('trajectory_history_size').value
        )
        self.max_plan_points = int(
            self.get_parameter('max_plan_points').value
        )

        self.obstacle_on_path_threshold_m = float(
            self.get_parameter('obstacle_on_path_threshold_m').value
        )
        self.base_path_weight = float(
            self.get_parameter('base_path_weight').value
        )
        self.obstacle_weight_increment = float(
            self.get_parameter('obstacle_weight_increment').value
        )

        if self.send_frequency_hz <= 0.0:
            self.get_logger().warn(
                'send_frequency_hz must be > 0. Using 1.0 Hz instead.'
            )
            self.send_frequency_hz = 1.0

        # =========================
        # Internal state
        # =========================
        self.last_odom = None
        self.last_cmd_vel = None
        self.last_plan = None
        self.last_goal = None
        self.last_obstacles = None
        self.last_clock = None

        self.previous_velocity_time = None
        self.previous_linear_velocity = None
        self.previous_angular_velocity = None

        self.current_linear_acceleration = 0.0
        self.current_angular_acceleration = 0.0

        self.current_trajectory_points = []
        self.current_trajectory_length = 0.0

        # =========================
        # Subscribers
        # =========================
        self.create_subscription(
            Odometry,
            self.odom_topic,
            self.odom_callback,
            10
        )

        self.create_subscription(
            Twist,
            self.cmd_vel_topic,
            self.cmd_vel_callback,
            10
        )

        self.create_subscription(
            Path,
            self.plan_topic,
            self.plan_callback,
            10
        )

        self.create_subscription(
            PoseStamped,
            self.goal_topic,
            self.goal_callback,
            10
        )

        self.create_subscription(
            PoseArray,
            self.obstacles_topic,
            self.obstacles_callback,
            10
        )

        self.create_subscription(
            Clock,
            self.clock_topic,
            self.clock_callback,
            10
        )

        # =========================
        # Timer
        # =========================
        timer_period = 1.0 / self.send_frequency_hz
        self.timer = self.create_timer(timer_period, self.timer_callback)

        self.get_logger().info('Telemetry exporter started.')
        self.get_logger().info(f'Target URL: {self.target_url if self.target_url else "not set"}')
        self.get_logger().info(f'Send frequency: {self.send_frequency_hz} Hz')

    # ============================================================
    # ROS callbacks
    # ============================================================

    def odom_callback(self, msg):
        self.last_odom = msg

        position = msg.pose.pose.position
        new_point = {
            'x': float(position.x),
            'y': float(position.y),
            'z': float(position.z),
        }

        if len(self.current_trajectory_points) > 0:
            previous = self.current_trajectory_points[-1]
            dx = new_point['x'] - previous['x']
            dy = new_point['y'] - previous['y']
            dz = new_point['z'] - previous['z']
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)

            # Ignore tiny odometry noise.
            if distance > 0.01:
                self.current_trajectory_length += distance
                self.current_trajectory_points.append(new_point)
        else:
            self.current_trajectory_points.append(new_point)

        if len(self.current_trajectory_points) > self.trajectory_history_size:
            self.current_trajectory_points.pop(0)

        self.update_acceleration(msg)

    def cmd_vel_callback(self, msg):
        self.last_cmd_vel = msg

    def plan_callback(self, msg):
        self.last_plan = msg

    def goal_callback(self, msg):
        self.last_goal = msg

    def obstacles_callback(self, msg):
        self.last_obstacles = msg

    def clock_callback(self, msg):
        self.last_clock = msg

    # ============================================================
    # Data computation
    # ============================================================

    def update_acceleration(self, odom_msg):
        current_time = self.get_time_from_msg(odom_msg.header.stamp)
        current_linear_velocity = odom_msg.twist.twist.linear.x
        current_angular_velocity = odom_msg.twist.twist.angular.z

        if self.previous_velocity_time is not None:
            dt = current_time - self.previous_velocity_time

            if dt > 1e-6:
                self.current_linear_acceleration = (
                    current_linear_velocity - self.previous_linear_velocity
                ) / dt

                self.current_angular_acceleration = (
                    current_angular_velocity - self.previous_angular_velocity
                ) / dt

        self.previous_velocity_time = current_time
        self.previous_linear_velocity = current_linear_velocity
        self.previous_angular_velocity = current_angular_velocity

    def quaternion_to_yaw(self, q):
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def get_time_from_msg(self, stamp):
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    def get_simulation_time(self):
        if self.last_clock is not None:
            return self.get_time_from_msg(self.last_clock.clock)

        return self.get_clock().now().nanoseconds * 1e-9

    def get_datetime_utc(self):
        return datetime.now(timezone.utc).isoformat(
            timespec='milliseconds'
        ).replace('+00:00', 'Z')

    def compute_path_length(self, points):
        if len(points) < 2:
            return 0.0

        length = 0.0
        for i in range(1, len(points)):
            dx = points[i]['x'] - points[i - 1]['x']
            dy = points[i]['y'] - points[i - 1]['y']
            dz = points[i]['z'] - points[i - 1]['z']
            length += math.sqrt(dx * dx + dy * dy + dz * dz)

        return length

    def sample_points(self, points, max_points):
        if len(points) <= max_points:
            return points

        step = max(1, math.ceil(len(points) / max_points))
        sampled = points[::step]

        if sampled[-1] != points[-1]:
            sampled.append(points[-1])

        return sampled

    def extract_plan_points(self):
        if self.last_plan is None:
            return []

        points = []
        for pose_stamped in self.last_plan.poses:
            p = pose_stamped.pose.position
            points.append({
                'x': float(p.x),
                'y': float(p.y),
                'z': float(p.z),
            })

        return self.sample_points(points, self.max_plan_points)

    def get_effective_goal_position(self, plan_points):
        """
        Return the navigation goal position.

        Priority:
        1. Use the last point of the Nav2 planned path.
        2. Otherwise, use /goal_pose if available.
        3. Otherwise, return None.
        """
        if plan_points:
            return plan_points[-1]

        if self.last_goal is not None:
            goal_position = self.last_goal.pose.position
            return {
                'x': float(goal_position.x),
                'y': float(goal_position.y),
                'z': float(goal_position.z),
            }

        return None

    def extract_obstacles(self):
        if self.last_obstacles is None:
            return []

        obstacles = []
        for pose in self.last_obstacles.poses:
            obstacles.append({
                'x': float(pose.position.x),
                'y': float(pose.position.y),
                'z': float(pose.position.z),
            })

        return obstacles

    def distance_between_xy(self, a, b):
        dx = a['x'] - b['x']
        dy = a['y'] - b['y']
        return math.sqrt(dx * dx + dy * dy)

    def compute_distance_to_goal(self, robot_position, goal_position):
        if goal_position is None:
            return 0.0

        dx = goal_position['x'] - robot_position['x']
        dy = goal_position['y'] - robot_position['y']
        dz = goal_position['z'] - robot_position['z']

        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def count_obstacles_on_path(self, obstacles, plan_points):
        if not obstacles or not plan_points:
            return 0

        count = 0

        for obstacle in obstacles:
            min_distance = min(
                self.distance_between_xy(obstacle, point)
                for point in plan_points
            )

            if min_distance <= self.obstacle_on_path_threshold_m:
                count += 1

        return count

    def compute_navigation_cost(self, planned_length, obstacles_on_path):
        obstacle_cost = obstacles_on_path * 10.0
        return planned_length + obstacle_cost

    def compute_path_weight(self, obstacles_on_path):
        return (
            self.base_path_weight
            + obstacles_on_path * self.obstacle_weight_increment
        )

    def get_navigation_state(self, distance_to_goal, has_plan):
        if not has_plan:
            return 'idle'

        if distance_to_goal < 0.3:
            return 'goal_reached'

        return 'navigating'

    # ============================================================
    # JSON construction and sending
    # ============================================================

    def build_payload(self):
        if self.last_odom is None:
            return None

        odom = self.last_odom

        robot_position = {
            'x': float(odom.pose.pose.position.x),
            'y': float(odom.pose.pose.position.y),
            'z': float(odom.pose.pose.position.z),
        }

        yaw_rad = self.quaternion_to_yaw(odom.pose.pose.orientation)
        yaw_deg = math.degrees(yaw_rad)

        linear_x = float(odom.twist.twist.linear.x)
        linear_y = float(odom.twist.twist.linear.y)
        angular_z = float(odom.twist.twist.angular.z)

        current_trajectory_points = self.current_trajectory_points

        plan_points = self.extract_plan_points()
        planned_length = self.compute_path_length(plan_points)

        obstacles = self.extract_obstacles()
        obstacles_on_path = self.count_obstacles_on_path(obstacles, plan_points)

        effective_goal = self.get_effective_goal_position(plan_points)
        distance_to_goal = self.compute_distance_to_goal(robot_position, effective_goal)
        navigation_state = self.get_navigation_state(
            distance_to_goal,
            has_plan=len(plan_points) > 0
        )

        navigation_cost = self.compute_navigation_cost(
            planned_length,
            obstacles_on_path
        )

        path_weight = self.compute_path_weight(obstacles_on_path)

        if effective_goal is not None:
            goal_payload = {
                'x': float(effective_goal['x']),
                'y': float(effective_goal['y']),
                'z': float(effective_goal['z']),
                'distance_restante_m': float(distance_to_goal),
            }
        else:
            goal_payload = {
                'x': 0.0,
                'y': 0.0,
                'z': 0.0,
                'distance_restante_m': 0.0,
            }

        payload = {
            'datetime': self.get_datetime_utc(),

            'bot': {
                'position': robot_position,

                'orientation': {
                    'yaw_rad': float(yaw_rad),
                    'yaw_deg': float(yaw_deg),
                },

                'vitesse': {
                    'lineaire_x': linear_x,
                    'lineaire_y': linear_y,
                    'angulaire_z': angular_z,
                },

                'acceleration': {
                    'lineaire': float(self.current_linear_acceleration),
                    'angulaire': float(self.current_angular_acceleration),
                },

                'trajectoire_courante': {
                    'points': current_trajectory_points,
                    'longueur_parcourue_m': float(self.current_trajectory_length),
                },

                'trajectoire_planifiee': {
                    'points': plan_points,
                    'nombre_points': len(plan_points),
                    'longueur_planifiee_m': float(planned_length),
                },

                'goal': goal_payload,

                'navigation': {
                    'etat': navigation_state,
                    'cout_navigation': float(navigation_cost),
                    'poids_trajectoire_courante': float(path_weight),
                },
            },

            'persons': obstacles,
        }

        return payload

    def save_payload_to_file(self, payload):
        if not self.save_to_file or not self.log_file_path:
            return

        file_path = os.path.expanduser(self.log_file_path)

        try:
            with open(file_path, 'a', encoding='utf-8') as file:
                file.write(json.dumps(payload, ensure_ascii=False) + '\n')

        except Exception as error:
            self.get_logger().error(
                f'Failed to save telemetry to file {file_path}: {error}'
            )

    def send_payload(self, payload):
        json_data = json.dumps(payload).encode('utf-8')

        if not self.target_url:
            self.get_logger().info(json.dumps(payload, indent=2))
            return

        request = urllib.request.Request(
            self.target_url,
            data=json_data,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST'
        )

        try:
            with urllib.request.urlopen(request, timeout=1.0) as response:
                status_code = response.getcode()

            self.get_logger().info(
                f'Telemetry sent successfully. HTTP status: {status_code}'
            )

        except urllib.error.URLError as error:
            self.get_logger().warn(
                f'Failed to send telemetry to {self.target_url}: {error}'
            )

        except Exception as error:
            self.get_logger().error(
                f'Unexpected telemetry export error: {error}'
            )

    def timer_callback(self):
        payload = self.build_payload()

        if payload is None:
            self.get_logger().warn(
                'Waiting for odometry data before sending telemetry...',
                throttle_duration_sec=5.0
            )
            return

        self.save_payload_to_file(payload)
        self.send_payload(payload)


def main(args=None):
    rclpy.init(args=args)
    node = TelemetryExporter()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()