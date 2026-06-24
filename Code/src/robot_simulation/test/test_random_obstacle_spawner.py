"""State-machine tests for the controlled obstacle spawner."""

import math
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from controlled_emergency_scenario import (  # noqa: E402
    CONTROLLED_EMERGENCY_ROUTES,
)
from controlled_patrol_scenarios import (  # noqa: E402
    CONTROLLED_PATROL_SCENARIOS,
)
from random_obstacle_core import OccupancyMap  # noqa: E402
from random_obstacle_spawner import (  # noqa: E402
    RandomHuman,
    RandomObstacleSpawner,
)


class RecordingLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)

    def warn(self, message):
        self.messages.append(message)

    def error(self, message):
        self.messages.append(message)


class CancelTimer:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class OpenMap:
    def is_valid_world(self, _point):
        return True

    def line_is_valid(self, _start, _end):
        return True


class MotionSpawner:
    def __init__(self):
        self.map = OpenMap()
        self.min_people_distance = 0.8
        self.moving_people_distance = 0.65
        self.human_radius = 0.28
        self.min_robot_distance = 2.0
        self.current_robot_position = (100.0, 100.0)
        self.fallback_robot_position = (100.0, 100.0)
        self.logger = RecordingLogger()

    def get_logger(self):
        return self.logger

    def _robot_exclusion_points(self):
        return RandomObstacleSpawner._robot_exclusion_points(self)

    def _outside_robot_keepout(self, point):
        return RandomObstacleSpawner._outside_robot_keepout(self, point)

    def _moving_people_clearance(self):
        return RandomObstacleSpawner._moving_people_clearance(self)

    def _position_clear(self, human, point, active, accepted):
        return RandomObstacleSpawner._position_clear(
            self, human, point, active, accepted
        )

    def _holding_emergency_position(self, human):
        return RandomObstacleSpawner._holding_emergency_position(self, human)


class FakeCycleSpawner:
    def __init__(self, human, loop=True):
        self.people = [human]
        self.emergency_cycle_active = True
        self.emergency_loop = loop
        self.emergency_repeat_interval = 25.0
        self.emergency_cycle = 2
        self.next_emergency_time = float("inf")
        self.logger = RecordingLogger()

    def get_logger(self):
        return self.logger


class ControlledEmergencyStateSpawner:
    def __init__(self):
        self.scenario = "emergency"
        self.controlled_emergency_speed = 1.0
        self.logger = RecordingLogger()

    def get_logger(self):
        return self.logger

    def _prepare_controlled_emergency_state(self, human, elapsed):
        return RandomObstacleSpawner._prepare_controlled_emergency_state(
            self, human, elapsed
        )

    def _controlled_route(self, _human):
        return CONTROLLED_EMERGENCY_ROUTES[0]


class ControlledPatrolStateSpawner:
    def __init__(self, scenario):
        self.scenario = scenario

    def _controlled_patrol_route(self, human):
        return CONTROLLED_PATROL_SCENARIOS[self.scenario][
            human.controlled_route_index
        ]


def hospital_map():
    map_yaml = Path(__file__).resolve().parents[1] / "maps" / "hospital_map.yaml"
    return OccupancyMap.load(str(map_yaml), clearance=0.78)


def path_length(start, waypoints):
    total = 0.0
    current = start
    for waypoint in waypoints:
        total += math.dist(current, waypoint)
        current = waypoint
    return total


def position_on_path(start, waypoints, elapsed, speed=1.0):
    if elapsed <= 0.0:
        return start
    remaining = elapsed * speed
    current = start
    for waypoint in waypoints:
        distance = math.dist(current, waypoint)
        if remaining <= distance:
            ratio = remaining / distance if distance else 1.0
            return (
                current[0] + ratio * (waypoint[0] - current[0]),
                current[1] + ratio * (waypoint[1] - current[1]),
            )
        remaining -= distance
        current = waypoint
    return waypoints[-1]


def sample_route_points(start, waypoints):
    samples = [start]
    current = start
    for waypoint in waypoints:
        distance = math.dist(current, waypoint)
        steps = max(1, int(math.ceil(distance / 0.1)))
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


