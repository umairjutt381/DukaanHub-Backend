from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus
from backend.app.services.payments.base import PaymentGateway, PaymentInitiationResult, PaymentVerificationResult
from backend.app.services.payments.jazzcash_hash import build_jazzcash_secure_hash, verify_jazzcash_secure_hash


class JazzCashGateway(PaymentGateway):
    def __init__(self):
        self.settings = get_settings()

    def _ensure_configured(self) -> None:
        required = {
            "JAZZCASH_MERCHANT_ID": self.settings.jazzcash_merchant_id,
            "JAZZCASH_PASSWORD": self.settings.jazzcash_password,
            "JAZZCASH_INTEGRITY_SALT": self.settings.jazzcash_integrity_salt,
            "JAZZCASH_PAYMENT_URL": self.settings.jazzcash_payment_url,
            "JAZZCASH_RETURN_URL": self.settings.jazzcash_return_url,
            "JAZZCASH_CALLBACK_URL": self.settings.jazzcash_callback_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"JazzCash is not configured: {', '.join(missing)}")

    async def initiate_payment(self, order, customer, **kwargs) -> PaymentInitiationResult:
        self._ensure_configured()
        txn_ref = kwargs.get("merchant_transaction_id") or f"JC{order.order_number}"
        tx_datetime = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        payload = {
            "pp_Version": "1.1",
            "pp_TxnType": "MPAY",
            "pp_Language": "EN",
            "pp_MerchantID": self.settings.jazzcash_merchant_id,
            "pp_Password": self.settings.jazzcash_password,
            "pp_TxnRefNo": txn_ref,
            "pp_Amount": str(int(round(order.total_amount * 100))),
            "pp_TxnCurrency": order.currency,
            "pp_TxnDateTime": tx_datetime,
            "pp_BillReference": order.order_number,
            "pp_Description": f"Order {order.order_number}",
            "pp_ReturnURL": self.settings.jazzcash_return_url,
            "pp_CallbackURL": self.settings.jazzcash_callback_url,
            "pp_SecureHash": "",
        }
        payload["pp_SecureHash"] = build_jazzcash_secure_hash(payload, self.settings.jazzcash_integrity_salt)
        return PaymentInitiationResult(
            gateway_name=GatewayName.JAZZCASH,
            payment_method=PaymentMethod.JAZZCASH,
            merchant_transaction_id=txn_ref,
            payment_status=PaymentStatus.PENDING,
            order_status=OrderStatus.PENDING,
            amount=order.total_amount,
            currency=order.currency,
            redirect_url=self.settings.jazzcash_payment_url,
            redirect_form=payload,
            response_message="Redirect customer to JazzCash hosted payment page",
            raw_request=payload,
        )

    async def verify_callback(self, payload, headers) -> PaymentVerificationResult:
        self._ensure_configured()
        data = dict(payload)
        provided_hash = data.pop("pp_SecureHash", "") or data.pop("secureHash", "")
        if not provided_hash or not verify_jazzcash_secure_hash(data, self.settings.jazzcash_integrity_salt, provided_hash):
            return PaymentVerificationResult(
                gateway_name=GatewayName.JAZZCASH,
                payment_method=PaymentMethod.JAZZCASH,
                merchant_transaction_id=str(data.get("pp_TxnRefNo") or data.get("txnRefNo") or ""),
                payment_status=PaymentStatus.FAILED,
                order_status=OrderStatus.FAILED_DELIVERY,
                amount=float(data.get("pp_Amount") or 0) / 100.0,
                currency=str(data.get("pp_TxnCurrency") or "PKR"),
                response_code=str(data.get("responseCode") or ""),
                response_message="Invalid secure hash",
                failure_reason="Invalid secure hash",
                raw_payload=data,
                raw_headers=dict(headers or {}),
            )

        response_code = str(data.get("responseCode") or data.get("pp_ResponseCode") or "")
        success = response_code == "000"
        return PaymentVerificationResult(
            gateway_name=GatewayName.JAZZCASH,
            payment_method=PaymentMethod.JAZZCASH,
            merchant_transaction_id=str(data.get("pp_TxnRefNo") or data.get("txnRefNo") or ""),
            payment_status=PaymentStatus.PAID if success else PaymentStatus.FAILED,
            order_status=OrderStatus.CONFIRMED if success else OrderStatus.FAILED_DELIVERY,
            amount=float(data.get("pp_Amount") or 0) / 100.0,
            currency=str(data.get("pp_TxnCurrency") or "PKR"),
            response_code=response_code,
            response_message=str(data.get("responseMessage") or data.get("pp_ResponseMessage") or ""),
            gateway_transaction_id=str(data.get("pp_RetrievalReferenceNo") or data.get("gatewayReference") or "") or None,
            gateway_reference=str(data.get("pp_RetrievalReferenceNo") or data.get("gatewayReference") or "") or None,
            failure_reason=None if success else str(data.get("responseMessage") or "Payment failed"),
            gateway_event_id=str(data.get("pp_TxnRefNo") or data.get("txnRefNo") or "") or None,
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
        return {"transaction_id": transaction_id, "status": "pending", "message": "JazzCash refund API integration must follow the latest merchant guide."}

