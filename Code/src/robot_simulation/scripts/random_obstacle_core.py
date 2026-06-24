"""Map geometry utilities for the controlled obstacle spawner."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np
import yaml
from PIL import Image, ImageFilter


Point2D = Tuple[float, float]
Cell = Tuple[int, int]


@dataclass
class OccupancyMap:
    """ROS occupancy map with a clearance-aware valid-cell mask."""

    yaml_path: str
    image_path: str
    resolution: float
    origin: Tuple[float, float, float]
    occupied_thresh: float
    free_thresh: float
    negate: bool
    valid_mask: np.ndarray
    valid_cell_count: int

    @classmethod
    def load(cls, yaml_path: str, clearance: float) -> "OccupancyMap":
        """Load a ROS map YAML and build a mask clear of walls/unknown cells."""
        yaml_path = os.path.abspath(os.path.expanduser(yaml_path))
        if not os.path.isfile(yaml_path):
            raise FileNotFoundError(f"Map YAML not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as stream:
            metadata = yaml.safe_load(stream) or {}

        required = (
            "image",
            "resolution",
            "origin",
            "occupied_thresh",
            "free_thresh",
            "negate",
        )
        missing = [key for key in required if key not in metadata]
        if missing:
            raise ValueError(
                f"Map YAML is missing required keys: {', '.join(missing)}"
            )

        image_path = os.path.expanduser(str(metadata["image"]))
        if not os.path.isabs(image_path):
            image_path = os.path.join(os.path.dirname(yaml_path), image_path)
        image_path = os.path.abspath(image_path)
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Map image not found: {image_path}")

        resolution = float(metadata["resolution"])
        if resolution <= 0.0:
            raise ValueError("Map resolution must be positive")
        if clearance < 0.0:
            raise ValueError("Map clearance cannot be negative")

        origin_values = metadata["origin"]
        if not isinstance(origin_values, Sequence) or len(origin_values) < 3:
            raise ValueError("Map origin must contain [x, y, yaw]")
        origin = tuple(float(value) for value in origin_values[:3])

        occupied_thresh = float(metadata["occupied_thresh"])
        free_thresh = float(metadata["free_thresh"])
        negate = bool(int(metadata["negate"]))
        if not 0.0 <= free_thresh <= occupied_thresh <= 1.0:
            raise ValueError("Invalid free/occupied map thresholds")

        image = Image.open(image_path).convert("L")
        pixels_u8 = np.frombuffer(image.tobytes(), dtype=np.uint8).reshape(
            image.height, image.width
        )
        pixels = pixels_u8.astype(np.float64)
        occupancy = pixels / 255.0 if negate else (255.0 - pixels) / 255.0

        # Anything that is not explicitly free is unsafe, including unknown cells.
        # ROS map_saver conventionally writes unknown trinary cells as grey 205.
        free_mask = np.logical_and(occupancy < free_thresh, pixels_u8 != 205)
        unsafe = np.logical_not(free_mask)
        clearance_cells = int(math.ceil(clearance / resolution))

        if clearance_cells:
            kernel_size = 2 * clearance_cells + 1
            unsafe_image = Image.fromarray((unsafe * 255).astype(np.uint8))
            dilated = unsafe_image.filter(ImageFilter.MaxFilter(kernel_size))
            unsafe = np.frombuffer(dilated.tobytes(), dtype=np.uint8).reshape(
                dilated.height, dilated.width
            ) > 0

        valid_mask = np.logical_not(unsafe)
        if clearance_cells:
            # Treat the region outside the image as occupied as well.
            valid_mask[:clearance_cells, :] = False
            valid_mask[-clearance_cells:, :] = False
            valid_mask[:, :clearance_cells] = False
            valid_mask[:, -clearance_cells:] = False

        valid_cell_count = int(np.count_nonzero(valid_mask))
        if not valid_cell_count:
            raise ValueError(
                "No valid map cells remain after applying wall clearance"
            )

        return cls(
            yaml_path=yaml_path,
            image_path=image_path,
            resolution=resolution,
            origin=origin,
            occupied_thresh=occupied_thresh,
            free_thresh=free_thresh,
            negate=negate,
            valid_mask=valid_mask,
            valid_cell_count=valid_cell_count,
        )

    @property
    def height(self) -> int:
        return int(self.valid_mask.shape[0])

    @property
    def width(self) -> int:
        return int(self.valid_mask.shape[1])

    def cell_to_world(self, row: int, col: int) -> Point2D:
        """Convert an image row/column to the centre of a map cell."""
        local_x = (col + 0.5) * self.resolution
        local_y = (self.height - row - 0.5) * self.resolution
        cos_yaw = math.cos(self.origin[2])
        sin_yaw = math.sin(self.origin[2])
        return (
            self.origin[0] + cos_yaw * local_x - sin_yaw * local_y,
            self.origin[1] + sin_yaw * local_x + cos_yaw * local_y,
        )

    def world_to_cell(self, x: float, y: float) -> Optional[Cell]:
        """Convert map coordinates to an image row/column."""
        dx = x - self.origin[0]
        dy = y - self.origin[1]
        cos_yaw = math.cos(self.origin[2])
        sin_yaw = math.sin(self.origin[2])
        local_x = cos_yaw * dx + sin_yaw * dy
        local_y = -sin_yaw * dx + cos_yaw * dy
        col = int(math.floor(local_x / self.resolution))
        map_row = int(math.floor(local_y / self.resolution))
        row = self.height - 1 - map_row
        if row < 0 or row >= self.height or col < 0 or col >= self.width:
            return None
        return row, col

    def is_valid_world(self, point: Point2D) -> bool:
        """Return whether a world point lies in the clearance-aware mask."""
        cell = self.world_to_cell(*point)
        return bool(cell is not None and self.valid_mask[cell])

    def line_is_valid(self, start: Point2D, end: Point2D) -> bool:
        """Sample a segment densely enough that it cannot skip a map cell."""
        if not self.is_valid_world(start) or not self.is_valid_world(end):
            return False
        distance = math.dist(start, end)
        samples = max(1, int(math.ceil(distance / (0.5 * self.resolution))))
        for index in range(samples + 1):
            ratio = index / samples
            point = (
                start[0] + ratio * (end[0] - start[0]),
                start[1] + ratio * (end[1] - start[1]),
            )
            if not self.is_valid_world(point):
                return False
        return True
