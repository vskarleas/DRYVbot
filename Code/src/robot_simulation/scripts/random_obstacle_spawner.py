#!/usr/bin/env python3
"""Spawn map-aware controlled human obstacles in Gazebo Classic."""

from __future__ import annotations

import math
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Optional


import rclpy
from ament_index_python.packages import get_package_share_directory
from gazebo_msgs.msg import EntityState
from gazebo_msgs.srv import DeleteEntity, SetEntityState, SpawnEntity
from geometry_msgs.msg import Point, Pose, PoseArray, Quaternion
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

from controlled_emergency_scenario import CONTROLLED_EMERGENCY_ROUTES
from controlled_patrol_scenarios import CONTROLLED_PATROL_SCENARIOS
from random_obstacle_core import OccupancyMap, Point2D


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


VALID_SCENARIOS = {
    "normal",
    "crowd",
    "emergency",
}


@dataclass
class RandomHuman:
    """Mutable state for one simulated person."""

    name: str
    x: float
    y: float
    speed: float
    state: str = "normal"
    waypoints: list[Point2D] = field(default_factory=list)
    yaw: float = 0.0
    emergency_member: bool = False
    emergency_release_time: Optional[float] = None
    spawned: bool = False
    state_request_pending: bool = False
    state_request_started: float = 0.0
    state_request_id: int = 0
    controlled_route_index: Optional[int] = None

    @property
    def position(self) -> Point2D:
        return self.x, self.y


