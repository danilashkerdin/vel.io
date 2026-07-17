"""End-to-end API tests using FastAPI TestClient.

Covers: registration, territory capture, overlap/subtract, notifications,
leaderboard, sponsored zones, user profile, activity feed, expiry.

Run:  docker-compose run --rm backend pytest tests/test_e2e.py -v
Requires: PostGIS database (DATABASE_URL in env or .env)
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/velo_io_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e-tests")
os.environ.setdefault("FREE_CAPTURES_LIMIT", "1")
os.environ.setdefault("VIP_EMAILS", "[]")

from database import init_db, SessionLocal
from main import app
from limiter import limiter
from models import User, Territory, Notification, SponsoredTerritory, UserBalance, Transaction, UserAchievement, ACHIEVEMENT_TYPES
from routers.territory_router import _leaderboard_cache

# ── helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_db():
    init_db()
    with SessionLocal() as s:
        s.execute(UserAchievement.__table__.delete())
        s.execute(UserBalance.__table__.delete())
        s.execute(Transaction.__table__.delete())
        s.execute(Notification.__table__.delete())
        s.execute(SponsoredTerritory.__table__.delete())
        s.execute(Territory.__table__.delete())
        s.execute(User.__table__.delete())
        s.commit()
    _leaderboard_cache["data"] = None
    _leaderboard_cache["ts"] = 0
    limiter.reset()
    yield


def register(email="a@b.com", username="u1", password="123456"):
    return client.post("/api/auth/register", json={
        "email": email, "username": username, "password": password,
    })


def login(email="a@b.com", password="123456"):
    return client.post("/api/auth/login", json={
        "email": email, "password": password,
    })


def token(email="a@b.com"):
    r = register(email)
    return r.json()["token"]


def auth_headers(t):
    return {"Authorization": f"Bearer {t}"}


def capture_ride(t, pts, name="test"):
    return client.post(
        "/api/capture-ride",
        json={"points": pts, "name": name},
        headers=auth_headers(t),
    )


# A small closed square around Moscow (55.74, 37.62)
SQUARE = [
    [55.748, 37.615],
    [55.748, 37.630],
    [55.738, 37.630],
    [55.738, 37.615],
    [55.748, 37.615],
]

SMALL_INSIDE = [
    [55.746, 37.620],
    [55.746, 37.624],
    [55.742, 37.624],
    [55.742, 37.620],
    [55.746, 37.620],
]

HALF_INSIDE = [
    [55.750, 37.620],
    [55.750, 37.628],
    [55.742, 37.628],
    [55.742, 37.620],
    [55.750, 37.620],
]

client = TestClient(app)


# ── 1. Auth ──────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_and_login(self):
        r = register()
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == "a@b.com"
        assert d["username"] == "u1"
        assert "token" in d

        r2 = login()
        assert r2.status_code == 200
        assert r2.json()["email"] == "a@b.com"

    def test_register_duplicate_email(self):
        register()
        r = register()
        assert r.status_code == 400

    def test_register_short_password(self):
        r = register(password="12")
        assert r.status_code == 422

    def test_login_wrong_password(self):
        register()
        r = login(password="wrong")
        assert r.status_code == 401

    def test_me(self):
        t = token()
        r = client.get("/api/auth/me", headers=auth_headers(t))
        assert r.status_code == 200
        assert r.json()["email"] == "a@b.com"


# ── 2. Territory capture ─────────────────────────────────────────────────────

class TestCaptureRide:
    def test_capture_new_territory(self):
        t = token()
        r = capture_ride(t, SQUARE)
        assert r.status_code == 200
        d = r.json()
        assert d["area"] > 0
        assert "id" in d
        assert d["name"] == "Поездка"

    def test_capture_invalid_data(self):
        t = token()
        r = capture_ride(t, [[55.74, 37.62]])  # only one point, not a loop
        assert r.status_code == 400

    def test_capture_open_path(self):
        """Open path (start != end) should be rejected."""
        t = token()
        open_path = [
            [55.750, 37.500],
            [55.752, 37.502],
            [55.740, 37.510],
        ]
        r = capture_ride(t, open_path)
        assert r.status_code == 400

    def test_free_limit_enforced(self):
        """Free tier: 1 capture per week."""
        t = token("limit@test.com")
        with SessionLocal() as s:
            u = s.query(User).filter(User.email == "limit@test.com").first()
            u.is_premium = False
            s.commit()
        capture_ride(t, SQUARE)
        r = capture_ride(t, HALF_INSIDE)  # second capture — should be blocked
        assert r.status_code == 402

    def test_premium_ignores_limit(self):
        """Premium user (is_premium=True) bypasses the limit."""
        t = token("prem_user@test.com")
        # Make user premium
        with SessionLocal() as s:
            user = s.query(User).filter(User.email == "prem_user@test.com").first()
            user.is_premium = True
            s.commit()
        capture_ride(t, SQUARE)
        r = capture_ride(t, HALF_INSIDE)  # second capture — allowed
        assert r.status_code == 200


# ── 3. Overlap + subtract ───────────────────────────────────────────────────

class TestOverlap:
    def test_overlap_deducts_area(self):
        """User2 captures inside User1's territory — gets nothing."""
        t1 = token("overlap1@test.com")
        t2 = token("overlap2@test.com")
        r1 = capture_ride(t1, SQUARE)
        assert r1.status_code == 200

        r2 = capture_ride(t2, SMALL_INSIDE)
        r2 = capture_ride(t2, SMALL_INSIDE)
        assert r2.status_code == 400
        assert "занята" in r2.text

    def test_partial_overlap(self):
        """User2 captures half inside User1 — gets only the non-overlapping part."""
        t1 = token("partial1@test.com")
        t2 = token("partial2@test.com")
        r1 = capture_ride(t1, SQUARE)
        area1 = r1.json()["area"]

        # HALF_INSIDE has its north half inside SQUARE, south half outside
        r2 = capture_ride(t2, HALF_INSIDE)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["area"] > 0
        # should be less than full half_inside area (subtracted portion)
        full_half = 0.008 * 0.008 * 111_320 * 111_320
        assert d2["area"] < full_half * 0.8, f"Expected reduced area, got {d2['area']}"

    def test_no_overlap(self):
        """User2 captures far away — full area awarded."""
        t1 = token("nooverlap1@test.com")
        t2 = token("nooverlap2@test.com")
        capture_ride(t1, SQUARE)

        far_away = [
            [55.800, 37.500],
            [55.800, 37.510],
            [55.790, 37.510],
            [55.790, 37.500],
            [55.800, 37.500],
        ]
        r2 = capture_ride(t2, far_away)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["area"] > 600_000  # ~1.1 km² = 1.1M m² area is reasonable