def sampled_routes_min_distance(routes):
    sampled = [
        sample_route_points(route.start, route.waypoints)
        for route in routes
    ]
    minimum = float("inf")
    for index, (route, points) in enumerate(zip(routes, sampled)):
        for other_route, other in zip(routes[index + 1:], sampled[index + 1:]):
            if route.track and route.track == other_route.track:
                continue
            for point in points:
                for other_point in other:
                    minimum = min(minimum, math.dist(point, other_point))
    return minimum


def route_path_length(route):
    return path_length(route.start, route.waypoints)


def route_position_at(route, elapsed):
    distance = (elapsed * route.speed) % route_path_length(route)
    current = route.start
    for waypoint in route.waypoints:
        segment = math.dist(current, waypoint)
        if distance <= segment:
            ratio = distance / segment if segment else 0.0
            return (
                current[0] + ratio * (waypoint[0] - current[0]),
                current[1] + ratio * (waypoint[1] - current[1]),
            )
        distance -= segment
        current = waypoint
    return route.waypoints[-1]


def shared_track_min_distance(routes):
    tracks = {}
    for route in routes:
        if route.track:
            tracks.setdefault(route.track, []).append(route)

    minimum = float("inf")
    for track_routes in tracks.values():
        if len(track_routes) < 2:
            continue
        duration = max(route_path_length(route) / route.speed for route in track_routes)
        sample = 0.0
        while sample <= duration:
            positions = [
                route_position_at(route, sample)
                for route in track_routes
            ]
            for index, position in enumerate(positions):
                for other in positions[index + 1:]:
                    minimum = min(minimum, math.dist(position, other))
            sample += 0.1
    return minimum


def minimum_emergency_distance(phase):
    starts = []
    paths = []
    delays = []
    for route in CONTROLLED_EMERGENCY_ROUTES:
        if phase == "ingress":
            starts.append(route.start)
            paths.append(route.to_emergency)
            delays.append(0.0)
        else:
            starts.append(route.gathering_point)
            paths.append(route.from_emergency)
            delays.append(route.egress_delay)

    duration = max(
        delay + path_length(start, path)
        for start, path, delay in zip(starts, paths, delays)
    )
    minimum = float("inf")
    sample = 0.0
    while sample <= duration + 1.0:
        positions = [
            position_on_path(start, path, sample - delay)
            for start, path, delay in zip(starts, paths, delays)
        ]
        for index, position in enumerate(positions):
            for other in positions[index + 1:]:
                minimum = min(minimum, math.dist(position, other))
        sample += 0.1
    return minimum


def test_cycle_waits_until_dispersal_is_complete():
    human = RandomHuman("human", 0.0, 0.0, 0.5)
    human.spawned = True
    human.state = "dispersing"
    human.emergency_member = True
    spawner = FakeCycleSpawner(human)

    RandomObstacleSpawner._finish_emergency_cycle_if_ready(spawner, 100.0)

    assert spawner.emergency_cycle_active
    assert spawner.next_emergency_time == float("inf")


def test_cycle_schedules_next_emergency_after_dispersal():
    human = RandomHuman("human", 0.0, 0.0, 0.5)
    human.spawned = True
    human.state = "normal"
    spawner = FakeCycleSpawner(human)

    RandomObstacleSpawner._finish_emergency_cycle_if_ready(spawner, 100.0)

    assert not spawner.emergency_cycle_active
    assert spawner.next_emergency_time == 125.0
    assert "next cycle in 25.0 s" in spawner.logger.messages[-1]


def test_disabled_loop_does_not_schedule_another_emergency():
    human = RandomHuman("human", 0.0, 0.0, 0.5)
    human.spawned = True
    human.state = "normal"
    spawner = FakeCycleSpawner(human, loop=False)

    RandomObstacleSpawner._finish_emergency_cycle_if_ready(spawner, 100.0)

    assert not spawner.emergency_cycle_active
    assert spawner.next_emergency_time == float("inf")


