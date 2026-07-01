import math
import random

import pygame


def _clamp(value, low, high):
    return max(low, min(high, value))


def _normalized(dx, dy, length=1.0):
    distance = math.hypot(dx, dy)
    if distance <= 0.0001:
        return 0.0, 0.0
    scale = length / distance
    return dx * scale, dy * scale


def separation_delta(enemy, nearby_enemies, weight=None):
    if not nearby_enemies:
        return 0.0, 0.0

    weight = getattr(enemy, "separation_weight", 0.55) if weight is None else weight
    if weight <= 0:
        return 0.0, 0.0

    push_x = 0.0
    push_y = 0.0
    for other in nearby_enemies:
        if other is enemy or not hasattr(other, "x") or not hasattr(other, "y"):
            continue
        dx = enemy.x - other.x
        dy = enemy.y - other.y
        distance = math.hypot(dx, dy)
        min_distance = max(12.0, (enemy.radius + other.radius) * 0.78)
        if distance >= min_distance:
            continue
        if distance <= 0.001:
            angle = random.random() * math.tau
            dx = math.cos(angle)
            dy = math.sin(angle)
            distance = 1.0
        strength = (min_distance - distance) / min_distance
        nx, ny = _normalized(dx, dy)
        push_x += nx * strength
        push_y += ny * strength

    max_push = max(0.35, enemy.speed * weight)
    return _normalized(push_x, push_y, max_push)


