from __future__ import annotations

from backend.app.domain.payments.enums import PaymentMethod
from backend.app.services.payments.base import PaymentGateway
from backend.app.services.payments.card import CardGateway
from backend.app.services.payments.cod import CashOnDeliveryService
from backend.app.services.payments.easypaisa import EasypaisaGateway
from backend.app.services.payments.jazzcash import JazzCashGateway
from backend.app.services.payments.stripe_checkout import StripeGateway


class PaymentGatewayFactory:
    @staticmethod
    def get_gateway(payment_method: str | PaymentMethod) -> PaymentGateway:
        method = PaymentMethod(payment_method)
        match method:
            case PaymentMethod.CASH_ON_DELIVERY:
                return CashOnDeliveryService()
            case PaymentMethod.JAZZCASH:
                return JazzCashGateway()
            case PaymentMethod.EASYPAISA:
                return EasypaisaGateway()
            case PaymentMethod.CARD:
                return CardGateway()
            case PaymentMethod.STRIPE:
                return StripeGateway()
        raise ValueError(f"Unsupported payment method: {payment_method}")