def test_spawn_timeout_starts_with_successful_partial_batch():
    humans = [
        RandomHuman("spawned", 0.0, 0.0, 0.5),
        RandomHuman("pending", 1.0, 0.0, 0.5),
    ]
    humans[0].spawned = True

    class SpawnTimeoutSpawner:
        def __init__(self):
            self.people = humans
            self.spawn_timeout_timer = CancelTimer()
            self.movement_started = False
            self.spawn_response_timeout = 10.0
            self.started = False
            self.logger = RecordingLogger()

        def get_logger(self):
            return self.logger

        def _start_movement(self):
            self.started = True
            self.movement_started = True

    spawner = SpawnTimeoutSpawner()
    RandomObstacleSpawner._spawn_timeout_elapsed(spawner)

    assert spawner.spawn_timeout_timer.cancelled
    assert spawner.started
    assert "Starting movement with 1/2 humans" in spawner.logger.messages[-1]


def test_spawn_timeout_without_successful_spawns_fails():
    class SpawnTimeoutSpawner:
        def __init__(self):
            self.people = [RandomHuman("pending", 0.0, 0.0, 0.5)]
            self.spawn_timeout_timer = CancelTimer()
            self.movement_started = False
            self.spawn_response_timeout = 10.0
            self.logger = RecordingLogger()

        def get_logger(self):
            return self.logger

    spawner = SpawnTimeoutSpawner()

    try:
        RandomObstacleSpawner._spawn_timeout_elapsed(spawner)
    except RuntimeError as error:
        assert "No controlled human was spawned before 10.0 s" in str(error)
    else:
        raise AssertionError("Expected RuntimeError when no human spawned")

    assert spawner.spawn_timeout_timer.cancelled


def test_close_humans_can_move_apart():
    spawner = MotionSpawner()
    human = RandomHuman("a", 0.0, 0.0, 0.5)
    other = RandomHuman("b", 0.7, 0.0, 0.5)
    active = [human, other]

    assert RandomObstacleSpawner._position_clear(
        spawner, human, (-0.05, 0.0), active, {}
    )


def test_close_humans_cannot_move_closer():
    spawner = MotionSpawner()
    human = RandomHuman("a", 0.0, 0.0, 0.5)
    other = RandomHuman("b", 0.7, 0.0, 0.5)
    active = [human, other]

    assert not RandomObstacleSpawner._position_clear(
        spawner, human, (0.1, 0.0), active, {}
    )


def test_walking_humans_can_enter_soft_spacing():
    spawner = MotionSpawner()
    human = RandomHuman("a", 0.0, 0.0, 0.5)
    other = RandomHuman("b", 0.8, 0.0, 0.5)
    active = [human, other]

    assert RandomObstacleSpawner._position_clear(
        spawner, human, (0.1, 0.0), active, {}
    )


def test_motion_rejects_robot_keepout():
    spawner = MotionSpawner()
    spawner.current_robot_position = (0.0, 0.0)
    spawner.fallback_robot_position = (10.0, 10.0)
    human = RandomHuman("a", 3.0, 0.0, 0.5)

    assert not RandomObstacleSpawner._position_clear(
        spawner, human, (1.0, 0.0), [human], {}
    )


def test_human_inside_robot_keepout_can_move_away():
    spawner = MotionSpawner()
    spawner.current_robot_position = (0.0, 0.0)
    spawner.fallback_robot_position = (10.0, 10.0)
    human = RandomHuman("a", 1.0, 0.0, 0.5)

    assert RandomObstacleSpawner._position_clear(
        spawner, human, (1.2, 0.0), [human], {}
    )


def test_waiting_emergency_human_holds_position_when_grouped():
    spawner = MotionSpawner()
    human = RandomHuman("a", 0.0, 0.0, 0.5)
    human.state = "waiting_emergency"
    other = RandomHuman("b", 0.6, 0.0, 0.5)
    active = [human, other]

    selected = RandomObstacleSpawner._select_motion(
        spawner, human, human.position, active, {}
    )

    assert selected == human.position


def test_controlled_patrol_counts_are_fixed():
    assert len(CONTROLLED_PATROL_SCENARIOS["normal"]) == 10
    assert len(CONTROLLED_PATROL_SCENARIOS["crowd"]) == 18


