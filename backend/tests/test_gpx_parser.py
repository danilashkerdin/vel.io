import math
from gpx_parser import parse_gpx, validate_gpx, _simplify, _haversine


class TestParseGpx:
    def test_basic_track(self, load_gpx):
        content = load_gpx("big_square.gpx")
        points = parse_gpx(content)
        assert len(points) > 0
        # Every point is (lat, lon, ele)
        for p in points:
            assert len(p) == 3
            assert isinstance(p[0], float)
            assert isinstance(p[1], float)

    def test_empty_gpx(self):
        points = parse_gpx("<gpx></gpx>")
        assert points == []

    def test_route_points(self):
        gpx = """<?xml version="1.0"?>
        <gpx>
            <rte>
                <rtept lat="55.75" lon="37.62"><ele>100</ele></rtept>
                <rtept lat="55.76" lon="37.63"><ele>101</ele></rtept>
            </rte>
        </gpx>"""
        points = parse_gpx(gpx)
        assert len(points) == 2
        assert points[0] == (55.75, 37.62, 100.0)

    def test_waypoint_fallback(self):
        gpx = """<?xml version="1.0"?>
        <gpx>
            <wpt lat="55.75" lon="37.62"><ele>100</ele></wpt>
            <wpt lat="55.76" lon="37.63"><ele>101</ele></wpt>
        </gpx>"""
        points = parse_gpx(gpx)
        assert len(points) == 2

    def test_simplification_triggered(self):
        """Tracks with >1000 points should be simplified."""
        # Build a GPX with 1100 closely-spaced points
        points_xml = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.000001}"><ele>100</ele></trkpt>'
            for i in range(1100)
        )
        gpx = f"""<?xml version="1.0"?>
        <gpx><trk><trkseg>{points_xml}</trkseg></trk></gpx>"""
        result = parse_gpx(gpx)
        # Simplified should have fewer than 1100 points
        assert len(result) < 1100
        assert len(result) >= 2

    def test_elevation_default_zero(self):
        gpx = """<?xml version="1.0"?>
        <gpx><trk><trkseg>
            <trkpt lat="55.75" lon="37.62"></trkpt>
        </trkseg></trk></gpx>"""
        points = parse_gpx(gpx)
        assert points[0][2] == 0


class TestSimplify:
    def test_reduces_close_points(self):
        # 10 points all within 1m of each other
        points = [(55.75, 37.62 + i * 0.000001, 100) for i in range(10)]
        result = _simplify(points, min_distance_m=5)
        # Only first point should remain (rest are too close)
        assert len(result) < len(points)
        assert result[0] == points[0]

    def test_keeps_far_points(self):
        # Points ~111m apart in longitude
        points = [(55.75, 37.62 + i * 0.001, 100) for i in range(5)]
        result = _simplify(points, min_distance_m=5)
        assert len(result) == len(points)

    def test_empty_input(self):
        assert _simplify([], min_distance_m=5) == []

    def test_single_point(self):
        assert _simplify([(55.75, 37.62, 100)], min_distance_m=5) == [(55.75, 37.62, 100)]

    def test_two_close_points(self):
        points = [(55.75, 37.62, 100), (55.75, 37.620001, 100)]
        result = _simplify(points, min_distance_m=5)
        assert len(result) == 1


class TestHaversine:
    def test_zero_distance(self):
        assert _haversine(55.75, 37.62, 55.75, 37.62) == 0.0

    def test_known_distance(self):
        # 1 degree of latitude ≈ 111,320 meters
        dist = _haversine(55.75, 37.62, 56.75, 37.62)
        assert abs(dist - 111320) < 1000  # within 1km

    def test_symmetric(self):
        assert _haversine(55.75, 37.62, 55.80, 37.70) == _haversine(55.80, 37.70, 55.75, 37.62)


