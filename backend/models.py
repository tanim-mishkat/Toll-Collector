"""ORM models for vehicles and toll events."""
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    plate: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_name: Mapped[str] = mapped_column(String(128), default="UNKNOWN")
    phone: Mapped[str] = mapped_column(String(20), default="")
    nid: Mapped[str] = mapped_column(String(20), default="")
    vehicle_class: Mapped[str] = mapped_column(String(16), default="unknown")
    balance_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    brta_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    registered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    events: Mapped[list["TollEvent"]] = relationship(
        back_populates="vehicle", cascade="all,delete-orphan"
    )


class TollEvent(Base):
    __tablename__ = "toll_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate: Mapped[str] = mapped_column(
        String(32), ForeignKey("vehicles.plate"), index=True
    )
    gantry_id: Mapped[str] = mapped_column(String(32))
    amount_bdt: Mapped[float] = mapped_column(Float)
    late_fee_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    fine_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="UNPAID")
    # UNPAID | REMINDED | LATE | FINED | BLOCKED | PAID
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    vehicle: Mapped[Vehicle] = relationship(back_populates="events")


class SmsMessage(Base):
    """Mocked outbound SMS (and Telegram mirror). Every notification the
    system would send to a real telco goes here first, so the dashboard
    can show what the driver 'receives'."""
    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    to_phone: Mapped[str] = mapped_column(String(20), index=True)
    plate: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(24))
    # TOLL_NOTICE | PAYMENT_CONFIRMATION | REMINDER | LATE_FEE | FINE | BRTA_BLOCK
    body: Mapped[str] = mapped_column(String(480))
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
