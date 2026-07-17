import html
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import joinedload

from config import settings
from database import SessionLocal
from models import Territory, User
from services.og_image import generate_og_png

logger = logging.getLogger("velo_io")
router = APIRouter(tags=["og"])

_OG_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{description}" />
<meta property="og:image" content="{image_url}" />
<meta property="og:image:secure_url" content="{image_url}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:type" content="image/png" />
<meta property="og:type" content="website" />
<meta property="og:url" content="{page_url}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{title}" />
<meta name="twitter:description" content="{description}" />
<meta name="twitter:image" content="{image_url}" />
<title>{title}</title>
</head>
<body style="background:#0a0a1a;color:#fff;font-family:sans-serif;text-align:center;padding:60px 20px;">
  <img src="{image_url}" alt="{title}" style="max-width:100%;border-radius:12px;margin-bottom:20px;" />
  <p><a href="{redirect_url}" style="color:#4CAF50;font-size:20px;text-decoration:none;">\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0432 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0438 \u2192</a></p>
  <script>location.href="{redirect_url}"</script>
</body>
</html>"""


@router.get("/api/og/territory/{territory_id}.png")
def og_image(territory_id: str):
    db = SessionLocal()
    try:
        t = (
            db.query(Territory)
            .options(joinedload(Territory.user))
            .filter(Territory.id == territory_id)
            .first()
        )
        if not t:
            raise HTTPException(404, "Territory not found")

        polygon = mapping(to_shape(t.polygon))
        username = t.user.username if t.user else "Unknown"
        png_bytes = generate_og_png(polygon, t.name, t.area, username)
        return Response(content=png_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("OG image error for %s: %s", territory_id, e)
        raise HTTPException(500, "Failed to generate image")
    finally:
        db.close()


@router.get("/og/{territory_id}")
def og_page(request: Request, territory_id: str):
    db = SessionLocal()
    try:
        t = (
            db.query(Territory)
            .options(joinedload(Territory.user))
            .filter(Territory.id == territory_id)
            .first()
        )
        if not t:
            raise HTTPException(404, "Territory not found")

        area_km2 = t.area / 1_000_000
        area_str = f"{area_km2:.2f} km\u00b2" if area_km2 >= 1 else f"{t.area:.0f} m\u00b2"
        username_raw = t.user.username if t.user else "Unknown"
        base_url_raw = str(request.base_url)
        fr_url_raw = settings.FRONTEND_URL or "https://vel-io-y8k7.onrender.com"

        username = html.escape(username_raw, quote=False)
        base_url = base_url_raw.rstrip("/")
        image_url = f"{base_url}/api/og/territory/{territory_id}.png"
        redirect_url = f"{fr_url_raw.rstrip('/')}/public.html?t={territory_id}"
        page_url = f"{base_url}/og/{territory_id}"
        safe_name = html.escape(t.name or "Territory", quote=False)
        title = f"{safe_name} — {area_str}"
        desc = f"Territory of @{username} at vel.io"
        page_html = _OG_HTML.format(
            title=title,
            description=desc,
            image_url=image_url,
            page_url=page_url,
            redirect_url=redirect_url,
        )
        return HTMLResponse(content=page_html)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OG page error for %s", territory_id)
        raise HTTPException(500, "Failed to generate page")
    finally:
        db.close()
