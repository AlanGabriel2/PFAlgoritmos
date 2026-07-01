import heapq
import math

import pygame


class PathResult:
    def __init__(self, points=None, found=False, used_hazards=False):
        self.points = points or []
        self.found = found
        self.used_hazards = used_hazards


class PathFinder:
    """A* navigation grid generated from level collision data."""

    def __init__(
        self,
        level=None,
        size=None,
        colliders=None,
        collider_metadata=None,
        walkable_zones=None,
        walkable_metadata=None,
        hazard_zones=None,
        hazard_metadata=None,
        cell_size=None,
        hazard_cost=8.0,
        allow_hazard_fallback=True,
    ):
        if level is not None:
            size = (level.width, level.height)
            colliders = level.colliders
            collider_metadata = level.collider_metadata
            walkable_zones = level.walkable_zones
            walkable_metadata = level.walkable_metadata
            hazard_zones = level.hazard_zones
            hazard_metadata = level.hazard_metadata
            cell_size = cell_size or getattr(level, "pathfinding_cell_size", 48)

        self.width, self.height = int(size[0]), int(size[1])
        self.cell_size = max(16, int(cell_size or 48))
        self.cols = max(1, int(math.ceil(self.width / self.cell_size)))
        self.rows = max(1, int(math.ceil(self.height / self.cell_size)))
        self.map_rect = pygame.Rect(0, 0, self.width, self.height)
        self.hazard_cost = float(hazard_cost)
        self.allow_hazard_fallback = allow_hazard_fallback

        self.colliders = self._enabled_rects(colliders or [], collider_metadata or [])
        self.walkable_zones = self._enabled_rects(walkable_zones or [], walkable_metadata or [])
        self.hazard_zones = self._enabled_rects(hazard_zones or [], hazard_metadata or [])
        self._grid_cache = {}

    def invalidate(self):
        self._grid_cache.clear()

    def _enabled_rects(self, rects, metadata):
        enabled = []
        for index, rect in enumerate(rects):
            data = metadata[index] if index < len(metadata) else {}
            if not data.get("enabled", True):
                continue
            enabled.append(rect.copy() if isinstance(rect, pygame.Rect) else pygame.Rect(rect))
        return enabled

    def _agent_key(self, agent_size):
        if agent_size is None:
            return (24, 24)
        return (max(2, int(math.ceil(agent_size[0]))), max(2, int(math.ceil(agent_size[1]))))

    def world_to_cell(self, position):
        x, y = position
        col = int(max(0, min(self.cols - 1, math.floor(x / self.cell_size))))
        row = int(max(0, min(self.rows - 1, math.floor(y / self.cell_size))))
        return col, row

    def cell_to_world(self, cell):
        col, row = cell
        x = min(self.width - 1, col * self.cell_size + self.cell_size / 2)
        y = min(self.height - 1, row * self.cell_size + self.cell_size / 2)
        return float(x), float(y)

    def cell_rect(self, cell):
        col, row = cell
        x = col * self.cell_size
        y = row * self.cell_size
        w = min(self.cell_size, self.width - x)
        h = min(self.cell_size, self.height - y)
        return pygame.Rect(x, y, w, h)

    def agent_rect_at(self, position, agent_size):
        w, h = self._agent_key(agent_size)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (int(round(position[0])), int(round(position[1])))
        return rect

    def agent_rect_for_cell(self, cell, agent_size):
        return self.agent_rect_at(self.cell_to_world(cell), agent_size)

    def find_path(self, start_pos, goal_pos, agent_size=None, allow_hazard_fallback=None):
        fallback = self.allow_hazard_fallback if allow_hazard_fallback is None else allow_hazard_fallback
        clean_result = self._find_path(start_pos, goal_pos, agent_size, allow_hazards=False)
        if clean_result.found or not fallback or not self.hazard_zones:
            return clean_result

        hazard_result = self._find_path(start_pos, goal_pos, agent_size, allow_hazards=True)
        hazard_result.used_hazards = hazard_result.found
        return hazard_result

    def has_line_of_sight(self, start_pos, goal_pos, agent_size=None, allow_hazards=False):
        dx = goal_pos[0] - start_pos[0]
        dy = goal_pos[1] - start_pos[1]
        distance = math.hypot(dx, dy)
        if distance <= 1:
            return self.is_position_walkable(start_pos, agent_size, allow_hazards=allow_hazards)

        steps = max(1, int(math.ceil(distance / max(8, self.cell_size * 0.35))))
        for step in range(steps + 1):
            t = step / steps
            point = (start_pos[0] + dx * t, start_pos[1] + dy * t)
            rect = self.agent_rect_at(point, agent_size)
            if not self._is_rect_navigable(rect, allow_hazards=allow_hazards):
                return False
        return True

    def is_position_walkable(self, position, agent_size=None, allow_hazards=False):
        rect = self.agent_rect_at(position, agent_size)
        return self._is_rect_navigable(rect, allow_hazards=allow_hazards)

    def _find_path(self, start_pos, goal_pos, agent_size, allow_hazards):
        agent_key = self._agent_key(agent_size)
        start = self.nearest_walkable_cell(self.world_to_cell(start_pos), agent_key, allow_hazards)
        goal = self.nearest_walkable_cell(self.world_to_cell(goal_pos), agent_key, allow_hazards)
        if start is None or goal is None:
            return PathResult(found=False)
        if start == goal:
            return PathResult(points=[goal_pos], found=True)

        open_heap = []
        push_count = 0
        heapq.heappush(open_heap, (0.0, 0.0, push_count, start))
        came_from = {}
        g_score = {start: 0.0}
        closed = set()
        max_expansions = max(128, self.cols * self.rows * 4)
        expansions = 0

        while open_heap and expansions < max_expansions:
            _, current_g, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            if current == goal:
                cells = self._reconstruct_cells(came_from, current)
                points = [self.cell_to_world(cell) for cell in cells[1:]]
                return PathResult(points=points, found=True)

            closed.add(current)
            expansions += 1

            for neighbor, move_cost in self._neighbors(current, agent_key, allow_hazards):
                if neighbor in closed:
                    continue
                hazard_penalty = self.hazard_cost if allow_hazards and self.is_hazard_cell(neighbor, agent_key) else 0.0
                tentative_g = current_g + move_cost + hazard_penalty
                if tentative_g >= g_score.get(neighbor, float("inf")):
                    continue
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                push_count += 1
                f_score = tentative_g + self._heuristic(neighbor, goal)
                heapq.heappush(open_heap, (f_score, tentative_g, push_count, neighbor))

        return PathResult(found=False)

    def nearest_walkable_cell(self, cell, agent_size, allow_hazards=False):
        if self.is_walkable_cell(cell, agent_size, allow_hazards):
            return cell

        max_radius = max(self.cols, self.rows)
        best = None
        best_dist = float("inf")
        start_x, start_y = cell
        for radius in range(1, max_radius + 1):
            for y in range(start_y - radius, start_y + radius + 1):
                for x in range(start_x - radius, start_x + radius + 1):
                    if abs(x - start_x) != radius and abs(y - start_y) != radius:
                        continue
                    candidate = (x, y)
                    if not self.is_walkable_cell(candidate, agent_size, allow_hazards):
                        continue
                    dist = (x - start_x) * (x - start_x) + (y - start_y) * (y - start_y)
                    if dist < best_dist:
                        best = candidate
                        best_dist = dist
            if best is not None:
                return best
        return None

    def is_walkable_cell(self, cell, agent_size, allow_hazards=False):
        col, row = cell
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return False
        base_grid, hazard_grid = self._get_grid(agent_size)
        if not base_grid[row][col]:
            return False
        if hazard_grid[row][col] and not allow_hazards:
            return False
        return True

    def is_hazard_cell(self, cell, agent_size):
        col, row = cell
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return False
        _, hazard_grid = self._get_grid(agent_size)
        return hazard_grid[row][col]

    def _get_grid(self, agent_size):
        agent_key = self._agent_key(agent_size)
        if agent_key in self._grid_cache:
            return self._grid_cache[agent_key]

        base_grid = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        hazard_grid = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        for row in range(self.rows):
            for col in range(self.cols):
                cell = (col, row)
                rect = self.agent_rect_for_cell(cell, agent_key)
                if self._is_rect_navigable(rect, allow_hazards=True, ignore_hazards=True):
                    base_grid[row][col] = True
                    hazard_grid[row][col] = any(rect.colliderect(hazard) for hazard in self.hazard_zones)

        self._grid_cache[agent_key] = (base_grid, hazard_grid)
        return base_grid, hazard_grid

    def _is_rect_navigable(self, rect, allow_hazards=False, ignore_hazards=False):
        if not self.map_rect.contains(rect):
            return False
        if self.walkable_zones and not any(zone.collidepoint(rect.center) for zone in self.walkable_zones):
            return False
        if any(rect.colliderect(collider) for collider in self.colliders):
            return False
        if not ignore_hazards and not allow_hazards:
            if any(rect.colliderect(hazard) for hazard in self.hazard_zones):
                return False
        return True

    def _neighbors(self, cell, agent_size, allow_hazards):
        x, y = cell
        directions = (
            (-1, 0, 1.0),
            (1, 0, 1.0),
            (0, -1, 1.0),
            (0, 1, 1.0),
            (-1, -1, math.sqrt(2)),
            (1, -1, math.sqrt(2)),
            (-1, 1, math.sqrt(2)),
            (1, 1, math.sqrt(2)),
        )
        for dx, dy, cost in directions:
            neighbor = (x + dx, y + dy)
            if not self.is_walkable_cell(neighbor, agent_size, allow_hazards):
                continue
            if dx != 0 and dy != 0:
                side_a = (x + dx, y)
                side_b = (x, y + dy)
                if not self.is_walkable_cell(side_a, agent_size, allow_hazards):
                    continue
                if not self.is_walkable_cell(side_b, agent_size, allow_hazards):
                    continue
            yield neighbor, cost

    def _reconstruct_cells(self, came_from, current):
        cells = [current]
        while current in came_from:
            current = came_from[current]
            cells.append(current)
        cells.reverse()
        return cells

    def _heuristic(self, a, b):
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        straight = abs(dx - dy)
        diagonal = min(dx, dy)
        return straight + diagonal * math.sqrt(2)