class EnemyNavigator:
    """Per-enemy path state and anti-stuck behavior."""

    def __init__(self):
        self.path = []
        self.path_index = 0
        self.current_waypoint = None
        self.mode = "direct"
        self.used_hazards = False
        self.repath_timer = random.randint(0, 18)
        self.target_snapshot = None
        self.force_repath = True
        self.force_path_frames = 0
        self.stuck_frames = 0
        self.collision_frames = 0
        self.no_path_frames = 0
        self.fallback_frames = 0
        self.recovery_frames = 0
        self.recovery_target = None
        self.recovery_side = random.choice((-1, 1))
        self.last_collision_flags = {"x": False, "y": False}
        self.last_attempted_delta = (0.0, 0.0)
        self.last_recovery_reason = "idle"
        self.last_result_found = False

    def clear_path(self):
        self.path = []
        self.path_index = 0
        self.current_waypoint = None
        self.used_hazards = False
        self.last_result_found = False

    def plan_movement(self, enemy, target_pos, intended_delta, pathfinder):
        speed = math.hypot(intended_delta[0], intended_delta[1])
        if speed <= 0.01 or pathfinder is None:
            self.mode = "direct"
            return intended_delta

        smartness = _clamp(getattr(enemy, "ai_smartness", 1.0), 0.0, 1.0)
        if smartness <= 0.05:
            self.mode = "direct"
            self.clear_path()
            return intended_delta

        enemy_pos = (enemy.x, enemy.y)
        agent_size = (enemy.rect.w, enemy.rect.h)
        self.repath_timer -= 1
        if self.force_path_frames > 0:
            self.force_path_frames -= 1

        if self.recovery_frames > 0:
            recovery_delta = self._recovery_delta(enemy_pos, target_pos, speed, agent_size, pathfinder)
            self.recovery_frames -= 1
            if recovery_delta is not None:
                return recovery_delta

        has_clear_route = pathfinder.has_line_of_sight(enemy_pos, target_pos, agent_size, allow_hazards=False)
        if has_clear_route and self.force_path_frames <= 0:
            self.mode = "direct"
            self.clear_path()
            self.fallback_frames = 0
            return intended_delta

        if self._needs_repath(target_pos, pathfinder, smartness):
            self._recalculate_path(enemy_pos, target_pos, agent_size, pathfinder, smartness)

        waypoint = self._active_waypoint(enemy_pos, enemy, pathfinder)
        if waypoint is None:
            self.mode = "fallback"
            self.fallback_frames += 1
            if self.fallback_frames >= 8:
                self._start_recovery(frames=32, clear_path=False, reason="no_path")
            return self._fallback_delta(enemy_pos, target_pos, speed)

        self.fallback_frames = 0
        self.mode = "astar_hazard" if self.used_hazards else "astar"
        dx = waypoint[0] - enemy.x
        dy = waypoint[1] - enemy.y
        return _normalized(dx, dy, speed)

    def record_result(self, before_pos, after_pos, attempted_delta, collision_flags):
        attempted = math.hypot(attempted_delta[0], attempted_delta[1])
        moved = math.hypot(after_pos[0] - before_pos[0], after_pos[1] - before_pos[1])
        collided = bool(collision_flags.get("x") or collision_flags.get("y"))

        if attempted > 0.4:
            self.last_attempted_delta = attempted_delta

        if collided:
            self.last_collision_flags = {"x": bool(collision_flags.get("x")), "y": bool(collision_flags.get("y"))}
        else:
            self.last_collision_flags = {"x": False, "y": False}

        if attempted > 0.4 and moved < min(0.9, attempted * 0.45):
            self.stuck_frames += 1
        else:
            self.stuck_frames = max(0, self.stuck_frames - 2)

        if collided and attempted > 0.4:
            self.collision_frames += 1
        else:
            self.collision_frames = max(0, self.collision_frames - 1)

        if self.stuck_frames >= 6 or self.collision_frames >= 4:
            reason = "collision" if self.collision_frames >= 4 else "stuck"
            self._start_recovery(frames=42, clear_path=True, reason=reason)
            self.stuck_frames = 0
            self.collision_frames = 0
            if self.path and self.path_index < len(self.path) - 1:
                self.path_index += 1

    def _start_recovery(self, frames=30, clear_path=True, reason="stuck"):
        self.force_repath = True
        self.force_path_frames = max(self.force_path_frames, 80)
        self.recovery_frames = max(self.recovery_frames, frames)
        self.recovery_target = None
        self.recovery_side *= -1
        self.fallback_frames = 0
        self.last_recovery_reason = reason
        if clear_path:
            self.path = []
            self.path_index = 0
            self.current_waypoint = None

    def _needs_repath(self, target_pos, pathfinder, smartness):
        if self.force_repath or not self.path:
            return True
        if self.repath_timer <= 0:
            return True
        if self.target_snapshot is None:
            return True
        moved = math.hypot(target_pos[0] - self.target_snapshot[0], target_pos[1] - self.target_snapshot[1])
        target_threshold = max(pathfinder.cell_size * 1.2, 96 - smartness * 36)
        return moved >= target_threshold

    def _recalculate_path(self, enemy_pos, target_pos, agent_size, pathfinder, smartness):
        result = pathfinder.find_path(enemy_pos, target_pos, agent_size=agent_size)
        self.path = result.points
        self.path_index = 0
        self.used_hazards = result.used_hazards
        self.last_result_found = result.found
        self.target_snapshot = target_pos
        self.force_repath = False
        self.repath_timer = int(45 - smartness * 24) + random.randint(0, 8)
        if not result.found:
            self.no_path_frames += 1
        else:
            self.no_path_frames = 0

    def _active_waypoint(self, enemy_pos, enemy, pathfinder):
        if not self.path:
            self.current_waypoint = None
            return None

        reach_radius = max(10.0, min(pathfinder.cell_size * 0.45, enemy.radius * 0.85))
        while self.path_index < len(self.path):
            waypoint = self.path[self.path_index]
            if math.hypot(waypoint[0] - enemy_pos[0], waypoint[1] - enemy_pos[1]) > reach_radius:
                self.current_waypoint = waypoint
                return waypoint
            self.path_index += 1

        self.current_waypoint = None
        return None

    def _fallback_delta(self, enemy_pos, target_pos, speed):
        # Orbit near the obstacle while waiting for the next valid A* route.
        dx = target_pos[0] - enemy_pos[0]
        dy = target_pos[1] - enemy_pos[1]
        if math.hypot(dx, dy) <= 0.001:
            return 0.0, 0.0
        direction = -1 if (self.no_path_frames // 45) % 2 else 1
        side_x, side_y = _normalized(-dy * direction, dx * direction, speed * 0.7)
        forward_x, forward_y = _normalized(dx, dy, speed * 0.25)
        return side_x + forward_x, side_y + forward_y

    def _recovery_delta(self, enemy_pos, target_pos, speed, agent_size, pathfinder):
        if self.recovery_target is None:
            self.recovery_target = self._find_recovery_target(enemy_pos, target_pos, agent_size, pathfinder)

        if self.recovery_target is None:
            self.mode = "fallback"
            return self._fallback_delta(enemy_pos, target_pos, speed)

        distance = math.hypot(self.recovery_target[0] - enemy_pos[0], self.recovery_target[1] - enemy_pos[1])
        if distance <= max(8, speed * 2):
            self.recovery_target = self._find_recovery_target(enemy_pos, target_pos, agent_size, pathfinder)
            if self.recovery_target is None:
                self.mode = "fallback"
                return self._fallback_delta(enemy_pos, target_pos, speed)

        self.mode = "unstuck"
        dx = self.recovery_target[0] - enemy_pos[0]
        dy = self.recovery_target[1] - enemy_pos[1]
        return _normalized(dx, dy, speed)

    def _find_recovery_target(self, enemy_pos, target_pos, agent_size, pathfinder):
        cell = max(16, getattr(pathfinder, "cell_size", 48))
        tangent_radii = (cell * 0.85, cell * 1.35, cell * 2.0, cell * 2.8, cell * 3.6)
        best_point = self._best_recovery_point(
            enemy_pos,
            target_pos,
            agent_size,
            pathfinder,
            self._recovery_directions(enemy_pos, target_pos),
            tangent_radii,
        )
        if best_point is not None:
            return best_point

        base_angle = math.atan2(target_pos[1] - enemy_pos[1], target_pos[0] - enemy_pos[0])
        angle_offsets = (
            math.pi / 2 * self.recovery_side,
            -math.pi / 2 * self.recovery_side,
            math.pi / 4 * self.recovery_side,
            -math.pi / 4 * self.recovery_side,
            math.pi,
            math.pi * 0.75 * self.recovery_side,
            -math.pi * 0.75 * self.recovery_side,
            0.0,
        )
        radial_directions = [(math.cos(base_angle + offset), math.sin(base_angle + offset)) for offset in angle_offsets]
        return self._best_recovery_point(
            enemy_pos,
            target_pos,
            agent_size,
            pathfinder,
            radial_directions,
            (cell * 1.15, cell * 1.85, cell * 2.6, cell * 3.5),
        )

    def _recovery_directions(self, enemy_pos, target_pos):
        to_target = _normalized(target_pos[0] - enemy_pos[0], target_pos[1] - enemy_pos[1])
        if to_target == (0.0, 0.0):
            to_target = (float(self.recovery_side), 0.0)

        attempted_x, attempted_y = self.last_attempted_delta
        blocked_x = self.last_collision_flags.get("x", False)
        blocked_y = self.last_collision_flags.get("y", False)
        directions = []

        if blocked_x:
            preferred_y = attempted_y if abs(attempted_y) > 0.05 else target_pos[1] - enemy_pos[1]
            y_sign = self.recovery_side if abs(preferred_y) <= 0.05 else (1 if preferred_y > 0 else -1)
            directions.extend(((0.0, float(y_sign)), (0.0, float(-y_sign))))
            away_x = -1 if attempted_x > 0 else 1
            directions.extend(((float(away_x), y_sign * 0.35), (float(away_x), -y_sign * 0.35)))

        if blocked_y:
            preferred_x = attempted_x if abs(attempted_x) > 0.05 else target_pos[0] - enemy_pos[0]
            x_sign = self.recovery_side if abs(preferred_x) <= 0.05 else (1 if preferred_x > 0 else -1)
            directions.extend(((float(x_sign), 0.0), (float(-x_sign), 0.0)))
            away_y = -1 if attempted_y > 0 else 1
            directions.extend(((x_sign * 0.35, float(away_y)), (-x_sign * 0.35, float(away_y))))

        side = (-to_target[1] * self.recovery_side, to_target[0] * self.recovery_side)
        directions.extend((side, (-side[0], -side[1]), to_target, (-to_target[0], -to_target[1])))
        return self._unique_directions(directions)

    def _unique_directions(self, directions):
        unique = []
        seen = set()
        for dx, dy in directions:
            nx, ny = _normalized(dx, dy)
            if nx == 0.0 and ny == 0.0:
                continue
            key = (round(nx, 2), round(ny, 2))
            if key in seen:
                continue
            seen.add(key)
            unique.append((nx, ny))
        return unique

    def _best_recovery_point(self, enemy_pos, target_pos, agent_size, pathfinder, directions, radii):
        best_point = None
        best_score = float("inf")
        for direction_index, (dir_x, dir_y) in enumerate(directions):
            for radius_index, radius in enumerate(radii):
                point = (enemy_pos[0] + dir_x * radius, enemy_pos[1] + dir_y * radius)
                if not pathfinder.is_position_walkable(point, agent_size, allow_hazards=True):
                    continue
                if not pathfinder.has_line_of_sight(enemy_pos, point, agent_size, allow_hazards=True):
                    continue

                distance_to_target = math.hypot(target_pos[0] - point[0], target_pos[1] - point[1])
                score = distance_to_target + direction_index * 12.0 + radius_index * 5.0
                if score < best_score:
                    best_score = score
                    best_point = point

            if best_point is not None and direction_index <= 1:
                return best_point
        return best_point


def draw_enemy_ai_debug(surface, enemies, pathfinder, camera=(0, 0), font=None, player_pos=None):
    if pathfinder is None:
        return

    offset_x, offset_y = int(camera[0]), int(camera[1])
    if player_pos is not None:
        player_cell = pathfinder.world_to_cell(player_pos)
        pygame.draw.rect(surface, (80, 160, 255), pathfinder.cell_rect(player_cell).move(offset_x, offset_y), 1)

    for enemy in enemies:
        navigator = getattr(enemy, "navigator", None)
        if navigator is None:
            continue

        enemy_cell = pathfinder.world_to_cell((enemy.x, enemy.y))
        pygame.draw.rect(surface, (255, 180, 80), pathfinder.cell_rect(enemy_cell).move(offset_x, offset_y), 1)

        route = navigator.path[navigator.path_index :]
        if route:
            points = [(int(enemy.x + offset_x), int(enemy.y + offset_y))]
            points.extend((int(x + offset_x), int(y + offset_y)) for x, y in route)
            if len(points) > 1:
                color = (255, 210, 60) if not navigator.used_hazards else (255, 120, 220)
                pygame.draw.lines(surface, color, False, points, 2)
            for x, y in route:
                pygame.draw.circle(surface, (255, 245, 120), (int(x + offset_x), int(y + offset_y)), 4)

        if navigator.current_waypoint is not None:
            wx, wy = navigator.current_waypoint
            pygame.draw.circle(surface, (80, 255, 140), (int(wx + offset_x), int(wy + offset_y)), 7, 2)

        if getattr(navigator, "recovery_target", None) is not None and getattr(navigator, "recovery_frames", 0) > 0:
            rx, ry = navigator.recovery_target
            start = (int(enemy.x + offset_x), int(enemy.y + offset_y))
            target = (int(rx + offset_x), int(ry + offset_y))
            pygame.draw.line(surface, (190, 100, 255), start, target, 2)
            pygame.draw.circle(surface, (230, 140, 255), target, 7, 2)

        if hasattr(enemy, "jump_debug_start") and hasattr(enemy, "jump_debug_target"):
            start = enemy.jump_debug_start
            target = enemy.jump_debug_target
            target_color = (80, 255, 140) if getattr(enemy, "jump_landing_valid", True) else (255, 120, 80)
            if getattr(enemy, "jump_landing_fallback", False):
                target_color = (255, 210, 70)

            start_screen = (int(start[0] + offset_x), int(start[1] + offset_y))
            target_screen = (int(target[0] + offset_x), int(target[1] + offset_y))
            pygame.draw.circle(surface, (100, 180, 255), start_screen, 6, 2)
            pygame.draw.circle(surface, target_color, target_screen, 8, 2)

            arc_points = []
            for step in range(17):
                t = step / 16
                x = start[0] + (target[0] - start[0]) * t
                y = start[1] + (target[1] - start[1]) * t
                lift = math.sin(t * math.pi) * getattr(enemy, "jump_height", 80) * 0.45
                arc_points.append((int(x + offset_x), int(y + offset_y - lift)))
            if len(arc_points) > 1:
                pygame.draw.lines(surface, target_color, False, arc_points, 2)

            for candidate in getattr(enemy, "jump_landing_candidates", [])[:36]:
                point = candidate.get("point")
                if not point:
                    continue
                color = (80, 210, 120) if candidate.get("valid") else (255, 80, 80)
                pygame.draw.circle(surface, color, (int(point[0] + offset_x), int(point[1] + offset_y)), 2)

            if font is not None and (getattr(enemy, "jump_timer", 0) > 0 or getattr(enemy, "jump_landing_reason", "idle") != "idle"):
                jump_label = "jump valid" if getattr(enemy, "jump_landing_valid", True) else "jump fallback"
                if getattr(enemy, "jump_landing_fallback", False):
                    jump_label = "jump fallback"
                reason = getattr(enemy, "jump_landing_reason", "")
                if reason:
                    jump_label += f" ({reason})"
                text = font.render(jump_label, True, target_color)
                bg = pygame.Surface((text.get_width() + 6, text.get_height() + 4), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 165))
                surface.blit(bg, (target_screen[0] + 9, target_screen[1] - 9))
                surface.blit(text, (target_screen[0] + 12, target_screen[1] - 7))
        if font is not None:
            label = f"{navigator.mode}"
            if navigator.last_result_found and navigator.path:
                label += f" {len(navigator.path) - navigator.path_index}"
            text = font.render(label, True, (255, 255, 255))
            bg = pygame.Surface((text.get_width() + 6, text.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 150))
            x = int(enemy.x + offset_x - text.get_width() / 2)
            y = int(enemy.y + offset_y - enemy.radius - text.get_height() - 8)
            surface.blit(bg, (x - 3, y - 2))
            surface.blit(text, (x, y))
