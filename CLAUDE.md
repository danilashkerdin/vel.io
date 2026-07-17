# Velo.io — CLAUDE.md

## Project Overview
Territorial game for cyclists. Users upload GPX tracks, the system detects closed loops, converts them to territory polygons, and tracks ownership. Overlapping territories are subtracted so only unclaimed area is awarded.

## Monetization Model
- **Sponsored territories**: Admin creates advertiser zones on the map (monthly budget ~5000₽)
- **Revenue share**: User who captures territory overlapping a sponsored zone gets **10%** of budget
- **Platform takes 90%**, user gets 10%
- If territory is re-captured, new owner gets the revenue

### Payment providers
- **ЮKassa** (yookassa.ru) — accepts payments from RF + international cards. Primary payment gateway
- **USDT TRC-20** — global crypto payouts to users (user provides wallet → admin processes batch)

### Key models (besides core)
- `SponsoredTerritory` — advertiser zone with polygon, budget, owner
- `UserBalance` — user's earned balance
- `Transaction` — earnings and payout history
- `User.crypto_wallet` — USDT TRC-20 address
- `User.is_premium` — premium status
- `User.captures_count` — territory count (free limit = 1 per week)
- `VIP_EMAILS` in `.env` — белый список email'ов (премиум без оплаты)

### Admin panel
- `/admin.html` — map-based CRUD for sponsored territories, dashboard, payout management
- Login: `admin@vel.io` + password (any registered user with this email)
- Payouts tab: view pending crypto withdrawals, mark as completed after sending USDT

## Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, PostGIS, GeoAlchemy2, Shapely, PyProj
- **Frontend**: Vanilla JS (ES modules), Leaflet.js, CSS (no build step)
- **Infra**: Docker Compose (PostGIS 15 + backend + nginx), Alembic for migrations

## Architecture
```
backend/
  main.py              — FastAPI app, CORS, rate limiter, health check, request logging
  config.py            — pydantic-settings (DATABASE_URL, SECRET_KEY, CORS_ORIGINS, YOOKASSA_*)
  database.py          — SQLAlchemy engine, Base, get_db, init_db
  models.py            — User, Territory (PostGIS), Notification, SponsoredTerritory, UserBalance, Transaction
  auth.py              — PBKDF2 password hashing, JWT tokens, get_current_user
  pipeline.py          — GPX → closures → polygon → area
  gpx_parser.py        — GPX parsing with simplification
  loop_detector.py     — GPS closure detection (spatial grid, dedup)
  merger.py            — Polygon union via Shapely
  routers/
    auth_router.py         — register/login/me (returns premium fields)
    territory_router.py    — upload-gpx (checks free limit, calls sponsored service), territories, leaderboard
    notification_router.py — notifications CRUD
    payment_router.py      — YooKassa payments, crypto wallet, balance, withdraw
    admin_router.py        — CRUD sponsored territories, dashboard, payout processing
  schemas/             — Pydantic request/response models
  services/
    territory_service.py   — subtract occupied, bbox query, CRUD territories
    sponsored_service.py   — overlap detection, capture rewards, balance
    notification_service.py— notifications CRUD
  alembic/             — Database migrations
  tests/               — pytest suite (unit + integration)

frontend/
  index.html / auth.html / public.html / admin.html
  js/   — ES modules: app, api, auth, map, upload, editor, share, territories, admin, etc.
  css/  — base, main, auth, public
  nginx.conf — reverse proxy + security headers
```

## Development
```bash
# Full stack
docker-compose up --build

# Local dev
docker-compose up -d db
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && python3 -m http.server 3000
```

## Testing
```bash
cd backend

# Unit tests (no DB required)
pytest tests/test_auth.py tests/test_gpx_parser.py tests/test_loop_detector.py tests/test_merger.py tests/test_pipeline.py -v

# E2E tests (requires PostGIS on localhost:5432)
# DB: postgresql://postgres:postgres@localhost:5432/velo_io_test
pytest tests/test_e2e.py -v

# All tests (requires PostGIS)
pytest tests/ -v

# Run specific test class
pytest tests/test_e2e.py::TestAuth -v
pytest tests/test_e2e.py::TestOverlap -v

# Start PostGIS via Docker if not running:
docker-compose up -d db

# Run tests via Docker (DB auto-resets):
docker-compose run --rm backend pytest tests/test_e2e.py -v
```

## Key APIs
- `POST /api/auth/register` / `POST /api/auth/login` — auth (returns premium fields + captures_count)
- `POST /api/upload-gpx` — upload GPX, run pipeline, save territory (checks weekly limit 1, calls sponsored rewards)
- `GET /api/territories?north=&south=&east=&west=&limit=&offset=` — bbox query
- `GET /api/leaderboard?limit=&offset=` — ranking by total area
- `GET /api/notifications?limit=&offset=` — user notifications
- `GET /api/health` — health check (DB connectivity)
- `POST /api/payment/yookassa-create` — create YooKassa payment for Premium
- `POST /api/payment/yookassa-webhook` — YooKassa webhook
- `POST /api/payment/set-crypto-wallet` — save user's USDT TRC-20 wallet
- `POST /api/payment/withdraw-crypto` — request crypto payout
- `GET /api/balance` — user balance + sponsored territories
- `GET /api/admin/dashboard` — admin stats
- `POST /api/admin/sponsored-territories` — create sponsored zone (admin)
- `PATCH /api/admin/sponsored-territories/{id}` — update zone
- `DELETE /api/admin/sponsored-territories/{id}` — delete zone
- `GET /api/admin/payouts/crypto-pending` — pending crypto payouts
- `POST /api/admin/payouts/{id}/complete` — mark payout completed

## Environment Variables
See `backend/.env.example`. Key vars:
- `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` (ЮKassa for all payments)
- `FRONTEND_URL`
- `ADMIN_EMAIL` (default: admin@vel.io)

## Migrations
Alembic migrations in `backend/alembic/versions/`:
- `0001_initial.py` — users, territories, notifications
- `0002_add_premium_fields.py` — is_premium, captures_count
- `0003_add_sponsored_tables.py` — SponsoredTerritory, UserBalance, Transaction
- `0004_add_crypto_wallet.py` — crypto_wallet on User
- `0005_drop_stripe_customer_id.py` — удаление stripe_customer_id

To generate new migrations:
```bash
cd backend && alembic revision --autogenerate -m "description"
```

### Production deployment
- **Docker**: migrations run automatically via `start.sh` (`alembic upgrade head` before app starts)
- **Render (non-Docker)**: set start command to `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000`
- **Manual**: `docker-compose exec backend alembic upgrade head`
- **Reset DB (loses data)**: `docker-compose down -v && docker-compose up --build`
- Never delete old migration files — Alembic tracks which have been applied

## Conventions
- Russian language for user-facing messages and default values
- JWT auth via `Authorization: Bearer` header
- PostGIS for all spatial queries (ST_Intersects, ST_Difference, ST_DWithin, ST_Union)
- All datetimes are timezone-aware UTC
- Color values: `#RRGGBB` hex only (validated)
- Passwords: minimum 6 characters
- Free captures limit: 1 per week (configurable via FREE_CAPTURES_LIMIT)
- Premium price: 299₽ (configurable via PREMIUM_PRICE_RUB)
- Revenue share to user: 10% (REVENUE_SHARE in sponsored_service.py)
- Admin user: `admin@vel.io` (configurable via ADMIN_EMAIL in .env)
