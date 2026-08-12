from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus, WebhookProcessingStatus
from backend.app.models import Order, Payment, Refund, WebhookEvent
from backend.app.services.payments.factory import PaymentGatewayFactory
from backend.app.services.payments.utils import redact_payload


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def _get_payment_by_order(self, order_id: int) -> Payment:
        payment = self.db.query(Payment).filter(Payment.order_id == order_id).first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment

    def get_status(self, order_id: int) -> dict:
        order = self.db.query(Order).options(selectinload(Order.items)).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        payment = self._get_payment_by_order(order_id)
        return {"order_id": order.id, "order_number": order.order_number, "payment_method": order.payment_method, "payment_status": payment.status, "order_status": order.status, "gateway_name": payment.gateway_name, "merchant_transaction_id": payment.merchant_transaction_id, "gateway_transaction_id": payment.gateway_transaction_id, "gateway_reference": payment.gateway_reference, "amount": payment.amount, "currency": payment.currency, "response_code": payment.response_code, "response_message": payment.response_message, "failure_reason": payment.failure_reason, "paid_at": payment.paid_at}

    def _record_webhook_event(self, gateway_name: GatewayName, gateway_event_id: str, order_id: int | None, payload: dict) -> WebhookEvent:
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        existing = self.db.query(WebhookEvent).filter(WebhookEvent.gateway_name == gateway_name.value, WebhookEvent.gateway_event_id == gateway_event_id).first()
        if existing:
            return existing
        event = WebhookEvent(gateway_name=gateway_name.value, gateway_event_id=gateway_event_id, order_id=order_id, payload_hash=payload_hash, processing_status=WebhookProcessingStatus.RECEIVED.value, payload=redact_payload(payload))
        self.db.add(event)
        self.db.flush()
        return event

    def _validate_callback_against_order(self, gateway_name: GatewayName, payload: dict, payment: Payment, order: Order) -> None:
        payload_amount = payload.get("pp_Amount") if gateway_name == GatewayName.JAZZCASH else payload.get("amount")
        payload_order = payload.get("pp_BillReference") if gateway_name == GatewayName.JAZZCASH else payload.get("orderId")
        payload_merchant = payload.get("pp_MerchantID") if gateway_name == GatewayName.JAZZCASH else payload.get("storeId")
        if gateway_name == GatewayName.JAZZCASH and str(payload_merchant or "") != self.settings.jazzcash_merchant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JazzCash merchant mismatch")
        if gateway_name == GatewayName.EASYPAISA and str(payload_merchant or "") != self.settings.easypaisa_store_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Easypaisa store mismatch")
        if payload_order and str(payload_order) != str(order.order_number):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order reference mismatch")
        if payload_amount is not None:
            raw_amount = float(payload_amount)
            normalized_amount = raw_amount / 100.0 if gateway_name in {GatewayName.JAZZCASH, GatewayName.EASYPAISA} else raw_amount
            if round(normalized_amount, 2) != round(payment.amount, 2) and round(raw_amount / 100.0, 2) != round(payment.amount, 2):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount mismatch")

    async def verify_and_apply_callback(self, gateway_name: GatewayName, payload: dict, headers: dict | None = None) -> dict:
        gateway = PaymentGatewayFactory.get_gateway(gateway_name)
        verification = await gateway.verify_callback(payload, headers or {})
        payment = self.db.query(Payment).filter(Payment.merchant_transaction_id == verification.merchant_transaction_id).with_for_update().first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        order = self.db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        event_id = verification.gateway_event_id or verification.merchant_transaction_id or payment.merchant_transaction_id
        webhook = self._record_webhook_event(gateway_name, event_id, order.id, payload)
        if webhook.processing_status == WebhookProcessingStatus.PROCESSED.value:
            return self.get_status(order.id)
        if payment.status in {PaymentStatus.PAID.value, PaymentStatus.REFUNDED.value, PaymentStatus.PARTIALLY_REFUNDED.value} and verification.payment_status != PaymentStatus.PAID:
            webhook.processing_status = WebhookProcessingStatus.IGNORED.value
            webhook.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            return self.get_status(order.id)
        self._validate_callback_against_order(gateway_name, verification.raw_payload or payload, payment, order)
        payment.status = verification.payment_status.value
        payment.gateway_transaction_id = verification.gateway_transaction_id or payment.gateway_transaction_id
        payment.gateway_reference = verification.gateway_reference or payment.gateway_reference
        payment.response_code = verification.response_code
        payment.response_message = verification.response_message
        payment.failure_reason = verification.failure_reason
        payment.paid_at = verification.paid_at or (datetime.now(timezone.utc) if verification.payment_status == PaymentStatus.PAID else None)
        order.status = verification.order_status.value
        order.payment_status = verification.payment_status.value
        webhook.processing_status = WebhookProcessingStatus.PROCESSED.value if verification.payment_status == PaymentStatus.PAID else WebhookProcessingStatus.FAILED.value
        webhook.processed_at = datetime.now(timezone.utc)
        webhook.payload = redact_payload(payload)
        self.db.commit()
        return self.get_status(order.id)

    def apply_stripe_event(self, event: dict) -> dict:
        """Apply a Stripe event after its signature has been verified by the router."""
        event_id = str(event.get("id") or "")
        event_type = str(event.get("type") or "")
        session = dict(event.get("data", {}).get("object") or {})
        session_id = str(session.get("id") or "")
        if not event_id or not session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe event")

        payment = self.db.query(Payment).filter(
            Payment.gateway_name == GatewayName.STRIPE.value,
            Payment.gateway_transaction_id == session_id,
        ).with_for_update().first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stripe payment not found")
        order = self.db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        webhook = self._record_webhook_event(GatewayName.STRIPE, event_id, order.id, event)
        if webhook.processing_status == WebhookProcessingStatus.PROCESSED.value:
            return self.get_status(order.id)

        paid_events = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
        failed_events = {"checkout.session.async_payment_failed", "checkout.session.expired"}
        if event_type in paid_events and session.get("payment_status") == "paid":
            payment.status = PaymentStatus.PAID.value
            payment.paid_at = datetime.now(timezone.utc)
            payment.gateway_reference = str(session.get("payment_intent") or payment.gateway_reference or "") or None
            payment.response_code = "paid"
            payment.response_message = "Stripe payment succeeded"
            order.payment_status = PaymentStatus.PAID.value
            order.status = OrderStatus.CONFIRMED.value
            webhook.processing_status = WebhookProcessingStatus.PROCESSED.value
        elif event_type in failed_events:
            payment.status = PaymentStatus.FAILED.value if event_type.endswith("failed") else PaymentStatus.EXPIRED.value
            payment.failure_reason = f"Stripe event: {event_type}"
            payment.response_code = event_type
            order.payment_status = payment.status
            order.status = OrderStatus.PENDING.value
            webhook.processing_status = WebhookProcessingStatus.FAILED.value
        else:
            webhook.processing_status = WebhookProcessingStatus.IGNORED.value
        webhook.processed_at = datetime.now(timezone.utc)
        webhook.payload = redact_payload(event)
        self.db.commit()
        return self.get_status(order.id)

    def mark_cod_collected(self, order_id: int) -> dict:
        order = self.db.query(Order).with_for_update().filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        payment = self._get_payment_by_order(order.id)
        if payment.payment_method != PaymentMethod.CASH_ON_DELIVERY.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not cash on delivery")
        payment.status = PaymentStatus.PAID.value
        payment.paid_at = datetime.now(timezone.utc)
        order.payment_status = PaymentStatus.PAID.value
        order.status = OrderStatus.DELIVERED.value
        self.db.commit()
        return self.get_status(order.id)

    async def refund_payment(self, payment_id: int, amount: float | None, reason: str) -> dict:
        payment = self.db.query(Payment).with_for_update().filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        refund_amount = amount or payment.amount
        if refund_amount <= 0 or refund_amount > payment.amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refund amount")
        if payment.status not in {PaymentStatus.PAID.value, PaymentStatus.PARTIALLY_REFUNDED.value}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only paid payments can be refunded")
        gateway = PaymentGatewayFactory.get_gateway(payment.payment_method)
        gateway_response = {"message": "Refund pending", "gateway": payment.gateway_name}
        if payment.gateway_name != GatewayName.CASH_ON_DELIVERY.value:
            gateway_response = await gateway.refund_payment(payment.merchant_transaction_id, refund_amount, reason)
        refund_status = str(gateway_response.get("status") or "pending")
        refund = Refund(payment_id=payment.id, amount=refund_amount, reason=reason, status=refund_status, gateway_refund_id=gateway_response.get("gateway_refund_id"))
        self.db.add(refund)
        payment.status = PaymentStatus.REFUNDED.value if refund_amount == payment.amount else PaymentStatus.PARTIALLY_REFUNDED.value
        payment.failure_reason = None
        self.db.commit()
        return {"payment_id": payment.id, "refund_id": refund.id, "amount": refund.amount, "status": refund.status, "gateway_refund_id": refund.gateway_refund_id, "gateway_response": gateway_response}
