"""Deterministic emergency scenario routes for the hospital map."""

from __future__ import annotations

from dataclasses import dataclass

from random_obstacle_core import Point2D


@dataclass(frozen=True)
class ControlledEmergencyRoute:
    """One fixed route used by one controlled emergency person."""

    name: str
    start: Point2D
    to_emergency: tuple[Point2D, ...]
    from_emergency: tuple[Point2D, ...]
    egress_delay: float = 0.0

    @property
    def gathering_point(self) -> Point2D:
        return self.to_emergency[-1]


CONTROLLED_EMERGENCY_ROUTES: tuple[ControlledEmergencyRoute, ...] = (
    ControlledEmergencyRoute(
        name="controlled_human_1",
        start=(-4.5, -30.0),
        to_emergency=((-5.62, -10.07),),
        from_emergency=((-4.5, -30.0),),
        egress_delay=0.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_2",
        start=(0.0, -25.0),
        to_emergency=(
            (-4.475, -23.925),
            (-4.525, -23.775),
            (-4.475, -9.225),
            (-2.62, -7.93),
        ),
        from_emergency=(
            (-4.475, -9.225),
            (-4.575, -23.875),
            (-0.325, -24.975),
            (0.0, -25.0),
        ),
        egress_delay=24.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_3",
        start=(5.0, -22.0),
        to_emergency=(
            (4.375, -15.175),
            (4.225, -15.125),
            (-0.425, -13.925),
            (-4.475, -13.925),
            (-4.475, -11.225),
            (-4.425, -9.175),
            (-4.175, -9.125),
            (-1.67, -9.12),
        ),
        from_emergency=(
            (-4.375, -9.125),
            (-4.424999999999999, -9.274999999999999),
            (-4.475, -13.225000000000001),
            (-4.475, -13.925),
            (4.325000000000001, -15.125),
            (4.475, -15.575),
            (4.525, -15.875),
            (5.0, -22.0),
        ),
        egress_delay=18.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_4",
        start=(5.0, -14.0),
        to_emergency=(
            (-4.475, -13.925),
            (-5.57, -8.48),
        ),
        from_emergency=(
            (-4.475, -13.925),
            (5.0, -14.0),
        ),
        egress_delay=30.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_5",
        start=(5.0, 2.0),
        to_emergency=(
            (4.375, -13.575),
            (4.325, -13.975),
            (-4.475, -13.925),
            (-4.475, -9.225),
            (-3.82, -8.93),
        ),
        from_emergency=(
            (-4.425, -9.175),
            (-4.475, -13.325),
            (-4.475, -13.925),
            (4.325, -13.975),
            (5.025, -1.975),
            (5.025, -1.425),
            (5.0, 2.0),
        ),
        egress_delay=12.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_6",
        start=(0.0, 14.0),
        to_emergency=(
            (4.225, 4.725),
            (4.375, 3.875),
            (4.425, -2.275),
            (4.375, -13.575),
            (4.325, -13.975),
            (-4.475, -13.925),
            (-4.475, -11.225),
            (-4.42, -11.23),
        ),
        from_emergency=(
            (-4.475, -11.225),
            (-4.475, -13.925),
            (4.325, -13.975),
            (4.425, -13.125),
            (4.425, -12.225),
            (4.425, 0.825),
            (4.375, 4.275),
            (3.925, 5.425),
            (3.875, 5.525),
            (0.0, 14.0),
        ),
        egress_delay=6.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_7",
        start=(-4.5, 14.0),
        to_emergency=(
            (1.525, 8.425),
            (2.325, 7.675),
            (4.175, 5.025),
            (4.425, 3.575),
            (4.375, -13.575),
            (4.325, -13.975),
            (-4.475, -13.925),
            (-4.47, -12.98),
        ),
        from_emergency=(
            (-4.475, -13.925),
            (4.325, -13.975),
            (4.425, -13.125),
            (4.425, -12.225),
            (4.425, 0.825),
            (4.375, 4.275),
            (3.925, 5.425),
            (3.875, 5.525),
            (1.275, 8.725),
            (-4.5, 14.0),
        ),
        egress_delay=0.0,
    ),
    ControlledEmergencyRoute(
        name="controlled_human_8",
        start=(-5.0, 0.0),
        to_emergency=((-4.87, -7.02),),
        from_emergency=((-5.0, 0.0),),
        egress_delay=0.0,
    ),
)
