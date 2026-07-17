import io
import logging
import os

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("velo_io")


def _get_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    logger.warning("No TrueType font found, using PIL default")
    return ImageFont.load_default()


def generate_og_png(
    polygon_geojson: dict,
    name: str,
    area_m2: float,
    username: str,
) -> bytes:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (10, 10, 26))
    draw = ImageDraw.Draw(img)

    coords = _extract_coords(polygon_geojson)
    if not coords:
        coords = [(37.618, 55.751), (37.62, 55.753), (37.622, 55.751)]

    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    lon_pad = max((max_lon - min_lon) * 0.15, 0.002)
    lat_pad = max((max_lat - min_lat) * 0.15, 0.002)
    min_lon -= lon_pad
    max_lon += lon_pad
    min_lat -= lat_pad
    max_lat += lat_pad

    def _to_px(lon: float, lat: float) -> tuple[float, float]:
        x = 120 + (lon - min_lon) / (max_lon - min_lon) * (W - 240)
        y = H - 100 - (lat - min_lat) / (max_lat - min_lat) * (H - 220)
        return x, y

    try:
        px_coords = [_to_px(lon, lat) for lon, lat in coords]
    except Exception:
        px_coords = [(W // 2, H // 2)]

    fill_color = (76, 175, 80)
    outline_color = (102, 255, 102)

    if len(px_coords) >= 3:
        draw.polygon(px_coords, fill=fill_color)
        for i in range(len(px_coords)):
            j = (i + 1) % len(px_coords)
            draw.line([px_coords[i], px_coords[j]], fill=outline_color, width=4)
    else:
        cx, cy = px_coords[0] if px_coords else (W // 2, H // 2)
        draw.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=fill_color, outline=outline_color, width=4)

    font_large = _get_font(44)
    font_medium = _get_font(28)
    font_small = _get_font(22)
    font_brand = _get_font(36)

    draw.text((40, 30), name[:50], fill=(255, 255, 255), font=font_large)

    area_km2 = area_m2 / 1_000_000
    area_str = f"{area_km2:.2f} км\u00b2" if area_km2 >= 1 else f"{area_m2:.0f} м\u00b2"
    draw.text((40, H - 80), area_str, fill=(170, 170, 170), font=font_medium)
    draw.text((40, H - 48), f"@{username}", fill=(76, 175, 80), font=font_small)
    draw.text((W - 120, 30), "vel.io", fill=(76, 175, 80), font=font_brand)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _extract_coords(geojson: dict) -> list:
    t = geojson.get("type", "")
    try:
        if t == "Polygon":
            return geojson["coordinates"][0]
        elif t == "MultiPolygon":
            return geojson["coordinates"][0][0]
        elif t == "Point":
            coords = geojson["coordinates"]
            return [
                (coords[0] - 0.002, coords[1] - 0.002),
                (coords[0] + 0.002, coords[1] - 0.002),
                (coords[0] + 0.002, coords[1] + 0.002),
                (coords[0] - 0.002, coords[1] + 0.002),
            ]
    except (KeyError, IndexError, TypeError) as e:
        logger.error("Failed to extract coords from %s: %s", t, e)
    return []
