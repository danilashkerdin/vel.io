import math
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ClosurePoint:
    start_index: int
    end_index: int
    distance_meters: float


class GPSClosureDetector:
    """Ищет все замкнутые контуры с порогом 10 метров."""

    def __init__(self, closure_threshold: float = 10.0):
        self.closure_threshold = closure_threshold
        self.min_loop_points = 5

    def find_all_closures(self, points: List[Tuple[float, float, float]]) -> List[ClosurePoint]:
        closures = []
        n = len(points)

        if n < self.min_loop_points:
            return closures

        # Всегда проверяем начало и конец
        first = points[0]
        last = points[-1]
        start_end_dist = self._fast_distance(first[0], first[1], last[0], last[1])

        if start_end_dist <= self.closure_threshold:
            closures.append(ClosurePoint(
                start_index=0,
                end_index=n - 1,
                distance_meters=start_end_dist,
            ))

        # Ищем внутренние замыкания
        proximity = self._build_proximity_map(points)

        for start_idx in range(n - self.min_loop_points):
            nearby = proximity.get(start_idx, [])

            for end_idx, distance in nearby:
                if end_idx - start_idx < self.min_loop_points:
                    continue

                if self._is_valid_closure(points, start_idx, end_idx):
                    closures.append(ClosurePoint(
                        start_index=start_idx,
                        end_index=end_idx,
                        distance_meters=distance,
                    ))

        closures = self._deduplicate(closures)
        closures.sort(key=lambda c: c.end_index - c.start_index, reverse=True)
        return closures

    def _build_proximity_map(self, points: List[Tuple]) -> dict:
        proximity = {}
        n = len(points)

        # Строим сетку с шагом ~10 метров
        grid_step = 0.0001  # примерно 10м
        grid = {}

        for i, (lat, lon, *_) in enumerate(points):
            key = (int(lat / grid_step), int(lon / grid_step))
            if key not in grid:
                grid[key] = []
            grid[key].append(i)

        for i in range(n - self.min_loop_points):
            lat, lon = points[i][0], points[i][1]
            nearby = []

            # Проверяем только соседние ячейки
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    key = (int(lat / grid_step) + dx, int(lon / grid_step) + dy)
                    if key in grid:
                        for j in grid[key]:
                            if j > i + self.min_loop_points:
                                dist = self._fast_distance(lat, lon, points[j][0], points[j][1])
                                if dist <= self.closure_threshold:
                                    nearby.append((j, dist))

            if nearby:
                nearby.sort(key=lambda x: x[1])
                grouped = []
                current = [nearby[0]]
                for k in range(1, len(nearby)):
                    if nearby[k][0] - nearby[k-1][0] <= 3:
                        current.append(nearby[k])
                    else:
                        grouped.append(min(current, key=lambda x: x[1]))
                        current = [nearby[k]]
                if current:
                    grouped.append(min(current, key=lambda x: x[1]))
                proximity[i] = grouped

        return proximity

    def _fast_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        lat_m = 111320
        lon_m = 111320 * math.cos(math.radians((lat1 + lat2) / 2))
        dlat = (lat2 - lat1) * lat_m
        dlon = (lon2 - lon1) * lon_m
        return math.sqrt(dlat ** 2 + dlon ** 2)

    def _is_valid_closure(self, points: List[Tuple], start_idx: int, end_idx: int) -> bool:
        """Проверяет валидность замыкания. Single-pass min/max без создания временных списков."""
        length = end_idx - start_idx + 1
        if length < self.min_loop_points:
            return False

        min_lat = max_lat = points[start_idx][0]
        min_lon = max_lon = points[start_idx][1]
        sum_lat = 0.0

        for i in range(start_idx, end_idx + 1):
            lat = points[i][0]
            lon = points[i][1]
            if lat < min_lat: min_lat = lat
            elif lat > max_lat: max_lat = lat
            if lon < min_lon: min_lon = lon
            elif lon > max_lon: max_lon = lon
            sum_lat += lat

        lat_range = (max_lat - min_lat) * 111320
        lon_range = (max_lon - min_lon) * 111320 * math.cos(math.radians(sum_lat / length))

        if lat_range == 0 or lon_range == 0:
            return False

        aspect = max(lat_range, lon_range) / min(lat_range, lon_range)
        return aspect <= 15

    def _deduplicate(self, closures: List[ClosurePoint]) -> List[ClosurePoint]:
        if len(closures) <= 1:
            return closures

        closures.sort(key=lambda c: c.end_index - c.start_index, reverse=True)
        unique = []
        used = []

        for c in closures:
            dup = False
            for u_start, u_end in used:
                overlap = min(c.end_index, u_end) - max(c.start_index, u_start)
                if overlap > 0 and overlap / (c.end_index - c.start_index) > 0.8:
                    dup = True
                    break

            if not dup:
                unique.append(c)
                used.append((c.start_index, c.end_index))

        return unique