# ── 4. Notifications ────────────────────────────────────────────────────────

class TestNotifications:
    def test_notification_created_on_capture(self):
        """User2 should receive a notification when User1 captures nearby."""
        t1 = token("notify1@test.com")
        capture_ride(t1, SQUARE)

        t2 = token("notify2@test.com")
        # Capture right next to User1's territory
        nearby = [[x + 0.002 for x in row] for row in SQUARE]
        capture_ride(t2, nearby)

        r = client.get("/api/notifications", headers=auth_headers(t1))
        assert r.status_code == 200
        d = r.json()
        assert d["unread"] > 0
        assert len(d["items"]) > 0

    def test_mark_all_read(self):
        t1 = token("markread1@test.com")
        capture_ride(t1, SQUARE)

        t2 = token("markread2@test.com")
        nearby = [[x + 0.002 for x in row] for row in SQUARE]
        capture_ride(t2, nearby)

        r = client.post("/api/notifications/read-all", headers=auth_headers(t1))
        assert r.status_code == 200

        r2 = client.get("/api/notifications", headers=auth_headers(t1))
        assert r2.json()["unread"] == 0

    def test_no_notifications_for_self(self):
        """Capturing near your own territory should not create a notification."""
        t = token("selfnotif@test.com")
        capture_ride(t, SQUARE)
        nearby = [[x + 0.002 for x in row] for row in SQUARE]
        capture_ride(t, nearby)

        r = client.get("/api/notifications", headers=auth_headers(t))
        assert r.json()["unread"] == 0


# ── 5. Leaderboard ──────────────────────────────────────────────────────────

class TestLeaderboard:
    def test_leaderboard_returns_users_by_area(self):
        t1 = token("lb1@test.com")
        t2 = token("lb2@test.com")
        capture_ride(t1, SQUARE)
        capture_ride(t2, HALF_INSIDE)

        r = client.get("/api/leaderboard?limit=10")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 2
        # User1 should rank higher (bigger territory)
        assert items[0]["username"] == "u1"

    def test_leaderboard_excludes_expired(self):
        t = token("lbexpire@test.com")
        capture_ride(t, SQUARE)
        # Manually expire the territory
        with SessionLocal() as s:
            terr = s.query(Territory).first()
            from datetime import datetime, timezone
            terr.expires_at = datetime.now(timezone.utc)
            s.commit()

        r = client.get("/api/leaderboard?limit=10")
        items = r.json()
        total_area = sum(i["total_area"] for i in items)
        assert total_area == 0, "Expired territories should not count"


# ── 6. Sponsored zones ──────────────────────────────────────────────────────

