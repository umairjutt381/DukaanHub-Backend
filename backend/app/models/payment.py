from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_id"),
        UniqueConstraint("merchant_transaction_id", name="uq_payments_merchant_transaction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    payment_method: Mapped[str] = mapped_column(String(40), index=True)
    gateway_name: Mapped[str] = mapped_column(String(80), index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    merchant_transaction_id: Mapped[str] = mapped_column(String(120), nullable=False)
    gateway_transaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    gateway_reference: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    response_code: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gateway_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order")
    attempts = relationship("PaymentAttempt", back_populates="payment", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempt_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    payment = relationship("Payment", back_populates="attempts")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("gateway_name", "gateway_event_id", name="uq_webhook_gateway_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gateway_name: Mapped[str] = mapped_column(String(80), index=True)
    gateway_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="received", index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    gateway_refund_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payment = relationship("Payment", back_populates="refunds")

