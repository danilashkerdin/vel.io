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


def _fix_column_type(table: str, column: str, old_type: str, new_type: str):
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
        conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_type} USING {column}::boolean"))
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
