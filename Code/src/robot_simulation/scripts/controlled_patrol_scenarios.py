"""Deterministic patrol routes for controlled hospital obstacle scenarios."""

from __future__ import annotations

import math
from dataclasses import dataclass

from random_obstacle_core import Point2D


@dataclass(frozen=True)
class ControlledPatrolRoute:
    """One looped patrol used by a controlled walking person."""

    name: str
    start: Point2D
    waypoints: tuple[Point2D, ...]
    speed: float = 0.6
    track: str = ""


MAIN_CENTRAL_LOOP: tuple[Point2D, ...] = (
    (-4.8, -24.0),
    (4.8, -24.0),
    (4.8, -14.0),
    (-4.8, -14.0),
)

MAIN_UPPER_LOOP: tuple[Point2D, ...] = (
    (-4.8, 10.0),
    (4.8, 10.0),
    (4.8, 14.0),
    (-4.8, 14.0),
)

MAIN_LOWER_TOUR: tuple[Point2D, ...] = (
    (-4.8, -25.5),
    (-4.8, -34.0),
    (10.8, -34.0),
    (-10.8, -34.0),
    (-4.8, -34.0),
    (-4.8, -25.5),
)

BOTTOM_INNER_TOUR: tuple[Point2D, ...] = (
    (-2.075, -30.525),
    (-1.125, -28.525),
    (-0.875, -28.275),
    (-0.175, -28.175),
    (-0.125, -28.175),
    (5.925, -28.125),
    (6.375, -28.175),
    (6.725, -28.325),
    (7.275, -29.025),
    (7.275, -30.525),
    (7.275, -28.975),
    (7.325, -28.575),
    (7.975, -27.025),
    (-2.075, -27.025),
    (-2.075, -30.525),
)

RIGHT_LOWER_WING_TOUR: tuple[Point2D, ...] = (
    (7.925, -22.525),
    (9.225, -22.525),
    (9.025, -19.425),
    (9.025, -13.325),
    (9.375, -12.525),
    (10.925, -12.425),
    (8.875, -12.425),
    (8.875, -15.475),
    (7.925, -22.525),
)

LEFT_LOWER_WING_TOUR: tuple[Point2D, ...] = (
    (-9.325, -22.475),
    (-8.075, -22.475),
    (-8.975, -15.175),
    (-8.975, -14.225),
    (-9.075, -14.975),
    (-9.325, -15.425),
    (-9.375, -15.425),
    (-10.825, -15.425),
    (-9.375, -15.825),
    (-9.325, -15.875),
    (-9.325, -22.475),
)

RIGHT_MID_WING_TOUR: tuple[Point2D, ...] = (
    (7.975, -8.525),
    (9.925, -8.825),
    (10.925, -8.825),
    (9.775, -8.825),
    (9.525, -8.775),
    (8.625, -5.675),
    (8.575, -4.825),
    (8.575, -3.175),
    (8.725, -2.425),
    (8.925, -2.225),
    (7.975, -2.075),
    (7.975, -8.525),
)

LEFT_MID_WING_TOUR: tuple[Point2D, ...] = (
    (-11.025, -8.825),
    (-9.225, -8.825),
    (-8.025, -8.475),
    (-8.725, -1.525),
    (-8.925, -1.325),
    (-8.925, -0.175),
    (-8.925, -1.375),
    (-8.725, -1.575),
    (-8.625, -7.075),
    (-8.625, -8.175),
    (-8.775, -8.575),
    (-9.125, -8.825),
    (-11.025, -8.825),
)

LOWER_LEFT_WING_TOUR: tuple[Point2D, ...] = (
    (-9.125, -31.075),
    (-8.825, -31.075),
    (-8.125, -30.475),
    (-8.125, -25.675),
    (-10.475, -25.675),
    (-8.125, -25.675),
    (-8.125, -27.525),
    (-8.525, -27.525),
    (-8.525, -29.825),
    (-8.825, -31.075),
    (-9.125, -31.075),
)

RIGHT_TOP_WING_TOUR: tuple[Point2D, ...] = (
    (7.525, 13.525),
    (9.325, 13.375),
    (10.975, 13.375),
    (9.025, 13.375),
    (8.925, 14.325),
    (8.925, 15.475),
    (7.525, 15.475),
    (7.525, 13.525),
)

LEFT_TOP_WING_TOUR: tuple[Point2D, ...] = (
    (-10.975, 13.175),
    (-8.825, 13.175),
    (-7.525, 13.525),
    (-7.525, 15.475),
    (-8.825, 15.475),
    (-8.775, 15.125),
    (-8.775, 13.625),
    (-8.825, 13.175),
    (-10.975, 13.175),
)

TOP_LEFT_WING_TOUR: tuple[Point2D, ...] = (
    (-7.525, 17.925),
    (-5.075, 17.925),
    (-4.475, 16.525),
    (-4.475, 19.525),
    (-5.175, 18.075),
    (-7.525, 17.925),
)

