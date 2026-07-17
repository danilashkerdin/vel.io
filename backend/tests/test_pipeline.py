from shapely.geometry import Polygon
from pipeline import TerritoryPipeline


class TestTerritoryPipeline:
    def setup_method(self):
        self.pipeline = TerritoryPipeline()

    def test_process_gpx_success(self, load_gpx):
        content = load_gpx("big_square.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["success"] is True
        assert result["area_sqm"] > 0
        assert result["closures_found"] >= 1
        assert result["geometry"] is not None

    def test_too_few_points(self):
        gpx = """<?xml version="1.0"?>
        <gpx><trk><trkseg>
            <trkpt lat="55.75" lon="37.62"><ele>100</ele></trkpt>
            <trkpt lat="55.76" lon="37.63"><ele>100</ele></trkpt>
        </trkseg></trk></gpx>"""
        result = self.pipeline.process_gpx_string(gpx)
        assert result["success"] is False
        assert result["error"] in ("too_few_points", "validation")

    def test_no_closures(self, load_gpx):
        content = load_gpx("open_route.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["success"] is False
        assert result["error"] == "no_closures"

    def test_figure_eight(self, load_gpx):
        content = load_gpx("figure_eight.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["success"] is True
        assert result["area_sqm"] > 0

    def test_area_reasonable(self, load_gpx):
        """Area of big_square.gpx should be reasonable (around 1 km²)."""
        content = load_gpx("big_square.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["success"] is True
        # big_square is ~0.01° x 0.015° at lat 55.7 → roughly 1.1 km²
        area_km2 = result["area_sqm"] / 1_000_000
        assert 0.1 < area_km2 < 10  # generous bounds

    def test_parts_count(self, load_gpx):
        content = load_gpx("big_square.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["parts_count"] >= 1

    def test_route_only_through_pipeline(self, load_gpx):
        """Route-only GPX (no timestamps, no trk/trkseg) should still succeed."""
        content = load_gpx("suunto_route.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["success"] is True
        assert result["area_sqm"] > 0

    def test_validation_error_propagated(self):
        """GPX that fails validation should return validation error."""
        gpx = """<?xml version="1.0"?>
        <gpx><trk><trkseg>
            <trkpt lat="55.75" lon="37.62"><time>2024-01-01T00:00:00Z</time></trkpt>
            <trkpt lat="55.76" lon="37.63"><time>2024-01-01T00:00:02Z</time></trkpt>
        </trkseg></trk></gpx>"""
        result = self.pipeline.process_gpx_string(gpx)
        assert result["success"] is False

    def test_real_koros_through_pipeline(self, load_gpx):
        content = load_gpx("koros.gpx")
        result = self.pipeline.process_gpx_string(content)
        assert result["success"] is True
        assert result["area_sqm"] > 0


class TestArea:
    def setup_method(self):
        self.pipeline = TerritoryPipeline()

    def test_known_area(self):
        """A 1km x 1km square should have area ≈ 1,000,000 m²."""
        # 1° lat ≈ 111,320m → 1km ≈ 0.00898°
        # At lat 55.75, 1° lon ≈ 111,320 * cos(55.75°) ≈ 62,700m → 1km ≈ 0.01594°
        square = Polygon([
            (37.62, 55.75),
            (37.62 + 0.01594, 55.75),
            (37.62 + 0.01594, 55.75 + 0.00898),
            (37.62, 55.75 + 0.00898),
            (37.62, 55.75),
        ])
        area = self.pipeline._area(square)
        area_km2 = area / 1_000_000
        assert 0.8 < area_km2 < 1.2  # within 20% tolerance
