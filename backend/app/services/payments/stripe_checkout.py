from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus
from backend.app.services.payments.base import PaymentGateway, PaymentInitiationResult, PaymentVerificationResult


def amount_in_minor_units(amount: float) -> int:
    """Convert a two-decimal currency amount without float rounding errors."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class StripeGateway(PaymentGateway):
    def __init__(self) -> None:
        self.settings = get_settings()

    def _client(self):
        if not self.settings.stripe_secret_key:
            raise RuntimeError("Stripe is not configured")
        try:
            import stripe
        except ImportError as exc:  # pragma: no cover - covered in deployment setup
            raise RuntimeError("Stripe package is not installed. Run pip install -r backend/requirements.txt") from exc
        stripe.api_key = self.settings.stripe_secret_key
        return stripe

    def _url(self, configured_url: str, path: str) -> str:
        base = self.settings.frontend_base_url.rstrip("/")
        return configured_url or f"{base}{path}"

    async def initiate_payment(self, order, customer, **kwargs) -> PaymentInitiationResult:
        stripe = self._client()
        line_items = [
            {
                "price_data": {
                    "currency": order.currency.lower(),
                    "product_data": {"name": item.product_name},
                    "unit_amount": amount_in_minor_units(item.unit_price),
                },
                "quantity": item.quantity,
            }
            for item in order.items
        ]
        if order.shipping_charges:
            line_items.append(
                {
                    "price_data": {
                        "currency": order.currency.lower(),
                        "product_data": {"name": "Delivery"},
                        "unit_amount": amount_in_minor_units(order.shipping_charges),
                    },
                    "quantity": 1,
                }
            )
        if order.tax:
            line_items.append(
                {
                    "price_data": {
                        "currency": order.currency.lower(),
                        "product_data": {"name": "Tax"},
                        "unit_amount": amount_in_minor_units(order.tax),
                    },
                    "quantity": 1,
                }
            )

        discounts = []
        if order.discount_amount:
            coupon = stripe.Coupon.create(
                amount_off=amount_in_minor_units(order.discount_amount),
                currency=order.currency.lower(),
                duration="once",
                name=f"DukaanHub order discount {order.order_number}",
            )
            discounts = [{"coupon": coupon.id}]

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            customer_email=customer.email,
            client_reference_id=str(order.id),
            metadata={"order_id": str(order.id), "order_number": order.order_number},
            discounts=discounts,
            idempotency_key=f"dukaanhub-checkout-{order.idempotency_key or order.id}",
            success_url=f"{self._url(self.settings.stripe_success_url, '/order-success')}?order={order.order_number}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{self._url(self.settings.stripe_cancel_url, '/order-failed')}?order={order.order_number}",
        )
        return PaymentInitiationResult(
            gateway_name=GatewayName.STRIPE,
            payment_method=PaymentMethod.STRIPE,
            merchant_transaction_id=kwargs.get("merchant_transaction_id") or f"ST-{order.order_number}",
            payment_status=PaymentStatus.PENDING,
            order_status=OrderStatus.PENDING,
            amount=order.total_amount,
            currency=order.currency,
            redirect_url=session.url,
            gateway_transaction_id=session.id,
            gateway_reference=getattr(session, "payment_intent", None),
            response_message="Continue to Stripe's secure payment page.",
            raw_request={"order_id": order.id, "order_number": order.order_number},
            raw_response={"checkout_session_id": session.id},
        )

    async def verify_callback(self, payload, headers) -> PaymentVerificationResult:
        raise NotImplementedError("Stripe webhooks are verified from the raw signed request body")

    async def get_payment_status(self, transaction_id: str):
        stripe = self._client()
        session = stripe.checkout.Session.retrieve(transaction_id)
        return {"transaction_id": transaction_id, "status": session.payment_status}

    async def refund_payment(self, transaction_id: str, amount: float | None = None, reason: str | None = None):
        stripe = self._client()
        session = stripe.checkout.Session.retrieve(transaction_id)
        if not session.payment_intent:
            return {"status": "failed", "message": "Stripe payment intent is unavailable"}
        refund = stripe.Refund.create(
            payment_intent=session.payment_intent,
            amount=amount_in_minor_units(amount) if amount is not None else None,
            reason="requested_by_customer" if reason else None,
        )
        return {"status": refund.status, "gateway_refund_id": refund.id}