TOP_RIGHT_WING_TOUR: tuple[Point2D, ...] = (
    (4.525, 16.525),
    (5.075, 16.525),
    (5.125, 19.875),
    (5.325, 19.975),
    (5.425, 19.975),
    (5.175, 19.925),
    (4.525, 19.475),
    (4.525, 16.525),
)


def _route_from_points(
    name: str,
    points: tuple[Point2D, ...],
    *,
    track: str,
    speed: float = 0.6,
) -> ControlledPatrolRoute:
    return ControlledPatrolRoute(
        name=name,
        start=points[0],
        waypoints=points[1:],
        speed=speed,
        track=track,
    )


def _shifted_loop_route(
    name: str,
    loop: tuple[Point2D, ...],
    phase: float,
    *,
    track: str,
    speed: float = 0.6,
) -> ControlledPatrolRoute:
    closed = loop + (loop[0],)
    segment_lengths = [
        math.dist(start, end)
        for start, end in zip(closed, closed[1:])
    ]
    total_length = sum(segment_lengths)
    offset = (phase % 1.0) * total_length

    accumulated = 0.0
    segment_index = 0
    local_offset = 0.0
    for index, segment_length in enumerate(segment_lengths):
        if offset <= accumulated + segment_length or index == len(segment_lengths) - 1:
            segment_index = index
            local_offset = offset - accumulated
            break
        accumulated += segment_length

    segment_start = closed[segment_index]
    segment_end = closed[segment_index + 1]
    segment_length = segment_lengths[segment_index]
    ratio = local_offset / segment_length if segment_length else 0.0
    start = (
        segment_start[0] + ratio * (segment_end[0] - segment_start[0]),
        segment_start[1] + ratio * (segment_end[1] - segment_start[1]),
    )

    waypoints: list[Point2D] = []
    current = start
    for step in range(1, len(loop) + 1):
        waypoint = loop[(segment_index + step) % len(loop)]
        if math.dist(current, waypoint) > 1e-6:
            waypoints.append(waypoint)
            current = waypoint
    if math.dist(current, start) > 1e-6:
        waypoints.append(start)

    return ControlledPatrolRoute(
        name=name,
        start=start,
        waypoints=tuple(waypoints),
        speed=speed,
        track=track,
    )


NORMAL_PATROL_ROUTES: tuple[ControlledPatrolRoute, ...] = (
    _shifted_loop_route(
        "normal_human_1", MAIN_CENTRAL_LOOP, 0.00, track="main_central"
    ),
    _shifted_loop_route(
        "normal_human_2", MAIN_CENTRAL_LOOP, 0.50, track="main_central"
    ),
    _shifted_loop_route(
        "normal_human_3", MAIN_UPPER_LOOP, 0.00, track="main_upper"
    ),
    _shifted_loop_route(
        "normal_human_4", MAIN_UPPER_LOOP, 0.50, track="main_upper"
    ),
    _route_from_points(
        "normal_human_5", MAIN_LOWER_TOUR, track="main_lower"
    ),
    _route_from_points(
        "normal_human_6", BOTTOM_INNER_TOUR, track="bottom_inner"
    ),
    _route_from_points(
        "normal_human_7", RIGHT_LOWER_WING_TOUR, track="right_lower_wing"
    ),
    _route_from_points(
        "normal_human_8", LEFT_LOWER_WING_TOUR, track="left_lower_wing"
    ),
    _route_from_points(
        "normal_human_9", RIGHT_MID_WING_TOUR, track="right_mid_wing"
    ),
    _route_from_points(
        "normal_human_10", LEFT_MID_WING_TOUR, track="left_mid_wing"
    ),
)


CROWD_EXTRA_PATROL_ROUTES: tuple[ControlledPatrolRoute, ...] = (
    _route_from_points(
        "crowd_human_11", LOWER_LEFT_WING_TOUR, track="lower_left_wing"
    ),
    _route_from_points(
        "crowd_human_12", RIGHT_TOP_WING_TOUR, track="right_top_wing"
    ),
    _route_from_points(
        "crowd_human_13", LEFT_TOP_WING_TOUR, track="left_top_wing"
    ),
    _route_from_points(
        "crowd_human_14", TOP_LEFT_WING_TOUR, track="top_left_wing"
    ),
    _route_from_points(
        "crowd_human_15", TOP_RIGHT_WING_TOUR, track="top_right_wing"
    ),
    _shifted_loop_route(
        "crowd_human_16", MAIN_CENTRAL_LOOP, 0.25, track="main_central"
    ),
    _shifted_loop_route(
        "crowd_human_17", MAIN_CENTRAL_LOOP, 0.75, track="main_central"
    ),
    _shifted_loop_route(
        "crowd_human_18", MAIN_UPPER_LOOP, 0.25, track="main_upper"
    ),
)


CROWD_PATROL_ROUTES: tuple[ControlledPatrolRoute, ...] = (
    NORMAL_PATROL_ROUTES + CROWD_EXTRA_PATROL_ROUTES
)


CONTROLLED_PATROL_SCENARIOS: dict[str, tuple[ControlledPatrolRoute, ...]] = {
    "normal": NORMAL_PATROL_ROUTES,
    "crowd": CROWD_PATROL_ROUTES,
}
