import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    captures_count = Column(Integer, default=0, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)
    ton_wallet = Column(String(48), nullable=True)
    is_advertiser = Column(Boolean, default=False, nullable=False)
    referred_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_bonuses = Column(Integer, default=0, nullable=False)
    telegram_chat_id = Column(String(32), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Territory(Base):
    __tablename__ = "territories"
    __table_args__ = (
        Index("ix_territories_user_id_created_at", "user_id", "created_at"),
        Index("ix_territories_polygon", "polygon", postgresql_using="gist"),
        Index("ix_territories_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False, default="Безымянный")
    polygon = Column(Geometry("GEOMETRY", srid=4326), nullable=False)
    area = Column(Float, nullable=False)
    closures_count = Column(Integer, default=1)
    parts_count = Column(Integer, default=1)
    source = Column(String(50), default="gpx")
    expires_at = Column(DateTime, nullable=True, default=None)

    color = Column(String(7), default="#4CAF50")
    image_url = Column(String(500), nullable=True)
    description = Column(String(1000), nullable=True)
    link_url = Column(String(500), nullable=True)

    user = relationship("User", backref="territories")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_read", "user_id", "read"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)  # nearby
    message = Column(String(500), nullable=False)
    territory_id = Column(UUID(as_uuid=True), ForeignKey("territories.id", ondelete="SET NULL"), nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SponsoredTerritory(Base):
    __tablename__ = "sponsored_territories"
    __table_args__ = (
        Index("ix_sponsored_polygon", "polygon", postgresql_using="gist"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    polygon = Column(Geometry("GEOMETRY", srid=4326), nullable=True)
    monthly_budget_rub = Column(Integer, nullable=False, default=5000)
    monthly_budget_stars = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    image_url = Column(String(500), nullable=True)
    link_url = Column(String(500), nullable=True)
    color = Column(String(7), default="#FFD700")
    current_owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owned_since = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    clicks = Column(Integer, default=0, nullable=False)
    impressions = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class AdvertiserProfile(Base):
    __tablename__ = "advertiser_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    business_name = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_telegram = Column(String(100), nullable=True)
    website = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="advertiser_profile", uselist=False)


class AdvertiserPayment(Base):
    __tablename__ = "advertiser_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sponsored_territory_id = Column(UUID(as_uuid=True), ForeignKey("sponsored_territories.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_stars = Column(Integer, nullable=False)
    purpose = Column(String(50), nullable=False, index=True)  # create_zone | top_up
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending | completed
    invoice_payload = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class UserBalance(Base):
    __tablename__ = "user_balances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    balance_rub = Column(Integer, default=0, nullable=False)
    total_earned_rub = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class GpxHash(Base):
    __tablename__ = "gpx_hashes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256 = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    territory_id = Column(UUID(as_uuid=True), ForeignKey("territories.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_id", "user_id"),
        Index("ix_transactions_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount_rub = Column(Integer, nullable=False)
    type = Column(String(50), nullable=False)  # "earned" | "payout"
    description = Column(String(500), nullable=True)
    sponsored_territory_id = Column(UUID(as_uuid=True), ForeignKey("sponsored_territories.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="completed")  # for payouts: "pending" | "completed"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
