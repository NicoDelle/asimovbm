from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import hypot

from .geometry import Pose2D
from .mapping import OccupancyGrid


@dataclass(frozen=True)
class PlannerConfig:
    robot_radius: float = 0.35
    unknown_penalty: float = 0.08
    occupied_threshold: float = 0.8


class AStarPlanner:
    def __init__(self, grid: OccupancyGrid, config: PlannerConfig | None = None) -> None:
        self.grid = grid
        self.config = config or PlannerConfig()

    def plan(self, start: Pose2D, goal: tuple[float, float]) -> list[tuple[float, float]]:
        start_cell = self.grid.world_to_cell(start.x, start.y)
        goal_cell = self.grid.world_to_cell(goal[0], goal[1])
        if not self.grid.in_bounds(start_cell) or not self.grid.in_bounds(goal_cell):
            return []
        blocked_cells = self._inflated_blocked_cells()
        if self._blocked(goal_cell, blocked_cells):
            goal_cell = self._nearest_unblocked(goal_cell, blocked_cells) or goal_cell

        frontier: list[tuple[float, tuple[int, int]]] = []
        heappush(frontier, (0.0, start_cell))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
        cost_so_far: dict[tuple[int, int], float] = {start_cell: 0.0}

        while frontier:
            _, current = heappop(frontier)
            if current == goal_cell:
                break
            for neighbor, step_cost in self._neighbors(current):
                if self._blocked(neighbor, blocked_cells):
                    continue
                new_cost = cost_so_far[current] + step_cost + self._unknown_cost(neighbor)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + self._heuristic(neighbor, goal_cell)
                    heappush(frontier, (priority, neighbor))
                    came_from[neighbor] = current

        if goal_cell not in came_from:
            return []
        cells = reconstruct_path(came_from, goal_cell)
        return [self.grid.cell_to_world(cell) for cell in cells]

    def _neighbors(self, cell: tuple[int, int]):
        x, y = cell
        for dx, dy, cost in (
            (-1, 0, 1.0),
            (1, 0, 1.0),
            (0, -1, 1.0),
            (0, 1, 1.0),
            (-1, -1, 1.414),
            (-1, 1, 1.414),
            (1, -1, 1.414),
            (1, 1, 1.414),
        ):
            neighbor = (x + dx, y + dy)
            if self.grid.in_bounds(neighbor):
                yield neighbor, cost

    def _inflated_blocked_cells(self) -> set[tuple[int, int]]:
        radius_cells = max(1, int(self.config.robot_radius / self.grid.spec.resolution))
        blocked: set[tuple[int, int]] = set()
        for y in range(self.grid.spec.height):
            for x in range(self.grid.spec.width):
                cell = (x, y)
                if not self.grid.is_occupied_cell(cell, self.config.occupied_threshold):
                    continue
                for yy in range(y - radius_cells, y + radius_cells + 1):
                    for xx in range(x - radius_cells, x + radius_cells + 1):
                        if hypot(xx - x, yy - y) <= radius_cells and self.grid.in_bounds((xx, yy)):
                            blocked.add((xx, yy))
        return blocked

    def _blocked(self, cell: tuple[int, int], blocked_cells: set[tuple[int, int]]) -> bool:
        if not self.grid.in_bounds(cell):
            return True
        return cell in blocked_cells

    def _nearest_unblocked(
        self,
        cell: tuple[int, int],
        blocked_cells: set[tuple[int, int]],
        radius: int = 8,
    ) -> tuple[int, int] | None:
        cx, cy = cell
        for r in range(1, radius + 1):
            candidates = []
            for y in range(cy - r, cy + r + 1):
                for x in range(cx - r, cx + r + 1):
                    candidate = (x, y)
                    if self.grid.in_bounds(candidate) and not self._blocked(candidate, blocked_cells):
                        candidates.append(candidate)
            if candidates:
                return min(candidates, key=lambda c: self._heuristic(c, cell))
        return None

    def _unknown_cost(self, cell: tuple[int, int]) -> float:
        idx = self.grid.index(cell)
        return self.config.unknown_penalty if abs(self.grid.log_odds[idx]) < 0.1 else 0.0

    @staticmethod
    def _heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
        return hypot(a[0] - b[0], a[1] - b[1])


def reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int] | None],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    current: tuple[int, int] | None = goal
    path: list[tuple[int, int]] = []
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path
