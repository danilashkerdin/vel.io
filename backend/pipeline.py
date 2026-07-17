from shapely.geometry import MultiPolygon
from shapely.ops import transform
import pyproj
from typing import List, Tuple
from gpx_parser import parse_gpx, validate_gpx
from loop_detector import GPSClosureDetector
from merger import SimpleClosureMerger


class TerritoryPipeline:
    """Полный пайплайн: GPX → замыкания → объединение → результат."""

    def __init__(self):
        self.detector = GPSClosureDetector(closure_threshold=10.0)
        self.merger = SimpleClosureMerger(closure_threshold=10.0)

    def process_raw_points(self, points: List[Tuple[float, float, float]]) -> dict:
        """Обрабатывает список точек (lat, lng, ele) без GPX."""
        if len(points) < 5:
            return {"success": False, "error": "too_few_points"}

        closures = self.detector.find_all_closures(points)

        if not closures:
            return {"success": False, "error": "no_closures"}

        loops = [points[c.start_index:c.end_index + 1] for c in closures]
        merged = self.merger.merge(loops)

        if not merged:
            return {"success": False, "error": "merge_failed"}

        area = self._area(merged)

        if merged.geom_type == "MultiPolygon":
            parts = len(merged.geoms)
        else:
            parts = 1

        return {
            "success": True,
            "geometry": merged,
            "area_sqm": area,
            "closures_found": len(closures),
            "parts_count": parts,
        }

    def process_gpx_string(self, gpx_content: str) -> dict:
        validation_error = validate_gpx(gpx_content)
        if validation_error:
            return {"success": False, "error": "validation", "detail": validation_error}

        points = parse_gpx(gpx_content)

        return self.process_raw_points(points)

        if not closures:
            return {"success": False, "error": "no_closures"}

        loops = [points[c.start_index:c.end_index + 1] for c in closures]
        merged = self.merger.merge(loops)

        if not merged:
            return {"success": False, "error": "merge_failed"}

        area = self._area(merged)

        if merged.geom_type == "MultiPolygon":
            parts = len(merged.geoms)
        else:
            parts = 1

        return {
            "success": True,
            "geometry": merged,
            "area_sqm": area,
            "closures_found": len(closures),
            "parts_count": parts,
        }

    def _area(self, geometry) -> float:
        # Берём центр геометрии для точной проекции
        centroid = geometry.centroid
        lon, lat = centroid.x, centroid.y

        # UTM зона для этой долготы
        utm_zone = int((lon + 180) / 6) + 1
        proj_str = f"+proj=utm +zone={utm_zone} +datum=WGS84 +units=m +no_defs"

        transformer = pyproj.Transformer.from_crs("EPSG:4326", proj_str, always_xy=True)
        projected = transform(transformer.transform, geometry)
        return projected.area