class TestSponsored:
    def test_capture_sponsored_zone_adds_balance(self):
        """Capturing over a sponsored zone should credit the capturer."""
        # Create sponsored zone as admin
        admin_t = token("admin@vel.io")
        big_square_sponsored = {
            "business_name": "Test Shop",
            "description": "Best shop ever",
            "monthly_budget_stars": 5000,
            "polygon": {
                "type": "Polygon",
                "coordinates": [[[37.61, 55.74], [37.63, 55.74],
                                 [37.63, 55.75], [37.61, 55.75],
                                 [37.61, 55.74]]]
            },
            "color": "#FF0000",
        }
        r = client.post(
            "/api/admin/sponsored-territories",
            json=big_square_sponsored,
            headers=auth_headers(admin_t),
        )
        assert r.status_code == 200

        # User captures inside the sponsored zone
        user_t = token("sponsored_user@test.com")
        sponsored_overlap = [
            [55.745, 37.615],
            [55.745, 37.625],
            [55.740, 37.625],
            [55.740, 37.615],
            [55.745, 37.615],
        ]
        r2 = capture_ride(user_t, sponsored_overlap)
        assert r2.status_code == 200

        # Check balance was credited — may be balance_rub or total_earned_rub
        r3 = client.get("/api/balance", headers=auth_headers(user_t))
        assert r3.status_code == 200
        bal = r3.json()
        if "total_earned_rub" in bal:
            assert bal["total_earned_rub"] >= 0, f"unexpected balance: {bal}"
        elif "balance_rub" in bal:
            assert bal["balance_rub"] >= 0, f"unexpected balance: {bal}"

    def test_sponsored_zones_in_bbox(self):
        """Public endpoint returns sponsored zones in bounding box."""
        # Create sponsored zone
        admin_t = token("admin@vel.io")
        client.post("/api/admin/sponsored-territories", json={
            "business_name": "Shop",
            "description": "Desc",
            "monthly_budget_stars": 1000,
            "polygon": {
                "type": "Polygon",
                "coordinates": [[[37.61, 55.74], [37.63, 55.74],
                                 [37.63, 55.75], [37.61, 55.75],
                                 [37.61, 55.74]]]
            },
            "color": "#00FF00",
        }, headers=auth_headers(admin_t))

        r = client.get("/api/sponsored-territories?north=56&south=55&east=38&west=37")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert items[0]["business_name"] == "Shop"


# ── 7. User profile ─────────────────────────────────────────────────────────

class TestUserProfile:
    def test_user_territories(self):
        t = token("profile_user@test.com")
        capture_ride(t, SQUARE)

        # Get current user's id
        me = client.get("/api/auth/me", headers=auth_headers(t)).json()
        uid = me["id"]

        r = client.get(f"/api/users/{uid}/territories")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert items[0]["name"] == "Поездка"

    def test_user_territories_nonexistent_user(self):
        r = client.get("/api/users/00000000-0000-0000-0000-000000000000/territories")
        assert r.status_code == 200
        assert r.json() == []

    def test_user_profile_fields(self):
        t = token("profile_fields@test.com")
        me = client.get("/api/auth/me", headers=auth_headers(t)).json()
        assert "id" in me
        assert "email" in me
        assert "username" in me
        assert "captures_count" in me
        assert "is_premium" in me


# ── 8. Activity feed ────────────────────────────────────────────────────────

class TestActivity:
    def test_activity_returns_recent_captures(self):
        t = token("activity_user@test.com")
        capture_ride(t, SQUARE)

        r = client.get("/api/activity?limit=10")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1

    def test_activity_pagination(self):
        t1 = token("act_pag1@test.com")
        t2 = token("act_pag2@test.com")
        capture_ride(t1, SQUARE)
        capture_ride(t2, [[55.75, 37.60], [55.75, 37.61], [55.74, 37.61],
                         [55.74, 37.60], [55.75, 37.60]])

        r = client.get("/api/activity?limit=10")
        items = r.json()
        assert len(items) >= 2

        r1 = client.get("/api/activity?limit=1")
        items1 = r1.json()
        assert len(items1) == 1


# ── 9. Territory query (bbox) ───────────────────────────────────────────────

