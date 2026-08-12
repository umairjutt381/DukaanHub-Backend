from __future__ import annotations

from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus
from backend.app.services.payments.base import PaymentGateway, PaymentInitiationResult, PaymentVerificationResult


class CashOnDeliveryService(PaymentGateway):
    async def initiate_payment(self, order, customer, **kwargs) -> PaymentInitiationResult:
        return PaymentInitiationResult(
            gateway_name=GatewayName.CASH_ON_DELIVERY,
            payment_method=PaymentMethod.CASH_ON_DELIVERY,
            merchant_transaction_id=f"COD-{order.order_number}",
            payment_status=PaymentStatus.PENDING,
            order_status=OrderStatus.CONFIRMED,
            amount=order.total_amount,
            currency=order.currency,
            response_code="COD",
            response_message="Cash on delivery selected",
        )

    async def verify_callback(self, payload, headers) -> PaymentVerificationResult:
        raise NotImplementedError("COD does not use gateway callbacks")

    async def get_payment_status(self, transaction_id: str):
        return {"status": PaymentStatus.PENDING, "transaction_id": transaction_id}

    async def refund_payment(self, transaction_id: str, amount: float | None = None, reason: str | None = None):
        return {"status": PaymentStatus.FAILED, "transaction_id": transaction_id, "message": "COD refunds are manual"}

