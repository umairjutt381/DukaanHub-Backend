from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus


@dataclass(slots=True)
class PaymentInitiationResult:
    gateway_name: GatewayName
    payment_method: PaymentMethod
    merchant_transaction_id: str
    payment_status: PaymentStatus
    order_status: OrderStatus
    amount: float
    currency: str
    redirect_url: str | None = None
    redirect_form: dict[str, Any] | None = None
    gateway_transaction_id: str | None = None
    gateway_reference: str | None = None
    response_code: str | None = None
    response_message: str | None = None
    raw_request: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None


@dataclass(slots=True)
class PaymentVerificationResult:
    gateway_name: GatewayName
    payment_method: PaymentMethod
    merchant_transaction_id: str
    payment_status: PaymentStatus
    order_status: OrderStatus
    amount: float
    currency: str
    response_code: str | None = None
    response_message: str | None = None
    gateway_transaction_id: str | None = None
    gateway_reference: str | None = None
    failure_reason: str | None = None
    gateway_event_id: str | None = None
    paid_at: datetime | None = None
    raw_payload: dict[str, Any] | None = None
    raw_headers: dict[str, Any] | None = None


class PaymentGateway(ABC):
    @abstractmethod
    async def initiate_payment(self, order, customer, **kwargs) -> PaymentInitiationResult:
        raise NotImplementedError

    @abstractmethod
    async def verify_callback(self, payload, headers) -> PaymentVerificationResult:
        raise NotImplementedError

    @abstractmethod
    async def get_payment_status(self, transaction_id: str):
        raise NotImplementedError

    @abstractmethod
    async def refund_payment(self, transaction_id: str, amount: float | None = None, reason: str | None = None):
        raise NotImplementedError

