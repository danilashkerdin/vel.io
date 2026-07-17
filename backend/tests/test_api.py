"""API integration tests using FastAPI TestClient.

These tests require a running PostGIS database.
Set DATABASE_URL env var to a test database before running.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override settings before importing app
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/velo_io_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-integration-tests")

from database import init_db, SessionLocal
from main import app
from limiter import limiter
from models import User, UserBalance, SponsoredTerritory, Transaction

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_gpx(filename):
    with open(os.path.join(FIXTURES, filename)) as f:
        return f.read()


def clean_db():
    """Manual DB cleanup — kept for ad-hoc use; the _clean_db fixture handles test cleanup."""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text("DELETE FROM notifications"))
        db.execute(text("DELETE FROM territories"))
        db.execute(text("DELETE FROM users"))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_db(client):
    # Reset shared rate limiter before each test
    limiter.reset()
    # Use raw SQL to truncate for speed
    db = SessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text("DELETE FROM transactions"))
        db.execute(text("DELETE FROM user_balances"))
        db.execute(text("DELETE FROM sponsored_territories"))
        db.execute(text("DELETE FROM notifications"))
        db.execute(text("DELETE FROM territories"))
        db.execute(text("DELETE FROM users"))
        db.commit()
    finally:
        db.close()
    yield


def register_user(client, email="test@test.com", username="testuser", password="test123"):
    r = client.post("/api/auth/register", json={
        "email": email,
        "username": username,
        "password": password,
    })
    assert r.status_code == 200, f"Register failed: {r.text}"
    return r.json()["token"]


def upload_gpx(client, token, gpx_content, filename="test.gpx"):
    files = {"file": (filename, gpx_content, "application/gpx+xml")}
    r = client.post(
        "/api/upload-gpx",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    return r


def _admin_token(client):
    """Register/login as admin@vel.io and return token."""
    r = client.post("/api/auth/register", json={
        "email": "admin@vel.io",
        "username": "admin",
        "password": "admin123",
    })
    assert r.status_code == 200, f"Admin register failed: {r.text}"
    return r.json()["token"]


def register_advertiser(client, email="adv@test.com", password="test123"):
    r = client.post("/api/auth/register", json={
        "email": email,
        "username": email.split("@")[0],
        "password": password,
        "is_advertiser": True,
    })
    assert r.status_code == 200, f"Advertiser register failed: {r.text}"
    return r.json()["token"]


SPONSORED_POINT = {
    "type": "Point",
    "coordinates": [37.6, 55.7],
}


# ==================== AUTH ====================


class TestAuth:
    def test_register(self, client):
        r = client.post("/api/auth/register", json={
            "email": "reg@test.com",
            "username": "reguser",
            "password": "test123",
        })
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["email"] == "reg@test.com"
        assert data["username"] == "reguser"

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "email": "dup@test.com", "username": "dup1", "password": "test123",
        })
        r = client.post("/api/auth/register", json={
            "email": "dup@test.com", "username": "dup2", "password": "test123",
        })
        assert r.status_code == 400

    def test_login(self, client):
        client.post("/api/auth/register", json={
            "email": "login@test.com", "username": "loginuser", "password": "test123",
        })
        r = client.post("/api/auth/login", json={
            "email": "login@test.com", "password": "test123",
        })
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={
            "email": "wrong@test.com", "username": "wronguser", "password": "test123",
        })
        r = client.post("/api/auth/login", json={
            "email": "wrong@test.com", "password": "wrongpassword",
        })
        assert r.status_code == 401

    def test_me(self, client):
        token = register_user(client)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["username"] == "testuser"

    def test_me_invalid_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"})
        assert r.status_code == 401


# ==================== TERRITORIES ====================


class TestTerritories:
    def test_upload_gpx_success(self, client):
        token = register_user(client)
        r = upload_gpx(client, token, load_gpx("big_square.gpx"))
        assert r.status_code == 200
        data = r.json()
        assert data["area"] > 0
        assert data["closures_found"] >= 1
        assert "polygon" in data

    def test_upload_non_gpx(self, client):
        token = register_user(client)
        files = {"file": ("test.txt", "hello", "text/plain")}
        r = client.post("/api/upload-gpx", files=files, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_fully_inside_subtraction(self, client):
        token1 = register_user(client, "inside1@test.com", "inside1")
        token2 = register_user(client, "inside2@test.com", "inside2")
        r1 = upload_gpx(client, token1, load_gpx("big_square.gpx"))
        assert r1.status_code == 200
        r2 = upload_gpx(client, token2, load_gpx("inside.gpx"))
        assert r2.status_code == 400
        assert "занята" in r2.json()["detail"].lower() or "уже" in r2.json()["detail"].lower()

    def test_far_away_no_subtraction(self, client):
        token1 = register_user(client, "far1@test.com", "far1")
        token2 = register_user(client, "far2@test.com", "far2")
        r1 = upload_gpx(client, token1, load_gpx("big_square.gpx"))
        r2 = upload_gpx(client, token2, load_gpx("far_away.gpx"))
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["area"] > 0

    def test_own_territory_not_subtracted(self, client):
        token = register_user(client, "own@test.com", "ownuser")
        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "own@test.com").first()
        user.is_premium = True
        sess.commit()
        sess.close()
        r1 = upload_gpx(client, token, load_gpx("far_away.gpx"))
        r2 = upload_gpx(client, token, load_gpx("far_away.gpx"))
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Both should have similar area (no self-subtraction)
        assert abs(r1.json()["area"] - r2.json()["area"]) / r1.json()["area"] < 0.1

    def test_half_inside_partial_subtraction(self, client):
        token1 = register_user(client, "half1@test.com", "half1")
        token2 = register_user(client, "half2@test.com", "half2")
        r1 = upload_gpx(client, token1, load_gpx("big_square.gpx"))
        r2 = upload_gpx(client, token2, load_gpx("half_inside.gpx"))
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["area"] < r1.json()["area"]

    def test_get_territories(self, client):
        token = register_user(client, "get@test.com", "getuser")
        upload_gpx(client, token, load_gpx("big_square.gpx"))
        r = client.get("/api/territories?north=56&south=55&east=38&west=37")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_update_territory(self, client):
        token = register_user(client, "upd@test.com", "upduser")
        r = upload_gpx(client, token, load_gpx("big_square.gpx"))
        tid = r.json()["id"]
        r2 = client.patch(
            f"/api/territories/{tid}",
            json={"name": "Новое имя", "color": "#FF0000"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["name"] == "Новое имя"
        assert r2.json()["color"] == "#FF0000"

    def test_delete_territory(self, client):
        token = register_user(client, "del@test.com", "deluser")
        r = upload_gpx(client, token, load_gpx("big_square.gpx"))
        tid = r.json()["id"]
        r2 = client.delete(
            f"/api/territories/{tid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200

    def test_delete_other_user_territory(self, client):
        token1 = register_user(client, "owner@test.com", "owner")
        token2 = register_user(client, "thief@test.com", "thief")
        r = upload_gpx(client, token1, load_gpx("big_square.gpx"))
        tid = r.json()["id"]
        r2 = client.delete(
            f"/api/territories/{tid}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r2.status_code == 403

    def test_my_territories(self, client):
        token = register_user(client, "my@test.com", "myuser")
        upload_gpx(client, token, load_gpx("far_away.gpx"))
        r = client.get("/api/my-territories", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert "name" in data[0]
        assert "area" in data[0]

    def test_public_territory(self, client):
        token = register_user(client, "pub@test.com", "pubuser")
        r = upload_gpx(client, token, load_gpx("big_square.gpx"))
        tid = r.json()["id"]
        r2 = client.get(f"/api/territories/public/{tid}")
        assert r2.status_code == 200
        assert r2.json()["name"] is not None
        assert r2.json()["username"] == "pubuser"


# ==================== LEADERBOARD ====================


class TestLeaderboard:
    def test_leaderboard(self, client):
        token1 = register_user(client, "lb1@test.com", "lbuser1")
        token2 = register_user(client, "lb2@test.com", "lbuser2")
        upload_gpx(client, token1, load_gpx("big_square.gpx"))
        upload_gpx(client, token2, load_gpx("far_away.gpx"))
        r = client.get("/api/leaderboard")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2
        # Sorted by total_area descending
        for i in range(len(data) - 1):
            assert data[i]["total_area"] >= data[i + 1]["total_area"]


# ==================== ADMIN ====================


class TestAdmin:
    def test_non_admin_forbidden(self, client):
        token = register_user(client, "user@test.com", "user")
        r = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    def test_admin_dashboard(self, client):
        token = _admin_token(client)
        r = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        d = r.json()
        assert "total_sponsored" in d
        assert "active_sponsored" in d
        assert "pending_payouts" in d

    def test_admin_tiers(self, client):
        token = _admin_token(client)
        r = client.get("/api/admin/tiers", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        tiers = r.json()
        assert len(tiers) == 3
        assert tiers[0]["name"] == "Старт"
        assert tiers[0]["stars"] == 1000

    def test_create_sponsored_point(self, client):
        token = _admin_token(client)
        r = client.post("/api/admin/sponsored-territories", json={
            "business_name": "Тестовый магазин",
            "monthly_budget_rub": 5000,
            "color": "#FF0000",
            "polygon": SPONSORED_POINT,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "created"
        assert "id" in data

    def test_list_sponsored(self, client):
        token = _admin_token(client)
        client.post("/api/admin/sponsored-territories", json={
            "business_name": "Магазин 1",
            "monthly_budget_rub": 3000,
            "polygon": SPONSORED_POINT,
        }, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/api/admin/sponsored-territories", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        zones = r.json()
        assert len(zones) >= 1
        assert zones[0]["business_name"] == "Магазин 1"
        assert "icon_size" in zones[0]

    def test_update_sponsored(self, client):
        token = _admin_token(client)
        r = client.post("/api/admin/sponsored-territories", json={
            "business_name": "Старое имя",
            "monthly_budget_rub": 5000,
            "polygon": SPONSORED_POINT,
        }, headers={"Authorization": f"Bearer {token}"})
        zone_id = r.json()["id"]
        r2 = client.patch(f"/api/admin/sponsored-territories/{zone_id}", json={
            "business_name": "Новое имя",
            "is_active": False,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "updated"
        zones = client.get("/api/admin/sponsored-territories", headers={"Authorization": f"Bearer {token}"}).json()
        updated = next(z for z in zones if z["id"] == zone_id)
        assert updated["business_name"] == "Новое имя"
        assert updated["is_active"] is False

    def test_delete_sponsored(self, client):
        token = _admin_token(client)
        r = client.post("/api/admin/sponsored-territories", json={
            "business_name": "Удалить меня",
            "monthly_budget_rub": 5000,
            "polygon": SPONSORED_POINT,
        }, headers={"Authorization": f"Bearer {token}"})
        zone_id = r.json()["id"]
        r2 = client.delete(f"/api/admin/sponsored-territories/{zone_id}", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "deleted"
        r3 = client.delete(f"/api/admin/sponsored-territories/{zone_id}", headers={"Authorization": f"Bearer {token}"})
        assert r3.status_code == 404

    def test_sponsored_not_found(self, client):
        token = _admin_token(client)
        r = client.patch("/api/admin/sponsored-territories/00000000-0000-0000-0000-000000000000",
                          json={"business_name": "x"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    def test_admin_payouts_pending_empty(self, client):
        token = _admin_token(client)
        r = client.get("/api/admin/payouts/pending", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []

    def test_admin_payouts_history_empty(self, client):
        token = _admin_token(client)
        r = client.get("/api/admin/payouts/history", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []

    def test_admin_process_payout(self, client):
        token = _admin_token(client)
        # Создаём пользователя с балансом
        user_token = register_user(client, "payuser@test.com", "payuser")
        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "payuser@test.com").first()
        user_id = str(user.id)
        sess.add(UserBalance(user_id=user.id, balance_rub=2000, total_earned_rub=3000))
        sess.commit()
        sess.close()
        # Обрабатываем выплату
        r = client.post(f"/api/admin/payouts/process/{user_id}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["amount_rub"] == 2000
        # Баланс обнулён
        bal = client.get("/api/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
        assert bal["balance_rub"] == 0

    def test_admin_process_payout_no_balance(self, client):
        token = _admin_token(client)
        register_user(client, "nobal@test.com", "nobaluser")
        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "nobal@test.com").first()
        user_id = str(user.id)
        sess.close()
        r = client.post(f"/api/admin/payouts/process/{user_id}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "Нет средств" in r.json()["detail"]


# ==================== PAYMENT ====================


class TestPayment:
    def test_payment_status_free(self, client):
        token = register_user(client)
        r = client.get("/api/payment/status", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["is_premium"] is False
        assert d["free_limit"] == 1
        assert d["captures_remaining"] == 1

    def test_balance_empty(self, client):
        token = register_user(client, "bal@test.com", "baluser")
        r = client.get("/api/balance", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["balance_rub"] == 0
        assert d["total_earned_rub"] == 0
        assert d["sponsored_territories"] == []

    def test_request_payout_insufficient_balance(self, client):
        token = register_user(client, "poor@test.com", "poor")
        r = client.post("/api/payment/request-payout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "минимальная" in r.json()["detail"].lower()

    def test_request_payout_full_flow(self, client):
        token = register_user(client, "rich@test.com", "rich")
        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "rich@test.com").first()
        sess.add(UserBalance(user_id=user.id, balance_rub=2000, total_earned_rub=3000))
        sess.commit()
        sess.close()
        # Request payout
        r = client.post("/api/payment/request-payout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["amount_rub"] == 2000
        assert d["status"] == "pending"
        # Balance should be zero
        bal = client.get("/api/balance", headers={"Authorization": f"Bearer {token}"}).json()
        assert bal["balance_rub"] == 0
        # Admin sees pending payout
        admin_token = _admin_token(client)
        history = client.get("/api/admin/payouts/history",
                             headers={"Authorization": f"Bearer {admin_token}"}).json()
        assert len(history) >= 1

    def test_transactions_history(self, client):
        token = register_user(client, "tx@test.com", "txuser")
        r = client.get("/api/transactions", headers={"Authorization": f"Bearer {token}"})
        assert r.json() == []

    def test_my_sponsored_empty(self, client):
        token = register_user(client, "mysp@test.com", "mysponsored")
        r = client.get("/api/my-sponsored", headers={"Authorization": f"Bearer {token}"})
        assert r.json() == []

    def test_star_invoice_no_bot(self, client):
        token = register_user(client, "st@test.com", "stuser")
        r = client.post("/api/payment/create-star-invoice?purpose=premium",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 503
        assert "бот не настроен" in r.json()["detail"]


# ==================== SPONSORED TERRITORIES (PUBLIC) ====================


class TestSponsored:
    def test_public_sponsored_empty_bbox(self, client):
        r = client.get("/api/sponsored-territories?north=56&south=55&east=38&west=37")
        assert r.status_code == 200
        assert r.json() == []

    def test_public_sponsored_shows_created(self, client):
        admin_token = _admin_token(client)
        client.post("/api/admin/sponsored-territories", json={
            "business_name": "Публичная зона",
            "monthly_budget_rub": 5000,
            "polygon": SPONSORED_POINT,
            "color": "#00FF00",
            "image_url": "https://example.com/logo.png",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        r = client.get("/api/sponsored-territories?north=56&south=55&east=38&west=37")
        assert r.status_code == 200
        zones = r.json()
        assert len(zones) >= 1
        z = zones[0]
        assert z["business_name"] == "Публичная зона"
        assert "color" in z
        assert "icon_size" in z
        assert z["image_url"] == "https://example.com/logo.png"

    def test_public_sponsored_outside_bbox(self, client):
        admin_token = _admin_token(client)
        client.post("/api/admin/sponsored-territories", json={
            "business_name": "Далеко",
            "monthly_budget_rub": 3000,
            "polygon": SPONSORED_POINT,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        # Query a bbox far from Moscow
        r = client.get("/api/sponsored-territories?north=60&south=59&east=31&west=30")
        assert r.json() == []


# ==================== FREE LIMIT ====================


class TestFreeLimit:
    def test_free_limit_blocks_second_upload(self, client):
        token = register_user(client, "limit@test.com", "limituser")
        gpx = load_gpx("far_away.gpx")
        r1 = upload_gpx(client, token, gpx, filename="first.gpx")
        assert r1.status_code == 200
        r2 = upload_gpx(client, token, gpx, filename="second.gpx")
        assert r2.status_code == 402
        assert "лимит" in r2.json()["detail"].lower()

    def test_premium_bypasses_free_limit(self, client):
        token = register_user(client, "prem@test.com", "premuser")
        gpx = load_gpx("far_away.gpx")
        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "prem@test.com").first()
        user.is_premium = True
        sess.commit()
        sess.close()
        # Upload 4 times — should all succeed
        for i in range(4):
            r = upload_gpx(client, token, gpx, filename=f"prem_track{i}.gpx")
            assert r.status_code == 200, f"Premium upload {i} failed: {r.text}"
        # Status should show unlimited
        s = client.get("/api/payment/status", headers={"Authorization": f"Bearer {token}"}).json()
        assert s["captures_remaining"] == -1


# ==================== NOTIFICATIONS ====================


class TestNotifications:
    def test_empty_notifications(self, client):
        token = register_user(client, "notif_empty@test.com", "notifempty")
        r = client.get("/api/notifications", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["unread"] == 0
        assert data["items"] == []

    def test_read_all_notifications(self, client):
        token = register_user(client, "notif_read@test.com", "notifread")
        r = client.post("/api/notifications/read-all", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200


# ==================== ADVERTISER FLOW ====================


class TestAdvertiserFlow:
    def test_register_as_advertiser(self, client):
        r = client.post("/api/auth/register", json={
            "email": "adv_reg@test.com",
            "username": "adv_reg",
            "password": "test123",
            "is_advertiser": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_advertiser"] is True

    def test_register_as_cyclist_default(self, client):
        token = register_user(client, "cyclist_default@test.com", "cyclist")
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["is_advertiser"] is False

    def test_cyclist_cannot_access_advertiser_endpoints(self, client):
        token = register_user(client, "cyclist_adv@test.com", "cyclistadv")
        r = client.get("/api/advertiser/profile", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    def test_advertiser_profile_created(self, client):
        token = register_advertiser(client, "adv_profile@test.com")
        r = client.get("/api/advertiser/profile", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["business_name"] is None
        assert data["email"] == "adv_profile@test.com"

    def test_advertiser_profile_update(self, client):
        token = register_advertiser(client, "adv_update@test.com")
        r = client.put("/api/advertiser/profile", json={
            "business_name": "Top Bike",
            "contact_telegram": "@topbike",
            "website": "https://topbike.example.com",
            "description": "Лучший веломагазин",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["business_name"] == "Top Bike"
        assert data["contact_telegram"] == "@topbike"

    def test_advertiser_dashboard_empty(self, client):
        token = register_advertiser(client, "adv_dash_empty@test.com")
        r = client.get("/api/advertiser/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["active_zones"] == 0
        assert data["total_zones"] == 0
        assert data["total_spent_stars"] == 0
        assert data["total_impressions"] == 0
        assert data["total_clicks"] == 0

    def test_advertiser_star_invoice_requires_bot(self, client):
        token = register_advertiser(client, "adv_invoice@test.com")
        r = client.post("/api/payment/create-star-invoice?purpose=sponsored&business_name=Test&monthly_budget_stars=100", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 503
        assert "бот не настроен" in r.json()["detail"]

    def test_advertiser_zone_crud(self, client):
        from geoalchemy2.shape import from_shape
        from shapely.geometry import shape
        token = register_advertiser(client, "adv_zone@test.com")

        # Create zone directly (without payment)
        zone = SponsoredTerritory(
            business_name="Тестовая зона",
            monthly_budget_rub=1000,
            polygon=from_shape(shape({"type": "Point", "coordinates": [37.6, 55.7]}), srid=4326),
            is_active=False,
            owner_id=User.id,
        )
        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "adv_zone@test.com").first()
        zone.owner_id = user.id
        sess.add(zone)
        sess.commit()
        zone_id = zone.id
        sess.close()

        # List zones
        r = client.get("/api/my-advertiser-zones", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        zones = r.json()
        assert len(zones) == 1
        assert zones[0]["business_name"] == "Тестовая зона"

        # Update zone
        r = client.patch(f"/api/my-advertiser-zones/{zone_id}", json={
            "business_name": "Обновлённая зона",
            "image_url": "https://example.com/logo.png",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        # Activate
        r = client.post(f"/api/my-advertiser-zones/{zone_id}/activate", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["is_active"] is True

        # Pause
        r = client.post(f"/api/my-advertiser-zones/{zone_id}/pause", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        # Other user cannot access
        other_token = register_user(client, "other_adv_zone@test.com", "otheruser")
        r = client.patch(f"/api/my-advertiser-zones/{zone_id}", json={"business_name": "Hack"}, headers={"Authorization": f"Bearer {other_token}"})
        assert r.status_code == 403

    def test_advertiser_payments(self, client):
        from models import AdvertiserPayment
        from uuid import uuid4
        token = register_advertiser(client, "adv_pay@test.com")

        sess = SessionLocal()
        user = sess.query(User).filter(User.email == "adv_pay@test.com").first()
        payment = AdvertiserPayment(
            user_id=user.id,
            amount_stars=500,
            purpose="create_zone",
            status="completed",
        )
        sess.add(payment)
        sess.commit()
        sess.close()

        r = client.get("/api/advertiser/payments", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        payments = r.json()
        assert len(payments) == 1
        assert payments[0]["amount_stars"] == 500
        assert payments[0]["purpose"] == "create_zone"