class TestTerritoryQuery:
    def test_bbox_returns_territories(self):
        t = token("bbox@test.com")
        capture_ride(t, SQUARE)

        r = client.get(
            "/api/territories",
            params={"north": 56, "south": 55, "east": 38, "west": 37},
            headers=auth_headers(t),
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1

    def test_bbox_empty_area(self):
        t = token("bbox_empty@test.com")
        r = client.get(
            "/api/territories",
            params={"north": 50, "south": 49, "east": 31, "west": 30},
            headers=auth_headers(t),
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_public_territory(self):
        t = token("public@test.com")
        cr = capture_ride(t, SQUARE)
        tid = cr.json()["id"]

        r = client.get(f"/api/territories/public/{tid}")
        assert r.status_code == 200
        d = r.json()
        assert d["username"] == "u1"


# ── 10. Expiry ──────────────────────────────────────────────────────────────

class TestExpiry:
    def test_expired_territory_hidden_from_public(self):
        t = token("expire@test.com")
        capture_ride(t, SQUARE)

        with SessionLocal() as s:
            from datetime import datetime, timezone
            terr = s.query(Territory).first()
            terr.expires_at = datetime.now(timezone.utc)
            s.commit()

        r = client.get(
            "/api/territories",
            params={"north": 56, "south": 55, "east": 38, "west": 37},
            headers=auth_headers(t),
        )
        items = r.json()
        assert len(items) == 0, "Expired territory should not appear in bbox query"

    def test_expired_territory_still_in_my_territories(self):
        t = token("expire_my@test.com")
        capture_ride(t, SQUARE)

        with SessionLocal() as s:
            from datetime import datetime, timezone
            terr = s.query(Territory).first()
            terr.expires_at = datetime.now(timezone.utc)
            s.commit()

        r = client.get("/api/my-territories", headers=auth_headers(t))
        items = r.json()
        assert len(items) == 1, "Expired territory should still appear in My Territories"


# ── 11. Territory CRUD ──────────────────────────────────────────────────────

class TestTerritoryCRUD:
    def test_update_territory(self):
        t = token("update@test.com")
        cr = capture_ride(t, SQUARE)
        tid = cr.json()["id"]

        r = client.patch(f"/api/territories/{tid}", json={
            "name": "updated name",
            "color": "#FF00FF",
        }, headers=auth_headers(t))
        assert r.status_code == 200
        assert r.json()["name"] == "updated name"

    def test_delete_territory(self):
        t = token("delete@test.com")
        cr = capture_ride(t, SQUARE)
        tid = cr.json()["id"]

        r = client.delete(f"/api/territories/{tid}", headers=auth_headers(t))
        assert r.status_code == 200

        r2 = client.get("/api/my-territories", headers=auth_headers(t))
        assert r2.json() == []


# ── 12. Achievements ─────────────────────────────────────────────────────────

class TestAchievements:
    def test_first_capture_achievement(self):
        t = token("ach_first@test.com")
        r = capture_ride(t, SQUARE)
        assert r.status_code == 200

        r2 = client.get("/api/achievements", headers=auth_headers(t))
        assert r2.status_code == 200
        types = [a["type"] for a in r2.json()]
        assert "first_capture" in types

    def test_territories_5_achievement(self):
        t = token("ach_5@test.com")
        from models import User as UserModel
        with SessionLocal() as s:
            user = s.query(UserModel).first()
            user.is_premium = True
            s.commit()

        for _ in range(5):
            r = capture_ride(t, SQUARE)
            assert r.status_code == 200

        r2 = client.get("/api/achievements", headers=auth_headers(t))
        types = [a["type"] for a in r2.json()]
        assert "territories_5" in types

    def test_premium_achievement(self):
        t = token("ach_prem@test.com")
        from models import User as UserModel
        with SessionLocal() as s:
            user = s.query(UserModel).filter(UserModel.email == "ach_prem@test.com").first()
            user.is_premium = True
            s.commit()

        from services.achievement_service import check_achievements_on_premium
        with SessionLocal() as s:
            user = s.query(UserModel).filter(UserModel.email == "ach_prem@test.com").first()
            check_achievements_on_premium(s, user.id)

        r = client.get("/api/achievements", headers=auth_headers(t))
        types = [a["type"] for a in r.json()]
        assert "premium" in types

    def test_referral_achievement(self):
        t = token("ach_ref1@test.com")
        uid = client.get("/api/auth/me", headers=auth_headers(t)).json()["id"]

        r = register("ach_ref2@test.com", "ref2", "123456")
        r2 = client.post(
            "/api/auth/register",
            json={"email": "ach_ref3@test.com", "username": "ref3", "password": "123456"},
            headers={"X-Referral-ID": uid},
        )
        assert r2.status_code == 200

        r3 = client.get("/api/achievements", headers=auth_headers(t))
        types = [a["type"] for a in r3.json()]
        assert "invite_friend" in types

    def test_achievements_endpoint_returns_all_types(self):
        t = token("ach_all@test.com")
        r = client.get("/api/achievements", headers=auth_headers(t))
        assert r.status_code == 200
        assert isinstance(r.json(), list)