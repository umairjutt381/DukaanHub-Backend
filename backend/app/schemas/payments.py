from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus, WebhookProcessingStatus
from backend.app.schemas.common import PHONE_REGEX


class CheckoutRequest(BaseModel):
    shipping_address_id: int | None = None
    payment_method: PaymentMethod
    coupon_code: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=80)
    shipping_name: str | None = None
    shipping_phone: str | None = Field(default=None, pattern=PHONE_REGEX)
    shipping_address: str | None = None
    billing_address: str | None = None
    notes: str | None = None


class PaymentInitiateRequest(BaseModel):
    order_id: int
    payment_method: PaymentMethod
    idempotency_key: str | None = Field(default=None, max_length=80)


class PaymentRedirectResponse(BaseModel):
    order_id: int
    order_number: str
    payment_id: int
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    order_status: OrderStatus
    redirect_url: str | None = None
    redirect_form: dict | None = None
    message: str
    gateway_name: GatewayName | None = None
    transaction_id: str | None = None


class PaymentCallbackPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class PaymentStatusResponse(BaseModel):
    order_id: int
    order_number: str
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    order_status: OrderStatus
    gateway_name: str | None = None
    merchant_transaction_id: str | None = None
    gateway_transaction_id: str | None = None
    gateway_reference: str | None = None
    amount: float
    currency: str
    response_code: str | None = None
    response_message: str | None = None
    failure_reason: str | None = None
    paid_at: datetime | None = None


class RefundRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    reason: str = Field(min_length=3, max_length=500)


class RefundResponse(BaseModel):
    payment_id: int
    refund_id: int
    amount: float
    status: str
    gateway_refund_id: str | None = None


class CODCollectResponse(BaseModel):
    order_id: int
    payment_id: int
    payment_status: PaymentStatus
    order_status: OrderStatus
    message: str


class PaymentGatewayPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class PaymentAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    attempt_number: int
    status: str
    created_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    payment_method: str
    gateway_name: str
    amount: float
    currency: str
    status: str
    merchant_transaction_id: str
    gateway_transaction_id: str | None = None
    gateway_reference: str | None = None
    response_code: str | None = None
    response_message: str | None = None
    failure_reason: str | None = None
    paid_at: datetime | None = None
    attempts: list[PaymentAttemptRead] = Field(default_factory=list)


class WebhookEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    gateway_name: str
    gateway_event_id: str
    order_id: int | None = None
    payload_hash: str
    processing_status: WebhookProcessingStatus
    received_at: datetime
    processed_at: datetime | None = None
