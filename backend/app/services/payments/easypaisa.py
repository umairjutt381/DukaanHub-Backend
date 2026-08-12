from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus
from backend.app.services.payments.base import PaymentGateway, PaymentInitiationResult, PaymentVerificationResult
from backend.app.services.payments.easypaisa_signature import build_easypaisa_signature, verify_easypaisa_signature


class EasypaisaGateway(PaymentGateway):
    def __init__(self):
        self.settings = get_settings()

    def _ensure_configured(self) -> None:
        required = {
            "EASYPAISA_STORE_ID": self.settings.easypaisa_store_id,
            "EASYPAISA_USERNAME": self.settings.easypaisa_username,
            "EASYPAISA_PASSWORD": self.settings.easypaisa_password,
            "EASYPAISA_HASH_KEY": self.settings.easypaisa_hash_key,
            "EASYPAISA_PAYMENT_URL": self.settings.easypaisa_payment_url,
            "EASYPAISA_RETURN_URL": self.settings.easypaisa_return_url,
            "EASYPAISA_CALLBACK_URL": self.settings.easypaisa_callback_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Easypaisa is not configured: {', '.join(missing)}")

    async def initiate_payment(self, order, customer, **kwargs) -> PaymentInitiationResult:
        self._ensure_configured()
        txn_ref = kwargs.get("merchant_transaction_id") or f"EP{order.order_number}"
        payload = {
            "storeId": self.settings.easypaisa_store_id,
            "transactionId": txn_ref,
            "amount": str(int(round(order.total_amount * 100))),
            "orderId": order.order_number,
            "currency": order.currency,
            "customerEmail": getattr(customer, "email", ""),
            "customerName": getattr(customer, "full_name", ""),
            "returnUrl": self.settings.easypaisa_return_url,
            "callbackUrl": self.settings.easypaisa_callback_url,
        }
        payload["hash"] = build_easypaisa_signature(payload, self.settings.easypaisa_hash_key)
        return PaymentInitiationResult(
            gateway_name=GatewayName.EASYPAISA,
            payment_method=PaymentMethod.EASYPAISA,
            merchant_transaction_id=txn_ref,
            payment_status=PaymentStatus.PENDING,
            order_status=OrderStatus.PENDING,
            amount=order.total_amount,
            currency=order.currency,
            redirect_url=self.settings.easypaisa_payment_url,
            redirect_form=payload,
            response_message="Redirect customer to Easypaisa hosted payment page",
            raw_request=payload,
        )

    async def verify_callback(self, payload, headers) -> PaymentVerificationResult:
        self._ensure_configured()
        data = dict(payload)
        provided_signature = data.pop("hash", "") or data.pop("signature", "")
        if not provided_signature or not verify_easypaisa_signature(data, self.settings.easypaisa_hash_key, provided_signature):
            return PaymentVerificationResult(
                gateway_name=GatewayName.EASYPAISA,
                payment_method=PaymentMethod.EASYPAISA,
                merchant_transaction_id=str(data.get("transactionId") or data.get("orderId") or ""),
                payment_status=PaymentStatus.FAILED,
                order_status=OrderStatus.FAILED_DELIVERY,
                amount=float(data.get("amount") or 0) / 100.0,
                currency=str(data.get("currency") or "PKR"),
                response_code=str(data.get("responseCode") or ""),
                response_message="Invalid signature",
                failure_reason="Invalid signature",
                raw_payload=data,
                raw_headers=dict(headers or {}),
            )

        response_code = str(data.get("responseCode") or "")
        success = response_code == "000"
        return PaymentVerificationResult(
            gateway_name=GatewayName.EASYPAISA,
            payment_method=PaymentMethod.EASYPAISA,
            merchant_transaction_id=str(data.get("transactionId") or data.get("orderId") or ""),
            payment_status=PaymentStatus.PAID if success else PaymentStatus.FAILED,
            order_status=OrderStatus.CONFIRMED if success else OrderStatus.FAILED_DELIVERY,
            amount=float(data.get("amount") or 0) / 100.0,
            currency=str(data.get("currency") or "PKR"),
            response_code=response_code,
            response_message=str(data.get("responseMessage") or ""),
            gateway_transaction_id=str(data.get("gatewayReference") or data.get("trxId") or "") or None,
            gateway_reference=str(data.get("gatewayReference") or data.get("trxId") or "") or None,
            failure_reason=None if success else str(data.get("responseMessage") or "Payment failed"),
            gateway_event_id=str(data.get("transactionId") or data.get("orderId") or "") or None,
            paid_at=datetime.now(timezone.utc) if success else None,
            raw_payload=data,
            raw_headers=dict(headers or {}),
        )

    async def get_payment_status(self, transaction_id: str):
        self._ensure_configured()
        async with httpx.AsyncClient(timeout=self.settings.payment_gateway_timeout_seconds) as client:
            _ = client
        return {"transaction_id": transaction_id, "status": "unknown"}

    async def refund_payment(self, transaction_id: str, amount: float | None = None, reason: str | None = None):
        self._ensure_configured()
        return {"transaction_id": transaction_id, "status": "pending", "message": "Easypaisa refund API integration must follow the latest merchant guide."}

