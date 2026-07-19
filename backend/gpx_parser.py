import gpxpy
import re
from typing import List, Tuple, Optional
import math
from datetime import datetime, timezone


def parse_gpx(content: str) -> List[Tuple[float, float, float]]:
    """Парсит GPX и возвращает список точек (lat, lon, ele)."""
    gpx = gpxpy.parse(content)
    points = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append((
                    point.latitude,
                    point.longitude,
                    point.elevation if point.elevation else 0
                ))

    if not points:
        for route in gpx.routes:
            for point in route.points:
                points.append((
                    point.latitude,
                    point.longitude,
                    point.elevation if point.elevation else 0
                ))

    if not points:
        for wp in gpx.waypoints:
            points.append((
                wp.latitude,
                wp.longitude,
                wp.elevation if wp.elevation else 0
            ))

    if len(points) > 1000:
        points = _simplify(points, min_distance_m=5)

    return points


def validate_gpx(content: str) -> Optional[str]:
    """Проверяет GPX-файл на признаки фальсификации.
    Возвращает строку с ошибкой или None если всё ок."""
    try:
        gpx = gpxpy.parse(content)
    except Exception:
        return "Не удалось распарсить GPX"

    all_points = []
    for track in gpx.tracks:
        for segment in track.segments:
            all_points.extend(segment.points)

    if not all_points:
        for route in gpx.routes:
            all_points.extend(route.points)

    if not all_points and gpx.waypoints:
        for wp in gpx.waypoints:
            all_points.append(wp)

    if len(all_points) < 5:
        return "Слишком мало точек"

    # Проверка, что точки из трека или маршрута, а не только waypoints
    has_track_points = any(
        seg.points for track in gpx.tracks for seg in track.segments
    )
    has_route_points = bool(gpx.routes)
    if not has_track_points and not has_route_points and gpx.waypoints:
        return "Файл должен содержать трек (trk) или маршрут (rte), а не только waypoints"

    # Проверка координат на валидность
    for p in all_points:
        if not (-90 <= p.latitude <= 90) or not (-180 <= p.longitude <= 180):
            return "Обнаружены невалидные координаты"

    # Проверка, что есть временные метки (не требуется для маршрутов)
    has_route_points = bool(gpx.routes)
    if len(all_points) > 10 and not has_route_points:
        timed_count = sum(1 for p in all_points if p.time)
        if timed_count < 2:
            return "Файл не содержит временных меток. Загрузите GPX с велокомпьютера или приложения"

    # Собираем точки с временными метками для проверки скорости
    timed_points = [p for p in all_points if p.time]

    # Проверка равномерных интервалов (боты)
    # Исключаем паузы (>3× медиана) — GPS-часы (COROS, Garmin) пишут строго 1Гц
    if len(timed_points) >= 10:
        intervals = []
        for i in range(1, len(timed_points)):
            dt = (timed_points[i].time - timed_points[i - 1].time).total_seconds()
            if 0 < dt < 3600:
                intervals.append(dt)
        if intervals:
            sorted_ints = sorted(intervals)
            median = sorted_ints[len(sorted_ints) // 2]
            if median > 0:
                riding = [i for i in intervals if i <= median * 3]
                if len(riding) >= 5:
                    avg = sum(riding) / len(riding)
                    max_dev = max(abs(i - avg) for i in riding)
                    if max_dev / avg < 0.001 and abs(avg - 1.0) > 0.01:
                        return "Файл выглядит сгенерированным (равномерные интервалы)"

    # Проверка дублирующихся точек (одинаковые lat/lon подряд)
    if len(all_points) >= 10:
        duplicates = 0
        for i in range(1, len(all_points)):
            p1, p2 = all_points[i - 1], all_points[i]
            if p1.latitude == p2.latitude and p1.longitude == p2.longitude:
                duplicates += 1
        if duplicates / len(all_points) > 0.05:
            return "Слишком много повторяющихся точек подряд"

    # Проверка скорости и ускорения (только если есть time)
    if len(timed_points) >= 2:
        total_dist = 0.0
        total_time = (timed_points[-1].time - timed_points[0].time).total_seconds()

        speeds: list[float] = []
        seg_dists: list[float] = []
        for i in range(1, len(timed_points)):
            p1, p2 = timed_points[i - 1], timed_points[i]
            dt = (p2.time - p1.time).total_seconds()
            dist = _haversine(p1.latitude, p1.longitude, p2.latitude, p2.longitude)

            if dt > 0:
                cur_speed = dist / dt

                if i >= 2:
                    prev_speed = seg_dists[-1] / max((timed_points[i-1].time - timed_points[i-2].time).total_seconds(), 0.001)
                    accel = abs(cur_speed - prev_speed) / dt
                    if accel > 15 and dist > prev_speed * 3:
                        continue

            seg_dists.append(dist)
            total_dist += dist
            if dt > 0:
                speed_kmh = (dist / 1000) / (dt / 3600)
                if speed_kmh > 0:
                    speeds.append(speed_kmh)

        if speeds:
            max_speed = max(speeds)
            if max_speed > 80:
                return f"Скорость {max_speed:.0f} км/ч превышает лимит 80 км/ч"

            if len(speeds) >= 5 and total_dist > 1000:
                sorted_speeds = sorted(speeds)
                middle = sorted_speeds[len(sorted_speeds)//4: -len(sorted_speeds)//4]
                if middle:
                    avg_speed = sum(middle) / len(middle)
                    if avg_speed > 55:
                        return f"Средняя скорость {avg_speed:.0f} км/ч слишком высока для велосипеда"

            if total_dist > 1000 and total_time > 0:
                overall_avg = (total_dist / 1000) / (total_time / 3600)
                if overall_avg > 55:
                    return f"Общая средняя скорость {overall_avg:.0f} км/ч слишком высока для велосипеда"

        # Проверка ускорения (используем кешированные seg_dists)
        if len(timed_points) >= 10:
            spike_count = 0
            for i in range(2, len(timed_points)):
                dt0 = (timed_points[i-1].time - timed_points[i-2].time).total_seconds()
                dt1 = (timed_points[i].time - timed_points[i-1].time).total_seconds()
                if dt0 <= 0 or dt1 <= 0 or dt0 > 30 or dt1 > 30:
                    spike_count = 0
                    continue
                v0 = seg_dists[i-2] / dt0
                v1 = seg_dists[i-1] / dt1
                accel = abs(v1 - v0) / ((dt0 + dt1) / 2)
                if accel > 15:
                    spike_count += 1
                    if spike_count >= 3:
                        return "Обнаружено резкое ускорение/торможение, невозможное на велосипеде"
                else:
                    spike_count = 0

    # Проверка координат на излишнюю точность (синтетика)
    if len(all_points) >= 10:
        coord_precisions = set()
        checked = 0
        for match in re.finditer(r'(?:lat|lon)="([^"]+)"', content):
            val = match.group(1)
            checked += 1
            if '.' in val:
                coord_precisions.add(len(val.split('.')[1]))
            else:
                coord_precisions.add(0)
            if len(coord_precisions) > 1:
                break
            if checked >= 100:
                break
        if len(coord_precisions) == 1:
            precision = list(coord_precisions)[0]
            if precision >= 10:
                return "Файл выглядит сгенерированным (координаты подозрительно ровные)"

    # Проверка перепадов высоты
    elevations = [p.elevation for p in all_points if p.elevation is not None]
    if len(elevations) >= 5:
        for i in range(1, len(elevations)):
            diff = abs(elevations[i] - elevations[i - 1])
            if diff > 200:
                return f"Нереалистичный перепад высоты между соседними точками: {diff:.0f}м"

        # Абсолютный максимум высоты
        max_ele = max(elevations)
        if max_ele > 6000:
            return f"Высота {max_ele:.0f}м превышает максимальную для велосипеда"

        # Диапазон высот за одну поездку
        ele_range = max(elevations) - min(elevations)
        if ele_range > 5500:
            return f"Перепад высот {ele_range:.0f}м за одну поездку нереалистичен"

    return None


def _haversine(lat1, lon1, lat2, lon2):
    """Расстояние между точками в метрах."""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _simplify(
    points: List[Tuple[float, float, float]],
    min_distance_m: float = 5
) -> List[Tuple[float, float, float]]:
    """Оставляет точки не ближе min_distance_m метров друг к другу."""
    if len(points) < 2:
        return points

    simplified = [points[0]]

    for p in points[1:]:
        last = simplified[-1]
        if _haversine(last[0], last[1], p[0], p[1]) >= min_distance_m:
            simplified.append(p)

    return simplified
