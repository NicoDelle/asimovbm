from __future__ import annotations

from dataclasses import dataclass
from math import cos, floor, sin
from pathlib import Path

from .geometry import Pose2D
from .lidar import LaserScan


@dataclass(frozen=True)
class GridSpec:
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float


class OccupancyGrid:
    def __init__(self, spec: GridSpec) -> None:
        self.spec = spec
        self.log_odds = [0.0 for _ in range(spec.width * spec.height)]
        self.log_free = -0.35
        self.log_occ = 0.85
        self.log_min = -4.0
        self.log_max = 4.0

    def index(self, cell: tuple[int, int]) -> int:
        x, y = cell
        return y * self.spec.width + x

    def in_bounds(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return 0 <= x < self.spec.width and 0 <= y < self.spec.height

    def world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        return (
            floor((x - self.spec.origin_x) / self.spec.resolution),
            floor((y - self.spec.origin_y) / self.spec.resolution),
        )

    def cell_to_world(self, cell: tuple[int, int]) -> tuple[float, float]:
        x, y = cell
        return (
            self.spec.origin_x + (x + 0.5) * self.spec.resolution,
            self.spec.origin_y + (y + 0.5) * self.spec.resolution,
        )

    def is_occupied_cell(self, cell: tuple[int, int], threshold: float = 0.8) -> bool:
        if not self.in_bounds(cell):
            return True
        return self.log_odds[self.index(cell)] >= threshold

    def occupancy_probability(self, cell: tuple[int, int]) -> float:
        if not self.in_bounds(cell):
            return 1.0
        odds = self.log_odds[self.index(cell)]
        return 1.0 - 1.0 / (1.0 + pow(2.718281828459045, odds))

    def update_from_scan(self, pose: Pose2D, scan: LaserScan) -> None:
        start = self.world_to_cell(pose.x, pose.y)
        if not self.in_bounds(start):
            return
        for angle, measured_range in zip(scan.angles, scan.ranges, strict=True):
            yaw = pose.yaw + angle
            end_x = pose.x + measured_range * cos(yaw)
            end_y = pose.y + measured_range * sin(yaw)
            end = self.world_to_cell(end_x, end_y)
            cells = list(bresenham(start, end))
            if not cells:
                continue

            hit = measured_range < scan.max_range * 0.98 and self.in_bounds(end)
            free_cells = cells[:-1] if hit else cells
            for cell in free_cells:
                self._add_log_odds(cell, self.log_free)
            if hit:
                self._add_log_odds(cells[-1], self.log_occ)

    def _add_log_odds(self, cell: tuple[int, int], delta: float) -> None:
        if not self.in_bounds(cell):
            return
        idx = self.index(cell)
        self.log_odds[idx] = max(self.log_min, min(self.log_max, self.log_odds[idx] + delta))

    def save_pgm(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fh:
            fh.write(f"P5\n{self.spec.width} {self.spec.height}\n255\n".encode("ascii"))
            for y in reversed(range(self.spec.height)):
                row = bytearray()
                for x in range(self.spec.width):
                    p = self.occupancy_probability((x, y))
                    row.append(int(255 * (1.0 - p)))
                fh.write(row)


def bresenham(start: tuple[int, int], end: tuple[int, int]):
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    while True:
        yield (x0, y0)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy

