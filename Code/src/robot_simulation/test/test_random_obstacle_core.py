"""Tests for map-aware controlled obstacle geometry."""

import math
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from random_obstacle_core import OccupancyMap  # noqa: E402


def write_map(tmp_path, pixels, resolution=0.1, origin=None):
    """Write a minimal ROS map and return its YAML path."""
    image_path = tmp_path / "test_map.pgm"
    Image.fromarray(pixels.astype(np.uint8)).save(image_path)
    yaml_path = tmp_path / "test_map.yaml"
    metadata = {
        "image": image_path.name,
        "resolution": resolution,
        "origin": origin or [0.0, 0.0, 0.0],
        "negate": 0,
        "occupied_thresh": 0.65,
        "free_thresh": 0.25,
    }
    yaml_path.write_text(yaml.safe_dump(metadata), encoding="utf-8")
    return yaml_path


def test_unknown_and_clearance_cells_are_rejected(tmp_path):
    pixels = np.full((15, 15), 254, dtype=np.uint8)
    pixels[7, 7] = 0
    pixels[2, 2] = 205
    grid = OccupancyMap.load(str(write_map(tmp_path, pixels)), clearance=0.2)

    assert not grid.valid_mask[7, 7]
    assert not grid.valid_mask[7, 9]
    assert grid.valid_mask[7, 10]
    assert not grid.valid_mask[2, 2]


def test_world_cell_round_trip_supports_rotated_origins(tmp_path):
    pixels = np.full((12, 16), 254, dtype=np.uint8)
    grid = OccupancyMap.load(
        str(
            write_map(
                tmp_path,
                pixels,
                resolution=0.05,
                origin=[-2.0, 3.0, math.pi / 3.0],
            )
        ),
        clearance=0.0,
    )

    for cell in ((0, 0), (5, 8), (11, 15)):
        assert grid.world_to_cell(*grid.cell_to_world(*cell)) == cell


def test_line_validation_rejects_a_wall(tmp_path):
    pixels = np.full((25, 25), 254, dtype=np.uint8)
    pixels[:, 12] = 0
    pixels[2, 12] = 254
    grid = OccupancyMap.load(str(write_map(tmp_path, pixels)), clearance=0.0)
    start = grid.cell_to_world(18, 4)
    goal = grid.cell_to_world(18, 20)
    open_goal = grid.cell_to_world(18, 8)

    assert not grid.line_is_valid(start, goal)
    assert grid.line_is_valid(start, open_goal)
