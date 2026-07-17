from shapely.geometry import Polygon, MultiPolygon
from merger import SimpleClosureMerger


class TestMerge:
    def setup_method(self):
        self.merger = SimpleClosureMerger()

    def test_single_loop(self):
        loop = [
            (55.750, 37.620, 100),
            (55.750, 37.630, 100),
            (55.760, 37.630, 100),
            (55.760, 37.620, 100),
            (55.750, 37.620, 100),
        ]
        result = self.merger.merge([loop])
        assert result is not None
        assert isinstance(result, Polygon)
        assert result.area > 0

    def test_two_overlapping_loops(self):
        loop1 = [
            (55.750, 37.620, 100),
            (55.750, 37.630, 100),
            (55.760, 37.630, 100),
            (55.760, 37.620, 100),
            (55.750, 37.620, 100),
        ]
        # Overlapping square shifted slightly
        loop2 = [
            (55.755, 37.625, 100),
            (55.755, 37.635, 100),
            (55.765, 37.635, 100),
            (55.765, 37.625, 100),
            (55.755, 37.625, 100),
        ]
        result = self.merger.merge([loop1, loop2])
        assert result is not None
        # Union area should be less than sum of both
        area1 = Polygon([(37.62, 55.75), (37.63, 55.75), (37.63, 55.76), (37.62, 55.76)]).area
        assert result.area < area1 * 2

    def test_two_disjoint_loops(self):
        loop1 = [
            (55.750, 37.620, 100),
            (55.750, 37.630, 100),
            (55.760, 37.630, 100),
            (55.760, 37.620, 100),
            (55.750, 37.620, 100),
        ]
        # Far away square
        loop2 = [
            (55.850, 37.820, 100),
            (55.850, 37.830, 100),
            (55.860, 37.830, 100),
            (55.860, 37.820, 100),
            (55.850, 37.820, 100),
        ]
        result = self.merger.merge([loop1, loop2])
        assert result is not None
        assert isinstance(result, MultiPolygon)
        assert len(result.geoms) == 2

    def test_empty_input(self):
        result = self.merger.merge([])
        assert result is None

    def test_invalid_loops_only(self):
        """Loops with <3 points should produce None."""
        result = self.merger.merge([[(55.75, 37.62, 100), (55.76, 37.63, 100)]])
        assert result is None


class TestMakePolygon:
    def setup_method(self):
        self.merger = SimpleClosureMerger()

    def test_too_few_points(self):
        result = self.merger._make_polygon([(55.75, 37.62, 100), (55.76, 37.63, 100)])
        assert result is None

    def test_closed_ring(self):
        """Open ring should be auto-closed."""
        points = [
            (55.750, 37.620, 100),
            (55.750, 37.630, 100),
            (55.760, 37.630, 100),
            (55.760, 37.620, 100),
            # Not closed (first != last)
        ]
        result = self.merger._make_polygon(points)
        assert result is not None
        assert isinstance(result, Polygon)

    def test_self_intersecting_fixed(self):
        """Bowtie polygon should be fixed by buffer(0)."""
        # Bowtie: self-intersecting quadrilateral
        points = [
            (0.0, 0.0, 0),
            (0.0, 1.0, 0),
            (1.0, 0.0, 0),
            (1.0, 1.0, 0),
            (0.0, 0.0, 0),
        ]
        result = self.merger._make_polygon(points)
        assert result is not None
        assert result.is_valid

    def test_lat_lon_swap(self):
        """Merger should swap lat/lon for GeoJSON convention (lon, lat)."""
        points = [
            (55.0, 37.0, 0),
            (55.0, 38.0, 0),
            (56.0, 38.0, 0),
            (56.0, 37.0, 0),
            (55.0, 37.0, 0),
        ]
        result = self.merger._make_polygon(points)
        assert result is not None
        # Shapely Polygon coords are (x, y) = (lon, lat)
        exterior = list(result.exterior.coords)
        assert exterior[0][0] == 37.0  # lon
        assert exterior[0][1] == 55.0  # lat