def _make_gpx(n: int, **kwargs) -> str:
    """Helper: build GPX with n trkpt points.
    gap_s can be int (fixed interval) or a callable (i) -> seconds.
    """
    from datetime import datetime, timezone, timedelta

    base_lat = kwargs.get("lat", 55.75)
    base_lon = kwargs.get("lon", 37.62)
    fmt_lat = kwargs.get("fmt_lat", lambda i: f"{base_lat + i * 0.000001}")
    fmt_lon = kwargs.get("fmt_lon", lambda i: f"{base_lon + i * 0.000001}")
    ele = kwargs.get("ele", 100)
    gap_s = kwargs.get("gap_s", 1)
    t0_str = kwargs.get("t0", "2026-07-10T10:00:00Z")
    t0 = datetime.fromisoformat(t0_str.replace("Z", "+00:00"))

    pts = []
    for i in range(n):
        sec = gap_s(i) if callable(gap_s) else i * gap_s
        t = (t0 + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(
            f'<trkpt lat="{fmt_lat(i)}" lon="{fmt_lon(i)}">'
            f'<ele>{ele}</ele>'
            f'<time>{t}</time>'
            f'</trkpt>'
        )
    pts_xml = "\n".join(pts)
    return f"""<?xml version="1.0"?>
<gpx><trk><trkseg>{pts_xml}</trkseg></trk></gpx>"""


class TestValidateGpx:
    def test_valid_gpx_passes(self):
        gpx = _make_gpx(20, gap_s=lambda i: 1 if i == 0 else 1 + (i % 3) * 0.1)
        assert validate_gpx(gpx) is None

    def test_too_few_points(self):
        gpx = _make_gpx(3)
        assert "мало" in validate_gpx(gpx)

    def test_missing_track(self):
        pts = "\n".join(
            f'<wpt lat="55.7{i}" lon="37.6{i}"><ele>100</ele></wpt>'
            for i in range(5)
        )
        gpx = f"""<?xml version="1.0"?><gpx>{pts}</gpx>"""
        result = validate_gpx(gpx)
        assert result is not None
        assert "трек" in result or "маршрут" in result

    def test_route_only_passes(self):
        """GPX только с rte (без trk, без wpt) — должно проходить."""
        pts = "\n".join(
            f'<rtept lat="55.7{i}" lon="37.6{i}"><ele>100</ele></rtept>'
            for i in range(10)
        )
        gpx = f"""<?xml version="1.0"?><gpx><rte>{pts}</rte></gpx>"""
        assert validate_gpx(gpx) is None

    def test_invalid_coordinates(self):
        pts = "\n".join(
            f'<trkpt lat="95.0" lon="37.62"><ele>100</ele><time>2026-07-10T10:00:{i:02d}Z</time></trkpt>'
            for i in range(5)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        assert "невалидные" in validate_gpx(gpx)

    def test_missing_timestamps(self):
        pts = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.001}"><ele>100</ele></trkpt>'
            for i in range(15)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        assert "временных меток" in validate_gpx(gpx)

    def test_uniform_intervals_detected(self):
        # 3s uniform intervals should be flagged (1s is legitimate 1Hz GPS)
        gpx = _make_gpx(15, gap_s=3)
        assert "равномерные интервалы" in validate_gpx(gpx)

    def test_variable_intervals_pass(self):
        gpx = _make_gpx(15, gap_s=lambda i: 1 + (0.5 if i % 2 else 0))
        assert validate_gpx(gpx) is None

    def test_too_many_duplicates(self):
        gaps = [1, 3, 2, 5, 7, 2, 4, 1, 6, 3, 2, 5, 1, 4, 3, 7, 2, 1, 5]
        t = 10
        pts = ""
        for gap in gaps:
            pts += f'<trkpt lat="55.75" lon="37.62"><ele>100</ele><time>2026-07-10T10:00:{t:02d}Z</time></trkpt>'
            t += gap
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        assert "повторяющихся" in validate_gpx(gpx)

    def test_high_speed_detected(self):
        gen_lat = lambda i: f"{55.75 + i * 0.01:.15f}"  # ~1km apart per second
        gen_lon = lambda i: f"{37.62 + i * 0.01:.15f}"
        gpx = _make_gpx(5, fmt_lat=gen_lat, fmt_lon=gen_lon, gap_s=1)
        result = validate_gpx(gpx)
        assert result is not None
        assert "Скорость" in result

    def test_precision_check_catches_uniform(self):
        """Uniform 15-decimal precision with irregular intervals should be flagged."""
        gaps = [1, 3, 1, 5, 2, 4, 1, 6, 3, 2, 5, 1, 4, 2]
        t = 10
        pts = ""
        for i, gap in enumerate(gaps):
            lat = 55.75 + i * 0.000001
            lon = 37.62 + i * 0.000001
            pts += f'<trkpt lat=\"{lat:.15f}\" lon=\"{lon:.15f}\"><ele>100</ele><time>2026-07-10T10:00:{t:02d}Z</time></trkpt>'
            t += gap
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        assert "сгенерированным" in validate_gpx(gpx)

    def test_precision_check_passes_variable(self):
        """Realistic varying precision should pass."""
        gen = lambda i: f"{55.75 + i * 0.000001}"  # natural float repr
        gpx = _make_gpx(15, fmt_lat=gen, fmt_lon=gen, gap_s=lambda i: 1 + (i % 3) * 0.1)
        assert validate_gpx(gpx) is None

    def test_real_mi_fitness_passes(self, load_gpx):
        content = load_gpx("mi_fitness.gpx")
        assert validate_gpx(content) is None

    def test_real_koros_passes(self, load_gpx):
        content = load_gpx("koros.gpx")
        assert validate_gpx(content) is None

    def test_real_suunto_route_passes(self, load_gpx):
        """Route-only GPX без таймстемпов должен проходить."""
        content = load_gpx("suunto_route.gpx")
        assert validate_gpx(content) is None

    def test_real_suunto_track_rejected(self, load_gpx):
        """Suunto track со средней скоростью 100км/ч — не велосипед."""
        content = load_gpx("suunto_track.gpx")
        result = validate_gpx(content)
        assert result is not None
        assert "Скорость" in result

    def test_bad_elevation_diff(self):
        pts = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.000001}"><ele>{100 if i == 0 else 400}</ele>'
            f'<time>2026-07-10T10:00:{i * 10:02d}Z</time></trkpt>'
            for i in range(5)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        assert "Нереалистичный" in validate_gpx(gpx)

    def test_bad_elevation_max(self):
        pts = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.001}"><ele>{7000}</ele>'
            f'<time>2026-07-10T10:00:{i:02d}Z</time></trkpt>'
            for i in range(5)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        assert "превышает" in validate_gpx(gpx) or "6000" in validate_gpx(gpx)

    def test_bad_elevation_range(self):
        base = 100
        pts = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.001}"><ele>{base if i == 0 else 6000}</ele>'
            f'<time>2026-07-10T10:00:{i:02d}Z</time></trkpt>'
            for i in range(2)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        result = validate_gpx(gpx)
        assert result is not None

    def test_invalid_xml(self):
        assert "распарсить" in validate_gpx("not xml at all")

    def test_elevation_beyond_max(self):
        pts = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.0005}"><ele>{100 if i == 0 else 6400}</ele>'
            f'<time>2026-07-10T10:00:{i*20:02d}Z</time></trkpt>'
            for i in range(6)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk></gpx>"""
        result = validate_gpx(gpx)
        assert result is not None
        assert "Нереалистичный перепад" in result

    def test_mixed_track_and_route(self):
        pts = "\n".join(
            f'<trkpt lat="55.75" lon="{37.62 + i * 0.0005}">'
            f'<time>2026-07-10T10:00:{i*20:02d}Z</time></trkpt>'
            for i in range(6)
        )
        gpx = f"""<?xml version="1.0"?><gpx><trk><trkseg>{pts}</trkseg></trk><rte><rtept lat="55.70" lon="37.50"/></rte></gpx>"""
        result = validate_gpx(gpx)
        assert result is None

    def test_empty_content(self):
        result = validate_gpx("")
        assert result is not None

    def test_whitespace_only(self):
        result = validate_gpx("   \n\n  ")
        assert result is not None
