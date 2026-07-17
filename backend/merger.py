from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from typing import List, Tuple, Optional


class SimpleClosureMerger:
    """Объединяет контуры через логическое ИЛИ."""

    def __init__(self, closure_threshold: float = 10.0):
        self.closure_threshold = closure_threshold

    def merge(
        self,
        loops: List[List[Tuple[float, float, float]]],
    ):
        if not loops:
            return None

        polygons = []
        for loop in loops:
            poly = self._make_polygon(loop)
            if poly:
                polygons.append(poly)

        if not polygons:
            return None

        result = unary_union(polygons)
        return result if not result.is_empty else None

    def _make_polygon(self, points: List[Tuple[float, float, float]]) -> Optional[Polygon]:
        if len(points) < 3:
            return None

        coords = [(p[1], p[0]) for p in points]
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)

        return poly if poly.is_valid and not poly.is_empty else None