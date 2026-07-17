import math
from loop_detector import GPSClosureDetector, ClosurePoint


class TestFindAllClosures:
    def test_closed_loop(self, load_gpx):
        content = load_gpx("big_square.gpx")
        from gpx_parser import parse_gpx
        points = parse_gpx(content)
        detector = GPSClosureDetector(closure_threshold=10.0)
        closures = detector.find_all_closures(points)
        assert len(closures) >= 1
        assert closures[0].distance_meters <= 10.0

    def test_open_route(self, load_gpx):
        content = load_gpx("open_route.gpx")
        from gpx_parser import parse_gpx
        points = parse_gpx(content)
        detector = GPSClosureDetector(closure_threshold=10.0)
        closures = detector.find_all_closures(points)
        assert len(closures) == 0

    def test_figure_eight(self, load_gpx):
        content = load_gpx("figure_eight.gpx")
        from gpx_parser import parse_gpx
        points = parse_gpx(content)
        detector = GPSClosureDetector(closure_threshold=10.0)
        closures = detector.find_all_closures(points)
        assert len(closures) >= 1

    def test_too_few_points(self):
        detector = GPSClosureDetector()
        points = [(55.75, 37.62, 100), (55.76, 37.63, 100), (55.77, 37.64, 100)]
        closures = detector.find_all_closures(points)
        assert closures == []

    def test_exactly_min_points(self):
        """5 points forming a closed loop should be detected."""
        detector = GPSClosureDetector(closure_threshold=15.0)
        # Small closed square (end near start)
        points = [
            (55.750, 37.620, 100),
            (55.750, 37.625, 100),
            (55.755, 37.625, 100),
            (55.755, 37.620, 100),
            (55.750, 37.620, 100),  # close to first point
        ]
        closures = detector.find_all_closures(points)
        assert len(closures) >= 1


class TestIsValidClosure:
    def test_degenerate_line(self):
        """All points on same longitude should be rejected."""
        detector = GPSClosureDetector()
        points = [(55.75 + i * 0.001, 37.62, 100) for i in range(10)]
        assert detector._is_valid_closure(points, 0, len(points) - 1) is False

    def test_degenerate_vertical(self):
        """All points on same latitude should be rejected."""
        detector = GPSClosureDetector()
        points = [(55.75, 37.62 + i * 0.001, 100) for i in range(10)]
        assert detector._is_valid_closure(points, 0, len(points) - 1) is False

    def test_valid_square(self):
        detector = GPSClosureDetector()
        points = [
            (55.750, 37.620, 100),
            (55.750, 37.625, 100),
            (55.755, 37.625, 100),
            (55.755, 37.620, 100),
            (55.750, 37.620, 100),
        ]
        assert detector._is_valid_closure(points, 0, len(points) - 1) is True

    def test_high_aspect_ratio_rejected(self):
        """Very thin elongated shapes should be rejected."""
        detector = GPSClosureDetector()
        points = [
            (55.750, 37.620, 100),
            (55.750, 37.621, 100),  # very narrow in longitude
            (55.800, 37.621, 100),  # wide in latitude
            (55.800, 37.620, 100),
            (55.750, 37.620, 100),
        ]
        # aspect ratio = lat_range/lon_range ~ 16:1 > 15:1
        assert detector._is_valid_closure(points, 0, len(points) - 1) is False


class TestDeduplicate:
    def test_no_duplicates(self):
        detector = GPSClosureDetector()
        c1 = ClosurePoint(start_index=0, end_index=10, distance_meters=5.0)
        c2 = ClosurePoint(start_index=20, end_index=30, distance_meters=3.0)
        result = detector._deduplicate([c1, c2])
        assert len(result) == 2

    def test_overlapping_removed(self):
        """Closures with >80% overlap should be deduplicated."""
        detector = GPSClosureDetector()
        # c2 overlaps c1 almost entirely (indices 5-95 vs 0-100)
        c1 = ClosurePoint(start_index=0, end_index=100, distance_meters=5.0)
        c2 = ClosurePoint(start_index=5, end_index=95, distance_meters=4.0)
        result = detector._deduplicate([c1, c2])
        # Only the larger one should survive
        assert len(result) == 1
        assert result[0].start_index == 0

    def test_single_closure(self):
        detector = GPSClosureDetector()
        c = ClosurePoint(start_index=0, end_index=10, distance_meters=5.0)
        assert detector._deduplicate([c]) == [c]


class TestFastDistance:
    def test_zero_distance(self):
        detector = GPSClosureDetector()
        assert detector._fast_distance(55.75, 37.62, 55.75, 37.62) == 0.0

    def test_approximates_haversine(self):
        """Fast distance should be within 5% of haversine for city-scale distances."""
        from gpx_parser import _haversine
        detector = GPSClosureDetector()
        fast = detector._fast_distance(55.75, 37.62, 55.80, 37.70)
        hav = _haversine(55.75, 37.62, 55.80, 37.70)
        assert abs(fast - hav) / hav < 0.05

    def test_symmetric(self):
        detector = GPSClosureDetector()
        d1 = detector._fast_distance(55.75, 37.62, 55.80, 37.70)
        d2 = detector._fast_distance(55.80, 37.70, 55.75, 37.62)
        assert abs(d1 - d2) < 1.0
