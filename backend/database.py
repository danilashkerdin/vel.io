import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

logger = logging.getLogger("velo_io")

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_recycle=900,
    pool_pre_ping=True,
    pool_timeout=30,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_not_exists(table: str, column: str, col_type: str):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT 1 FROM information_schema.columns "
                f"WHERE table_name='{table}' AND column_name='{column}'"
            )
        ).fetchone()
        if not row:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
            logger.info("Added column %s.%s (%s)", table, column, col_type)


def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)

    # Apply missing migrations idempotently (alembic env.py may fail on Render)
    _add_column_if_not_exists("users", "is_premium", "BOOLEAN DEFAULT FALSE")
    _add_column_if_not_exists("users", "captures_count", "INTEGER DEFAULT 0")
    _add_column_if_not_exists("users", "ton_wallet", "VARCHAR(48)")
    _add_column_if_not_exists("users", "is_advertiser", "BOOLEAN DEFAULT FALSE")
    with engine.connect() as conn:
        conn.execute(text("UPDATE users SET is_advertiser = FALSE WHERE is_advertiser IS NULL"))
        conn.commit()
    _add_column_if_not_exists("users", "referred_by", "UUID REFERENCES users(id) ON DELETE SET NULL")
    _add_column_if_not_exists("users", "referral_bonuses", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_not_exists("users", "telegram_chat_id", "VARCHAR(32)")
    if "crypto_wallet" in _get_columns("users"):
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users DROP COLUMN crypto_wallet"))
            conn.commit()
            logger.info("Dropped column users.crypto_wallet")
    if "stripe_customer_id" in _get_columns("users"):
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users DROP COLUMN stripe_customer_id"))
            conn.commit()
            logger.info("Dropped column users.stripe_customer_id")
    with engine.connect() as conn:
        conn.execute(text(
            f"UPDATE users SET is_premium = TRUE WHERE id IN "
            f"(SELECT id FROM users ORDER BY created_at ASC LIMIT {settings.FREE_PREMIUM_SLOTS})"
            f" AND is_premium = FALSE"
        ))
        conn.commit()
        logger.info("Free premium granted to first %d users", settings.FREE_PREMIUM_SLOTS)
    cols = _get_columns("users")
    if "yoomoney_wallet" in cols and "ton_wallet" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users RENAME COLUMN yoomoney_wallet TO ton_wallet"))
            conn.commit()
            logger.info("Renamed users.yoomoney_wallet → ton_wallet")
    elif "yoomoney_wallet" in cols and "ton_wallet" in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users DROP COLUMN yoomoney_wallet"))
            conn.commit()
            logger.info("Dropped users.yoomoney_wallet (ton_wallet already exists)")
    _add_column_if_not_exists("sponsored_territories", "owner_id", "UUID REFERENCES users(id) ON DELETE SET NULL")
    _add_column_if_not_exists("sponsored_territories", "clicks", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_not_exists("sponsored_territories", "impressions", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_not_exists("sponsored_territories", "expires_at", "TIMESTAMP WITH TIME ZONE")
    _add_column_if_not_exists("sponsored_territories", "monthly_budget_stars", "INTEGER")
    _add_column_if_not_exists("sponsored_territories", "is_active", "BOOLEAN NOT NULL DEFAULT TRUE")
    _add_column_if_not_exists("territories", "expires_at", "TIMESTAMP WITH TIME ZONE")
    _fix_column_type("notifications", "read", "BOOLEAN DEFAULT FALSE")
    _activate_demo_zone()
    _cleanup_expired()
    _notify_expiring_territories()


def _fix_column_type(table: str, column: str, new_type: str):
    """Исправляет тип колонки, если она не того типа."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT data_type FROM information_schema.columns "
                f"WHERE table_name='{table}' AND column_name='{column}'"
            )
        ).fetchone()
        if not row:
            return
        current = row[0]
        expected = new_type.split()[0].lower()
        if current == expected:
            return  # уже правильный тип
        new_type_clean = new_type.split()[0]
        default_clause = new_type[len(new_type_clean):].strip()
        conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_type_clean} USING {column}::boolean"))
        if default_clause:
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} SET {default_clause}"))
        conn.commit()
        logger.info("Fixed column type %s.%s: %s → %s", table, column, current, new_type)


def _activate_demo_zone():
    """Активирует демо-зону «Здесь может быть ваша реклама»."""
    from models import SponsoredTerritory
    with SessionLocal() as session:
        zone = session.query(SponsoredTerritory).filter(
            SponsoredTerritory.business_name == "Здесь может быть ваша реклама"
        ).first()
        if zone and not zone.is_active:
            zone.is_active = True
            session.commit()


def _notify_expiring_territories():
    """Отправляет Telegram-уведомления владельцам территорий, которые скоро сгорят."""
    from datetime import datetime, timezone, timedelta
    from models import User, Territory

    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=1)
    very_soon = now + timedelta(hours=6)

    with SessionLocal() as session:
        territories = (
            session.query(Territory, User.telegram_chat_id)
            .join(User, User.id == Territory.user_id)
            .filter(
                Territory.expires_at.isnot(None),
                Territory.expires_at > now,
                Territory.expires_at <= soon,
                User.telegram_chat_id.isnot(None),
            )
            .all()
        )

        for t, chat_id in territories:
            remaining = t.expires_at - now
            if remaining.total_seconds() <= 0:
                continue
            text = f"⚠️ Твоя территория *{t.name}* скоро сгорит! Осталось *{remaining.seconds // 3600} ч {remaining.seconds % 3600 // 60} мин*"
            # Шлём в телеграм
            import httpx
            bot_token = settings.TELEGRAM_BOT_TOKEN
            if bot_token:
                try:
                    httpx.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                        timeout=10,
                    )
                except Exception as e:
                    logger.error("Failed to send expiry notification: %s", e)
            logger.info("Activated demo sponsored zone «Здесь может быть ваша реклама»")


def _get_columns(table: str) -> set:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{table}'"
            )
        ).fetchall()
        return {r[0] for r in rows}


def _cleanup_expired():
    """Удаляет просроченные территории и деактивирует просроченные спонсорские зоны."""
    from datetime import datetime, timezone
    from models import Territory, SponsoredTerritory
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        # Удаляем истёкшие территории обычных пользователей
        deleted = session.query(Territory).filter(
            Territory.expires_at.isnot(None),
            Territory.expires_at <= now,
        ).delete(synchronize_session=False)
        if deleted:
            logger.info("Deleted %d expired territories", deleted)

        # Деактивируем истёкшие спонсорские зоны
        deactivated = session.query(SponsoredTerritory).filter(
            SponsoredTerritory.expires_at.isnot(None),
            SponsoredTerritory.expires_at <= now,
            SponsoredTerritory.is_active == True,
        ).update({"is_active": False}, synchronize_session=False)
        if deactivated:
            logger.info("Deactivated %d expired sponsored territories", deactivated)

        session.commit()
