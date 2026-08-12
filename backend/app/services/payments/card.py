from __future__ import annotations

from datetime import datetime, timezone

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus
from backend.app.services.payments.base import PaymentGateway, PaymentInitiationResult, PaymentVerificationResult


class CardGateway(PaymentGateway):
    def __init__(self):
        self.settings = get_settings()

    def _ensure_configured(self) -> None:
        if not self.settings.card_payment_url:
            raise RuntimeError("Card gateway is not configured")

    async def initiate_payment(self, order, customer, **kwargs) -> PaymentInitiationResult:
        self._ensure_configured()
        txn_ref = kwargs.get("merchant_transaction_id") or f"CC{order.order_number}"
        payload = {
            "merchant_transaction_id": txn_ref,
            "order_number": order.order_number,
            "amount": str(int(round(order.total_amount * 100))),
            "currency": order.currency,
            "return_url": self.settings.card_return_url,
            "callback_url": self.settings.card_callback_url,
        }
        return PaymentInitiationResult(
            gateway_name=GatewayName.CARD,
            payment_method=PaymentMethod.CARD,
            merchant_transaction_id=txn_ref,
            payment_status=PaymentStatus.PENDING,
            order_status=OrderStatus.PENDING,
            amount=order.total_amount,
            currency=order.currency,
            redirect_url=self.settings.card_payment_url,
            redirect_form=payload,
            response_message="Redirect customer to hosted card checkout",
            raw_request=payload,
        )

    async def verify_callback(self, payload, headers) -> PaymentVerificationResult:
        data = dict(payload)
        response_code = str(data.get("responseCode") or data.get("status") or "")
        success = response_code in {"000", "success", "succeeded", "paid"}
        return PaymentVerificationResult(
            gateway_name=GatewayName.CARD,
            payment_method=PaymentMethod.CARD,
            merchant_transaction_id=str(data.get("merchant_transaction_id") or data.get("order_number") or ""),
            payment_status=PaymentStatus.PAID if success else PaymentStatus.FAILED,
            order_status=OrderStatus.CONFIRMED if success else OrderStatus.FAILED_DELIVERY,
            amount=float(data.get("amount") or 0) / 100.0 if str(data.get("amount") or "").isdigit() else float(data.get("amount") or 0),
            currency=str(data.get("currency") or "PKR"),
            response_code=response_code,
            response_message=str(data.get("responseMessage") or data.get("message") or ""),
            gateway_transaction_id=str(data.get("gateway_transaction_id") or data.get("gatewayReference") or "") or None,
            gateway_reference=str(data.get("gatewayReference") or data.get("gateway_transaction_id") or "") or None,
            failure_reason=None if success else str(data.get("failure_reason") or data.get("message") or "Payment failed"),
            gateway_event_id=str(data.get("event_id") or data.get("gateway_transaction_id") or "") or None,
            paid_at=datetime.now(timezone.utc) if success else None,
            raw_payload=data,
            raw_headers=dict(headers or {}),
        )

    async def get_payment_status(self, transaction_id: str):
        return {"transaction_id": transaction_id, "status": "unknown"}

    async def refund_payment(self, transaction_id: str, amount: float | None = None, reason: str | None = None):
        return {"transaction_id": transaction_id, "status": "pending", "message": "Card refund integration depends on the selected gateway."}