def test_controlled_patrol_routes_are_valid_on_hospital_map():
    grid = hospital_map()
    for routes in CONTROLLED_PATROL_SCENARIOS.values():
        for route in routes:
            current = route.start
            assert grid.is_valid_world(current)
            for waypoint in route.waypoints:
                assert grid.line_is_valid(current, waypoint)
                current = waypoint


def test_controlled_patrol_routes_are_spaced():
    for routes in CONTROLLED_PATROL_SCENARIOS.values():
        assert sampled_routes_min_distance(routes) >= 0.8
        assert shared_track_min_distance(routes) >= 0.8


def test_controlled_patrol_state_restarts_loop():
    route = CONTROLLED_PATROL_SCENARIOS["normal"][0]
    human = RandomHuman(
        route.name,
        route.start[0],
        route.start[1],
        route.speed,
        controlled_route_index=0,
    )
    spawner = ControlledPatrolStateSpawner("normal")

    RandomObstacleSpawner._prepare_human_state(spawner, human, 10.0)

    assert human.waypoints == list(route.waypoints)


def test_controlled_emergency_has_eight_spaced_gathering_points():
    assert len(CONTROLLED_EMERGENCY_ROUTES) == 8

    targets = [route.gathering_point for route in CONTROLLED_EMERGENCY_ROUTES]
    for index, target in enumerate(targets):
        for other in targets[index + 1:]:
            assert math.dist(target, other) >= 0.8


def test_controlled_emergency_routes_are_valid_on_hospital_map():
    grid = hospital_map()

    for route in CONTROLLED_EMERGENCY_ROUTES:
        current = route.start
        for waypoint in route.to_emergency:
            assert grid.line_is_valid(current, waypoint)
            current = waypoint

        current = route.gathering_point
        for waypoint in route.from_emergency:
            assert grid.line_is_valid(current, waypoint)
            current = waypoint


def test_controlled_emergency_routes_keep_distance_over_time():
    assert minimum_emergency_distance("ingress") >= 0.8
    assert minimum_emergency_distance("egress") >= 0.8


def test_controlled_emergency_trigger_assigns_fixed_routes():
    humans = [
        RandomHuman(route.name, route.start[0], route.start[1], 1.0)
        for route in CONTROLLED_EMERGENCY_ROUTES
    ]
    for index, human in enumerate(humans):
        human.spawned = True
        human.controlled_route_index = index

    class TriggerSpawner:
        def __init__(self):
            self.people = humans
            self.emergency_cycle = 0
            self.emergency_cycle_active = False
            self.next_emergency_time = 30.0
            self.emergency_duration = 80.0
            self.controlled_emergency_speed = 1.0
            self.logger = RecordingLogger()

        def get_logger(self):
            return self.logger

        def _controlled_route(self, human):
            return RandomObstacleSpawner._controlled_route(self, human)

    spawner = TriggerSpawner()
    RandomObstacleSpawner._trigger_emergency(spawner, 30.0)

    assert spawner.emergency_cycle == 1
    assert spawner.emergency_cycle_active
    assert spawner.next_emergency_time == float("inf")
    for human, route in zip(humans, CONTROLLED_EMERGENCY_ROUTES):
        assert human.state == "moving_to_emergency"
        assert human.waypoints == list(route.to_emergency)
        assert human.emergency_release_time == 110.0 + route.egress_delay


def test_controlled_emergency_waiting_human_uses_fixed_return_route():
    route = CONTROLLED_EMERGENCY_ROUTES[0]
    human = RandomHuman(
        route.name,
        route.gathering_point[0],
        route.gathering_point[1],
        1.0,
    )
    human.state = "waiting_emergency"
    human.emergency_member = True
    human.emergency_release_time = 110.0
    human.controlled_route_index = 0
    spawner = ControlledEmergencyStateSpawner()

    RandomObstacleSpawner._prepare_human_state(spawner, human, 110.0)

    assert human.state == "dispersing"
    assert human.waypoints == list(route.from_emergency)
