import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from config import settings
from database import engine, init_db, SessionLocal
from limiter import limiter
from routers import auth_router, territory_router, notification_router, payment_router, admin_router, telegram_router, og_router, advertiser_router

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("velo_io")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Velo.io backend…")
    init_db()
    logger.info("Database tables ensured")
    yield
    logger.info("Shutting down Velo.io backend")


app = FastAPI(title="Velo.io", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

# CORS: FRONTEND_URL + CORS_ORIGINS + fallback
_cors_origins = settings.cors_origins_list

for origin in [settings.FRONTEND_URL, "capacitor://localhost", "http://localhost", "https://velio.app"]:
    if origin not in _cors_origins:
        _cors_origins.append(origin)
logger.info("CORS origins: %s", _cors_origins)
# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception("Unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)},
        )
    duration = time.time() - start
    logger.info(
        "%s %s → %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration * 1000,
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router.router)
app.include_router(territory_router.router)
app.include_router(notification_router.router)
app.include_router(payment_router.router)
app.include_router(admin_router.router)
app.include_router(telegram_router.router)
app.include_router(og_router.router)
app.include_router(advertiser_router.router)


@app.get("/api/health")
def health_check():
    """Health check endpoint — verifies DB connectivity."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        logger.error("Health check DB failure: %s", e)
        db_status = "error"
    finally:
        db.close()
    return JSONResponse(
        status_code=200 if db_status == "ok" else 503,
        content={"status": db_status, "service": "velo_io"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