class RandomObstacleSpawner(Node):
    """Generate and move collision-aware controlled humans on an occupancy map."""

    def __init__(self):
        super().__init__("random_obstacle_spawner")
        # Gazebo /clock can be unavailable or QoS-incompatible during startup.
        # A steady clock keeps spawning and movement alive in that situation.
        self.steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self._declare_parameters()
        self._read_parameters()
        self._validate_parameters()

        clearance = self.human_radius + self.min_wall_distance
        self.map = OccupancyMap.load(self.map_yaml, clearance)

        self.get_logger().info(
            f"Loaded map {self.map.width}x{self.map.height} at "
            f"{self.map.resolution:.3f} m/cell; "
            f"{self.map.valid_cell_count} valid cells after "
            f"{clearance:.2f} m clearance"
        )
        self.get_logger().info(
            f"Controlled obstacle scenario={self.scenario}"
        )

        self.people_pub = self.create_publisher(
            PoseArray, "/people_positions", 10
        )
        self.marker_pub = self.create_publisher(
            MarkerArray, "/people_markers", 10
        )
        self.spawn_client = self.create_client(SpawnEntity, "/spawn_entity")
        self.set_state_client = self.create_client(
            SetEntityState, "/set_entity_state"
        )
        self.delete_client = self.create_client(
            DeleteEntity, "/delete_entity"
        )

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.people: list[RandomHuman] = []
        self.current_robot_position = self.fallback_robot_position
        self.pending_spawns = 0
        self.next_spawn_index = 0
        self.next_emergency_time = self.emergency_start_time
        self.emergency_cycle = 0
        self.emergency_cycle_active = False
        self.next_gazebo_state_update = 0.0
        self.movement_timer = None
        self.spawn_timeout_timer = None
        self.movement_started = False
        self.cleaned_up = False
        self.startup_started = time.monotonic()
        self.startup_timer = self.create_timer(
            0.25, self._startup_tick, clock=self.steady_clock
        )

    def _emergency_in_progress(self) -> bool:
        return self.emergency_cycle_active or any(
            human.state in (
                "moving_to_emergency",
                "waiting_emergency",
                "dispersing",
            )
            for human in self.people
            if human.spawned
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("scenario", "normal")
        self.declare_parameter("map_yaml", "")
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("fallback_robot_position", [0.0, 2.0])
        self.declare_parameter("robot_tf_timeout", 5.0)
        self.declare_parameter("gazebo_service_timeout", 30.0)
        self.declare_parameter("spawn_response_timeout", 30.0)

        self.declare_parameter("human_radius", 0.28)
        self.declare_parameter("min_wall_distance", 0.50)
        self.declare_parameter("min_robot_distance", 2.0)
        self.declare_parameter("min_people_distance", 0.60)
        self.declare_parameter("moving_people_distance", 0.60)
        self.declare_parameter("arrival_tolerance", 0.08)

        self.declare_parameter("update_rate", 10.0)
        self.declare_parameter("gazebo_state_update_rate", 5.0)
        self.declare_parameter("gazebo_state_timeout", 1.0)

        self.declare_parameter("emergency_start_time", 30.0)
        self.declare_parameter("emergency_duration", 80.0)
        self.declare_parameter("controlled_emergency_speed", 1.0)
        self.declare_parameter("emergency_loop", True)
        self.declare_parameter("emergency_repeat_interval", 120.0)

    def _read_parameters(self) -> None:
        def value(name):
            return self.get_parameter(name).value

        self.scenario = str(value("scenario"))
        map_yaml = str(value("map_yaml"))
        if not map_yaml:
            package_dir = get_package_share_directory("robot_simulation")
            map_yaml = os.path.join(package_dir, "maps", "hospital_map.yaml")
        self.map_yaml = map_yaml
        self.map_frame = str(value("map_frame"))
        self.robot_frame = str(value("robot_frame"))
        fallback = value("fallback_robot_position")
        self.fallback_robot_position = (float(fallback[0]), float(fallback[1]))
        self.robot_tf_timeout = float(value("robot_tf_timeout"))
        self.gazebo_service_timeout = float(value("gazebo_service_timeout"))
        self.spawn_response_timeout = float(value("spawn_response_timeout"))

        self.human_radius = float(value("human_radius"))
        self.min_wall_distance = float(value("min_wall_distance"))
        self.min_robot_distance = float(value("min_robot_distance"))
        self.min_people_distance = float(value("min_people_distance"))
        self.moving_people_distance = float(value("moving_people_distance"))
        self.arrival_tolerance = float(value("arrival_tolerance"))

        self.update_rate = float(value("update_rate"))
        self.gazebo_state_update_rate = float(value("gazebo_state_update_rate"))
        self.gazebo_state_timeout = float(value("gazebo_state_timeout"))

        self.emergency_start_time = float(value("emergency_start_time"))
        self.emergency_duration = float(value("emergency_duration"))
        self.controlled_emergency_speed = float(value("controlled_emergency_speed"))
        self.emergency_loop = bool(value("emergency_loop"))
        self.emergency_repeat_interval = float(value("emergency_repeat_interval"))

    def _validate_parameters(self) -> None:
        if self.scenario not in VALID_SCENARIOS:
            raise ValueError(
                f"Unknown controlled scenario {self.scenario!r}; "
                f"expected one of {sorted(VALID_SCENARIOS)}"
            )
        if self.update_rate <= 0.0:
            raise ValueError("update_rate must be positive")
        if self.gazebo_state_update_rate <= 0.0:
            raise ValueError("gazebo_state_update_rate must be positive")
        if self.gazebo_state_timeout <= 0.0:
            raise ValueError("gazebo_state_timeout must be positive")
        if self.spawn_response_timeout <= 0.0:
            raise ValueError("spawn_response_timeout must be positive")
        distances = (
            self.human_radius,
            self.min_wall_distance,
            self.min_robot_distance,
            self.min_people_distance,
            self.moving_people_distance,
            self.arrival_tolerance,
            self.emergency_start_time,
            self.emergency_duration,
            self.controlled_emergency_speed,
        )
        if any(distance < 0.0 for distance in distances):
            raise ValueError("Distance parameters cannot be negative")
        if self.min_people_distance < 2.0 * self.human_radius:
            raise ValueError(
                "min_people_distance must be at least twice human_radius "
                "to prevent model overlap"
            )
        if self.moving_people_distance < 2.0 * self.human_radius:
            raise ValueError(
                "moving_people_distance must be at least twice human_radius "
                "to prevent model overlap while walking"
            )
        if self.controlled_emergency_speed <= 0.0:
            raise ValueError("controlled_emergency_speed must be positive")
        if self.emergency_repeat_interval < 0.0:
            raise ValueError("emergency_repeat_interval cannot be negative")

    def _startup_tick(self) -> None:
        elapsed = time.monotonic() - self.startup_started
        services_ready = (
            self.spawn_client.service_is_ready()
            and self.set_state_client.service_is_ready()
            and self.delete_client.service_is_ready()
        )
        if not services_ready:
            if elapsed >= self.gazebo_service_timeout:
                self.startup_timer.cancel()
                message = (
                    "Gazebo services /spawn_entity, /set_entity_state and "
                    "/delete_entity were not ready before timeout"
                )
                self.get_logger().error(message)
                raise RuntimeError(message)
            self.get_logger().info(
                "Waiting for Gazebo entity services...",
                throttle_duration_sec=5.0,
            )
            return

        robot_position = self._lookup_robot_position()
        if robot_position is None and elapsed < self.robot_tf_timeout:
            self.get_logger().warn(
                f"Waiting for TF {self.map_frame} -> {self.robot_frame}...",
                throttle_duration_sec=2.0,
            )
            return
        if robot_position is None:
            robot_position = self.fallback_robot_position
            self.get_logger().warn(
                "Robot TF unavailable; using fallback position "
                f"({robot_position[0]:.2f}, {robot_position[1]:.2f})"
            )
        else:
            self.get_logger().info(
                f"Robot position from TF: ({robot_position[0]:.2f}, "
                f"{robot_position[1]:.2f})"
            )

        self.current_robot_position = robot_position
        self.startup_timer.cancel()
        self._generate_people()
        if not self.people:
            message = "Could not generate any valid controlled humans"
            self.get_logger().error(message)
            raise RuntimeError(message)
        self._spawn_people()

    def _lookup_robot_position(self) -> Optional[Point2D]:
        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame, self.robot_frame, Time()
            )
        except TransformException:
            return None
        translation = transform.transform.translation
        return float(translation.x), float(translation.y)

    def _robot_exclusion_points(self) -> list[Point2D]:
        points: list[Point2D] = []
        for point in (
            getattr(self, "current_robot_position", None),
            getattr(self, "fallback_robot_position", None),
        ):
            if point is None:
                continue
            candidate = (float(point[0]), float(point[1]))
            if any(math.dist(candidate, existing) < 0.05 for existing in points):
                continue
            points.append(candidate)
        return points

    def _outside_robot_keepout(self, point: Point2D) -> bool:
        return all(
            math.dist(point, robot_position) >= self.min_robot_distance
            for robot_position in self._robot_exclusion_points()
        )

    def _generate_people(self) -> None:
        if self.scenario == "emergency":
            self._generate_controlled_emergency_people()
            return
        self._generate_controlled_patrol_people()

    def _generate_controlled_patrol_people(self) -> None:
        routes = CONTROLLED_PATROL_SCENARIOS[self.scenario]
        self._validate_controlled_patrol_routes(routes)
        self.people = []
        for index, route in enumerate(routes):
            self.people.append(
                RandomHuman(
                    name=route.name,
                    x=route.start[0],
                    y=route.start[1],
                    speed=route.speed,
                    waypoints=list(route.waypoints),
                    controlled_route_index=index,
                )
            )

        self.get_logger().info(
            f"Generated {len(self.people)} fixed patrol humans "
            f"for controlled {self.scenario}"
        )

    def _generate_controlled_emergency_people(self) -> None:
        self._validate_controlled_emergency_routes()
        self.people = []
        for index, route in enumerate(CONTROLLED_EMERGENCY_ROUTES):
            start = route.start
            self.people.append(
                RandomHuman(
                    name=route.name,
                    x=start[0],
                    y=start[1],
                    speed=self.controlled_emergency_speed,
                    controlled_route_index=index,
                )
            )

        self.get_logger().info(
            f"Generated {len(self.people)} fixed humans for controlled "
            "emergency"
        )

    def _validate_controlled_patrol_routes(self, routes) -> None:
        starts = []
        sampled_routes = []
        for route in routes:
            if not route.waypoints:
                raise ValueError(f"Controlled patrol route {route.name} is empty")
            self._validate_route_segments(
                route.name, route.start, route.waypoints
            )
            if not self._outside_robot_keepout(route.start):
                raise ValueError(
                    f"Controlled patrol route {route.name} starts inside "
                    "robot keepout"
                )
            route_samples = self._sample_route_points(route.start, route.waypoints)
            self._validate_route_robot_keepout(route.name, route_samples)
            starts.append(route.start)
            sampled_routes.append((route, route_samples))

        self._validate_point_spacing(
            starts,
            self.min_people_distance,
            "controlled patrol starts",
        )
        self._validate_sampled_route_spacing(sampled_routes)
        self._validate_shared_track_timing(routes)

    def _validate_controlled_emergency_routes(self) -> None:
        starts = []
        gatherings = []
        for route in CONTROLLED_EMERGENCY_ROUTES:
            if not route.to_emergency or not route.from_emergency:
                raise ValueError(f"Controlled route {route.name} is empty")
            self._validate_route_segments(
                route.name, route.start, route.to_emergency
            )
            self._validate_route_segments(
                route.name, route.gathering_point, route.from_emergency
            )
            if not self._outside_robot_keepout(route.start):
                raise ValueError(
                    f"Controlled route {route.name} starts inside robot keepout"
                )
            starts.append(route.start)
            gatherings.append(route.gathering_point)

        self._validate_point_spacing(
            starts,
            self.min_people_distance,
            "controlled emergency starts",
        )
        self._validate_point_spacing(
            gatherings,
            self.min_people_distance,
            "controlled emergency gathering points",
        )

    def _validate_route_segments(
        self, route_name: str, start: Point2D, waypoints: tuple[Point2D, ...]
    ) -> None:
        current = start
        for waypoint in waypoints:
            if not self.map.is_valid_world(waypoint):
                raise ValueError(
                    f"Controlled route {route_name} has invalid waypoint "
                    f"{waypoint}"
                )
            if not self.map.line_is_valid(current, waypoint):
                raise ValueError(
                    f"Controlled route {route_name} has blocked segment "
                    f"{current} -> {waypoint}"
                )
            self._validate_dense_route_segment(route_name, current, waypoint)
            current = waypoint

    def _validate_dense_route_segment(
        self, route_name: str, start: Point2D, end: Point2D
    ) -> None:
        distance = math.dist(start, end)
        samples = max(1, int(math.ceil(distance / 0.01)))
        for index in range(samples + 1):
            ratio = index / samples
            point = (
                start[0] + ratio * (end[0] - start[0]),
                start[1] + ratio * (end[1] - start[1]),
            )
            if not self.map.is_valid_world(point):
                raise ValueError(
                    f"Controlled route {route_name} has invalid sampled point "
                    f"{point} on segment {start} -> {end}"
                )

    def _validate_point_spacing(
        self, points: list[Point2D], min_distance: float, label: str
    ) -> None:
        for index, point in enumerate(points):
            for other in points[index + 1:]:
                if math.dist(point, other) < min_distance:
                    raise ValueError(
                        f"{label} are closer than {min_distance:.2f} m: "
                        f"{point} and {other}"
                    )

    def _sample_route_points(
        self, start: Point2D, waypoints: tuple[Point2D, ...]
    ) -> list[Point2D]:
        samples = [start]
        current = start
        for waypoint in waypoints:
            distance = math.dist(current, waypoint)
            steps = max(1, int(math.ceil(distance / 0.20)))
            for step in range(1, steps + 1):
                ratio = step / steps
                samples.append(
                    (
                        current[0] + ratio * (waypoint[0] - current[0]),
                        current[1] + ratio * (waypoint[1] - current[1]),
                    )
                )
            current = waypoint
        return samples

    def _validate_route_robot_keepout(
        self, route_name: str, samples: list[Point2D]
    ) -> None:
        for point in samples:
            if not self._outside_robot_keepout(point):
                raise ValueError(
                    f"Controlled patrol route {route_name} enters robot keepout "
                    f"near {point}"
                )

    def _validate_sampled_route_spacing(
        self, sampled_routes: list[tuple[object, list[Point2D]]]
    ) -> None:
        clearance = self._moving_people_clearance()
        for index, (route, route_points) in enumerate(sampled_routes):
            for other_index, (other_route, other_points) in enumerate(
                sampled_routes[index + 1:]
            ):
                if route.track and route.track == other_route.track:
                    continue
                if self._sampled_routes_distance(route_points, other_points) < clearance:
                    raise ValueError(
                        "controlled patrol routes are closer than "
                        f"{clearance:.2f} m: route {index + 1} and "
                        f"route {index + other_index + 2}"
                    )

    def _sampled_routes_distance(
        self, first: list[Point2D], second: list[Point2D]
    ) -> float:
        return min(math.dist(point, other) for point in first for other in second)

    def _validate_shared_track_timing(self, routes) -> None:
        tracks = {}
        for route in routes:
            if not route.track:
                continue
            tracks.setdefault(route.track, []).append(route)

        clearance = self._moving_people_clearance()
        for track_name, track_routes in tracks.items():
            if len(track_routes) < 2:
                continue
            periods = [
                self._route_path_length(route) / route.speed
                for route in track_routes
            ]
            if max(periods) - min(periods) > 1e-3:
                raise ValueError(
                    f"Shared patrol track {track_name} has mismatched periods"
                )

            sample_time = 0.0
            duration = max(periods)
            while sample_time <= duration:
                positions = [
                    self._route_position_at(route, sample_time)
                    for route in track_routes
                ]
                for index, point in enumerate(positions):
                    for other in positions[index + 1:]:
                        if math.dist(point, other) < clearance:
                            raise ValueError(
                                f"Shared patrol track {track_name} is closer "
                                f"than {clearance:.2f} m at t={sample_time:.1f}"
                            )
                sample_time += 0.1

    def _route_path_length(self, route) -> float:
        points = [route.start] + list(route.waypoints)
        return sum(
            math.dist(start, end)
            for start, end in zip(points, points[1:])
        )

    def _route_position_at(self, route, elapsed: float) -> Point2D:
        points = [route.start] + list(route.waypoints)
        distances = [
            math.dist(start, end)
            for start, end in zip(points, points[1:])
        ]
        total_distance = sum(distances)
        if total_distance <= 0.0:
            return route.start

        travel = (elapsed * route.speed) % total_distance
        accumulated = 0.0
        for start, end, distance in zip(points, points[1:], distances):
            if travel <= accumulated + distance or distance <= 0.0:
                ratio = (travel - accumulated) / distance if distance else 0.0
                return (
                    start[0] + ratio * (end[0] - start[0]),
                    start[1] + ratio * (end[1] - start[1]),
                )
            accumulated += distance
        return points[-1]

    def _spawn_people(self) -> None:
        self.pending_spawns = len(self.people)
        self.next_spawn_index = 0
        self.spawn_timeout_timer = self.create_timer(
            self.spawn_response_timeout,
            self._spawn_timeout_elapsed,
            clock=self.steady_clock,
        )
        self._spawn_next_person()

    def _spawn_next_person(self) -> None:
        if self.next_spawn_index >= len(self.people):
            if self.pending_spawns == 0 and not self.movement_started:
                self._start_movement()
            return

        human = self.people[self.next_spawn_index]
        self.next_spawn_index += 1

        request = SpawnEntity.Request()
        request.name = human.name
        request.xml = PERSON_SDF.format(name=human.name)
        request.initial_pose = Pose(
            position=Point(x=human.x, y=human.y, z=0.0),
            orientation=Quaternion(w=1.0),
        )
        future = self.spawn_client.call_async(request)
        future.add_done_callback(
            lambda result, person=human: self._on_spawn_done(person, result)
        )

    def _on_spawn_done(self, human: RandomHuman, future) -> None:
        try:
            result = future.result()
            human.spawned = bool(result is not None and result.success)
            if human.spawned:
                self.get_logger().info(
                    f"Spawned {human.name} at ({human.x:.2f}, {human.y:.2f})"
                )
            else:
                status = result.status_message if result is not None else "no response"
                self.get_logger().warn(
                    f"Failed to spawn {human.name}: {status}"
                )
        except Exception as error:
            self.get_logger().error(f"Spawn failed for {human.name}: {error}")
        finally:
            self.pending_spawns = max(0, self.pending_spawns - 1)
            if not self.movement_started:
                if self.next_spawn_index < len(self.people):
                    self._spawn_next_person()
                elif self.pending_spawns == 0:
                    self._start_movement()

    def _spawn_timeout_elapsed(self) -> None:
        if self.spawn_timeout_timer is not None:
            self.spawn_timeout_timer.cancel()
        if self.movement_started:
            return

        spawned_count = sum(human.spawned for human in self.people)
        if spawned_count:
            self.get_logger().warn(
                f"Starting movement with {spawned_count}/{len(self.people)} "
                "humans; some Gazebo spawn requests did not answer before "
                f"{self.spawn_response_timeout:.1f} s"
            )
            self._start_movement()
            return

        message = (
            "No controlled human was spawned before "
            f"{self.spawn_response_timeout:.1f} s"
        )
        self.get_logger().error(message)
        raise RuntimeError(message)

    def _start_movement(self) -> None:
        if self.movement_started:
            return
        spawned_count = sum(human.spawned for human in self.people)
        if not spawned_count:
            message = "No controlled human was spawned successfully"
            self.get_logger().error(message)
            raise RuntimeError(message)
        self.movement_started = True
        if self.spawn_timeout_timer is not None:
            self.spawn_timeout_timer.cancel()
        now = self._clock_seconds()
        self.simulation_start = now
        self.last_update = now
        self.next_gazebo_state_update = now
        self.movement_timer = self.create_timer(
            1.0 / self.update_rate,
            self._update,
            clock=self.steady_clock,
        )
        self.get_logger().info(
            f"Movement started at {self.update_rate:.1f} Hz "
            f"for {spawned_count} humans"
        )

    def _clock_seconds(self) -> float:
        return self.steady_clock.now().nanoseconds / 1_000_000_000.0

    def _update(self) -> None:
        now = self._clock_seconds()
        elapsed = max(0.0, now - self.simulation_start)
        dt = max(0.0, now - self.last_update)
        dt = min(dt, 2.0 / self.update_rate)
        self.last_update = now
        send_gazebo_states = now >= self.next_gazebo_state_update
        if send_gazebo_states:
            self.next_gazebo_state_update = now + 1.0 / self.gazebo_state_update_rate

        robot_position = self._lookup_robot_position()
        if robot_position is not None:
            self.current_robot_position = robot_position

        if (
            self.scenario == "emergency"
            and elapsed >= self.next_emergency_time
            and not self._emergency_in_progress()
        ):
            self._trigger_emergency(elapsed)

        active = [human for human in self.people if human.spawned]
        accepted_positions: dict[str, Point2D] = {}
        for human in active:
            self._prepare_human_state(human, elapsed)
            proposed = self._propose_position(human, dt)
            selected = self._select_motion(
                human, proposed, active, accepted_positions
            )
            if selected != human.position:
                human.yaw = math.atan2(
                    selected[1] - human.y,
                    selected[0] - human.x,
                )
                human.x, human.y = selected
            accepted_positions[human.name] = human.position
            self._complete_reached_waypoints(human, elapsed)
            if send_gazebo_states:
                self._send_state(human, now)

        self._finish_emergency_cycle_if_ready(elapsed)
        self._publish_people(active)
        self._publish_people_markers(active)

    def _prepare_human_state(self, human: RandomHuman, elapsed: float) -> None:
        if self.scenario == "emergency":
            self._prepare_controlled_emergency_state(human, elapsed)
            return

        if human.waypoints:
            return
        route = self._controlled_patrol_route(human)
        if route is None:
            return
        human.state = "normal"
        human.speed = route.speed
        human.waypoints = list(route.waypoints)

    def _controlled_patrol_route(self, human: RandomHuman):
        index = human.controlled_route_index
        if index is None:
            return None
        routes = CONTROLLED_PATROL_SCENARIOS.get(self.scenario)
        if routes is None or not 0 <= index < len(routes):
            return None
        return routes[index]

    def _prepare_controlled_emergency_state(
        self, human: RandomHuman, elapsed: float
    ) -> None:
        if human.waypoints:
            return
        route = self._controlled_route(human)
        if route is None:
            return

        if human.state == "moving_to_emergency":
            human.state = "waiting_emergency"
            self.get_logger().info(
                f"{human.name} reached controlled emergency gathering point"
            )
            return

        if human.state == "waiting_emergency":
            if (
                human.emergency_release_time is not None
                and elapsed >= human.emergency_release_time
            ):
                human.state = "dispersing"
                human.speed = self.controlled_emergency_speed
                human.waypoints = list(route.from_emergency)
            return

        if human.state == "dispersing":
            human.emergency_member = False
            human.emergency_release_time = None
            human.state = "normal"
            human.speed = self.controlled_emergency_speed

    def _controlled_route(self, human: RandomHuman):
        index = human.controlled_route_index
        if index is None:
            return None
        if not 0 <= index < len(CONTROLLED_EMERGENCY_ROUTES):
            return None
        return CONTROLLED_EMERGENCY_ROUTES[index]

    def _propose_position(self, human: RandomHuman, dt: float) -> Point2D:
        if not human.waypoints or dt <= 0.0:
            return human.position
        target = human.waypoints[0]
        distance = math.dist(human.position, target)
        if distance <= self.arrival_tolerance:
            return target
        step = min(distance, human.speed * dt)
        ratio = step / distance
        return (
            human.x + ratio * (target[0] - human.x),
            human.y + ratio * (target[1] - human.y),
        )

    def _position_clear(
        self,
        human: RandomHuman,
        point: Point2D,
        active: list[RandomHuman],
        accepted: dict[str, Point2D],
    ) -> bool:
        if not self.map.is_valid_world(point):
            self.get_logger().error(
                f"Rejected invalid map position for {human.name}: {point}",
                throttle_duration_sec=5.0,
            )
            return False
        for robot_position in self._robot_exclusion_points():
            current_distance = math.dist(human.position, robot_position)
            proposed_distance = math.dist(point, robot_position)
            if proposed_distance < self.min_robot_distance:
                if (
                    current_distance < self.min_robot_distance
                    and proposed_distance > current_distance + 1e-3
                ):
                    continue
                return False
        moving_distance = self._moving_people_clearance()
        for other in active:
            if other is human:
                continue
            other_position = accepted.get(other.name, other.position)
            current_distance = math.dist(human.position, other_position)
            proposed_distance = math.dist(point, other_position)
            hard_distance = max(0.05, 2.0 * self.human_radius)
            if proposed_distance < hard_distance:
                if (
                    current_distance < hard_distance
                    and proposed_distance > current_distance + 1e-3
                ):
                    continue
                return False
            if proposed_distance < moving_distance:
                if (
                    current_distance < moving_distance
                    and proposed_distance > current_distance + 1e-3
                ):
                    continue
                return False
        return True

    def _moving_people_clearance(self) -> float:
        return max(2.0 * self.human_radius, self.moving_people_distance)

    def _holding_emergency_position(self, human: RandomHuman) -> bool:
        return human.state == "waiting_emergency" and not human.waypoints

    def _select_motion(
        self,
        human: RandomHuman,
        proposed: Point2D,
        active: list[RandomHuman],
        accepted: dict[str, Point2D],
    ) -> Point2D:
        if (
            self._holding_emergency_position(human)
            and self._outside_robot_keepout(human.position)
        ):
            return human.position

        if self._position_clear(human, proposed, active, accepted):
            return proposed

        return human.position

    def _complete_reached_waypoints(
        self, human: RandomHuman, elapsed: float
    ) -> None:
        while human.waypoints:
            target = human.waypoints[0]
            if math.dist(human.position, target) > self.arrival_tolerance:
                break
            human.x, human.y = target
            human.waypoints.pop(0)
        if not human.waypoints:
            self._prepare_human_state(human, elapsed)

    def _trigger_emergency(self, elapsed: float) -> None:
        self.emergency_cycle += 1
        # The next cycle is scheduled only after every controlled human has
        # returned to its fixed start position.
        self.next_emergency_time = float("inf")

        assigned = 0
        release_time = elapsed + self.emergency_duration
        for human in self.people:
            if not human.spawned:
                continue
            route = self._controlled_route(human)
            if route is None:
                self.get_logger().warn(
                    f"No controlled emergency route for {human.name}"
                )
                continue
            human.emergency_member = True
            human.emergency_release_time = release_time + route.egress_delay
            human.state = "moving_to_emergency"
            human.speed = self.controlled_emergency_speed
            human.waypoints = list(route.to_emergency)
            assigned += 1

        self.emergency_cycle_active = assigned > 0

        self.get_logger().info(
            f"Controlled emergency cycle {self.emergency_cycle} started: "
            f"{assigned}/{len(CONTROLLED_EMERGENCY_ROUTES)} humans moving; "
            f"return begins after {self.emergency_duration:.1f} s"
        )

    def _finish_emergency_cycle_if_ready(self, elapsed: float) -> None:
        """Schedule a new emergency after gathering, waiting and dispersal."""
        if not self.emergency_cycle_active:
            return
        unfinished_states = {
            "moving_to_emergency",
            "waiting_emergency",
            "dispersing",
        }
        if any(
            human.spawned
            and (
                human.emergency_member
                or human.state in unfinished_states
            )
            for human in self.people
        ):
            return

        self.emergency_cycle_active = False
        if self.emergency_loop:
            self.next_emergency_time = elapsed + self.emergency_repeat_interval
            self.get_logger().info(
                f"Emergency cycle {self.emergency_cycle} completed; "
                f"next cycle in {self.emergency_repeat_interval:.1f} s"
            )
        else:
            self.next_emergency_time = float("inf")
            self.get_logger().info(
                f"Emergency cycle {self.emergency_cycle} completed"
            )

    def _send_state(self, human: RandomHuman, now: float) -> None:
        if human.state_request_pending:
            waiting = now - human.state_request_started
            if waiting < self.gazebo_state_timeout:
                return
            self.get_logger().warn(
                f"SetEntityState response timed out for {human.name}; "
                "sending latest pose again",
                throttle_duration_sec=5.0,
            )
            human.state_request_pending = False

        state = EntityState()
        state.name = human.name
        state.reference_frame = "world"
        state.pose.position.x = float(human.x)
        state.pose.position.y = float(human.y)
        state.pose.position.z = 0.0
        state.pose.orientation.z = math.sin(human.yaw / 2.0)
        state.pose.orientation.w = math.cos(human.yaw / 2.0)

        request = SetEntityState.Request()
        request.state = state
        human.state_request_id += 1
        request_id = human.state_request_id
        human.state_request_pending = True
        human.state_request_started = now
        future = self.set_state_client.call_async(request)
        future.add_done_callback(
            lambda result, person=human, sent_id=request_id: self._on_state_done(
                person, sent_id, result
            )
        )

    def _on_state_done(self, human: RandomHuman, request_id: int, future) -> None:
        if request_id == human.state_request_id:
            human.state_request_pending = False
            human.state_request_started = 0.0
        try:
            result = future.result()
            if result is not None and not result.success:
                self.get_logger().warn(
                    f"SetEntityState failed for {human.name}",
                    throttle_duration_sec=5.0,
                )
        except Exception as error:
            self.get_logger().error(
                f"SetEntityState error for {human.name}: {error}",
                throttle_duration_sec=5.0,
            )

    def _publish_people(self, people: list[RandomHuman]) -> None:
        message = PoseArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = self.map_frame
        for human in people:
            pose = Pose()
            pose.position.x = float(human.x)
            pose.position.y = float(human.y)
            pose.position.z = 0.85
            pose.orientation.w = 1.0
            message.poses.append(pose)
        self.people_pub.publish(message)

    def _publish_people_markers(self, people: list[RandomHuman]) -> None:
        """Publish one flat circle per human for the RViz top-down view."""
        markers = MarkerArray()
        clear = Marker()
        clear.action = Marker.DELETEALL
        markers.markers.append(clear)

        stamp = self.get_clock().now().to_msg()
        colours = {
            "normal": (0.10, 0.85, 0.25),
            "moving_to_emergency": (0.95, 0.15, 0.10),
            "waiting_emergency": (0.85, 0.10, 0.75),
            "dispersing": (1.00, 0.60, 0.05),
        }
        diameter = max(0.10, 2.0 * self.human_radius)
        for marker_id, human in enumerate(people):
            marker = Marker()
            marker.header.stamp = stamp
            marker.header.frame_id = self.map_frame
            marker.ns = "controlled_humans"
            marker.id = marker_id
            marker.type = Marker.CYLINDER
            marker.action = Marker.ADD
            marker.pose.position.x = float(human.x)
            marker.pose.position.y = float(human.y)
            marker.pose.position.z = 0.04
            marker.pose.orientation.w = 1.0
            marker.scale.x = diameter
            marker.scale.y = diameter
            marker.scale.z = 0.08
            red, green, blue = colours.get(
                human.state, colours["normal"]
            )
            marker.color.r = red
            marker.color.g = green
            marker.color.b = blue
            marker.color.a = 0.95
            markers.markers.append(marker)
        self.marker_pub.publish(markers)

    def _clear_people_markers(self) -> None:
        markers = MarkerArray()
        clear = Marker()
        clear.action = Marker.DELETEALL
        markers.markers.append(clear)
        self.marker_pub.publish(markers)

    def cleanup(self) -> None:
        """Stop movement and delete every model successfully spawned by this node."""
        if self.cleaned_up:
            return
        self.cleaned_up = True
        if self.startup_timer is not None:
            self.startup_timer.cancel()
        if self.movement_timer is not None:
            self.movement_timer.cancel()
        if self.spawn_timeout_timer is not None:
            self.spawn_timeout_timer.cancel()
        self._clear_people_markers()

        spawned = [human for human in self.people if human.spawned]
        if not spawned:
            return
        if not self.delete_client.service_is_ready():
            self.get_logger().warn(
                "Cannot delete controlled humans: /delete_entity is unavailable"
            )
            return

        self.get_logger().info(f"Deleting {len(spawned)} controlled humans...")
        for human in spawned:
            request = DeleteEntity.Request()
            request.name = human.name
            future = self.delete_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
            try:
                result = future.result()
                if result is None or not result.success:
                    self.get_logger().warn(f"Failed to delete {human.name}")
            except Exception as error:
                self.get_logger().warn(
                    f"DeleteEntity error for {human.name}: {error}"
                )


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = RandomObstacleSpawner()
    except Exception as error:
        if node is not None:
            node.get_logger().error(f"Initialization failed: {error}")
            node.destroy_node()
        else:
            print(f"random_obstacle_spawner initialization failed: {error}")
        rclpy.shutdown()
        return 1

    def request_shutdown(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    exit_code = 0
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Random obstacle shutdown requested")
    except Exception as error:
        node.get_logger().error(f"Random obstacle spawner stopped: {error}")
        exit_code = 1
    finally:
        node.cleanup()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
