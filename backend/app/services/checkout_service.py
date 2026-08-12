from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import GatewayName, OrderStatus, PaymentMethod, PaymentStatus
from backend.app.models import Address, CartItem, Coupon, Notification, Order, OrderItem, Payment, PaymentAttempt, Product, User
from backend.app.schemas.commerce import OrderCreate
from backend.app.schemas.payments import PaymentRedirectResponse
from backend.app.services.idempotency_service import IdempotencyService
from backend.app.services.payment_settings import get_payment_method_enabled
from backend.app.services.payments.factory import PaymentGatewayFactory
from backend.app.services.payments.utils import redact_payload


@dataclass(slots=True)
class CheckoutContext:
    order: Order
    payment: Payment | None
    redirect_url: str | None = None
    redirect_form: dict | None = None


class CheckoutService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def _resolve_shipping(self, user: User, payload: OrderCreate) -> tuple[str, str, str, str | None]:
        if payload.shipping_address_id:
            address = self.db.get(Address, payload.shipping_address_id)
            if not address or address.user_id != user.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid shipping address")
            return address.full_name, address.phone, f"{address.line1}{f', {address.line2}' if address.line2 else ''}, {address.city}, {address.country}", None
        if not payload.shipping_name or not payload.shipping_phone or not payload.shipping_address:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shipping information is required")
        return payload.shipping_name, payload.shipping_phone, payload.shipping_address, payload.billing_address

    def _build_totals(self, user: User, payload: OrderCreate):
        cart_items = self.db.query(CartItem).filter(CartItem.user_id == user.id).all()
        if not cart_items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        subtotal = 0.0
        order_items = []
        product_ids = [item.product_id for item in cart_items]
        products = self.db.execute(select(Product).where(Product.id.in_(product_ids)).with_for_update()).scalars().all()
        products_by_id = {product.id: product for product in products}

        for item in cart_items:
            product = products_by_id.get(item.product_id)
            if not product or not product.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product {item.product_id} is unavailable")
            if product.stock < item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for {product.name}")
            line_total = product.price * item.quantity
            subtotal += line_total
            order_items.append((product, item.quantity, line_total))

        discount = 0.0
        if payload.coupon_code:
            coupon = self.db.query(Coupon).filter(Coupon.code == payload.coupon_code.upper(), Coupon.is_active == True).first()  # noqa: E712
            if coupon and subtotal >= coupon.min_order_amount:
                raw_discount = subtotal * (coupon.discount_value / 100.0) if coupon.discount_type == "percent" else coupon.discount_value
                discount = min(raw_discount, coupon.max_discount_amount) if coupon.max_discount_amount else raw_discount

        shipping_fee = self.settings.payment_shipping_fee
        tax = round(subtotal * self.settings.payment_tax_rate, 2)
        total = round(max(subtotal - discount, 0) + tax + shipping_fee, 2)
        return subtotal, discount, shipping_fee, tax, total, order_items

    def _get_or_create_order(self, user: User, payload: OrderCreate, idempotency_key: str | None) -> Order | None:
        return IdempotencyService(self.db).get_order(user.id, idempotency_key or "")

    async def checkout(self, user: User, payload: OrderCreate, idempotency_key: str | None = None) -> PaymentRedirectResponse:
        payment_method = PaymentMethod(payload.payment_method)
        if not get_payment_method_enabled(self.db, payment_method):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{payment_method.value} is currently disabled")
        existing_order = self._get_or_create_order(user, payload, idempotency_key)
        if existing_order:
            payment = self.db.query(Payment).filter(Payment.order_id == existing_order.id).first()
            if not payment:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already exists without payment record")
            return self._to_response(existing_order, payment)

        shipping_name, shipping_phone, shipping_address, billing_address = self._resolve_shipping(user, payload)
        subtotal, discount, shipping_fee, tax, total, order_items = self._build_totals(user, payload)
        if not idempotency_key:
            idempotency_key = uuid.uuid4().hex

        gateway = PaymentGatewayFactory.get_gateway(payment_method)
        order_status = OrderStatus.CONFIRMED if payment_method == PaymentMethod.CASH_ON_DELIVERY else OrderStatus.PENDING
        payment_status = PaymentStatus.PENDING
        order = Order(
            order_number=f"DH-{uuid.uuid4().hex[:10].upper()}",
            user_id=user.id,
            status=order_status.value,
            payment_method=payment_method.value,
            payment_status=payment_status.value,
            currency=self.settings.payment_currency,
            idempotency_key=idempotency_key,
            shipping_name=shipping_name,
            shipping_phone=shipping_phone,
            shipping_address=shipping_address,
            billing_address=billing_address,
            subtotal=subtotal,
            tax=tax,
            shipping_charges=shipping_fee,
            discount_amount=discount,
            total_amount=total,
            notes=payload.notes,
        )
        self.db.add(order)
        self.db.flush()

        for product, quantity, line_total in order_items:
            self.db.add(OrderItem(order_id=order.id, product_id=product.id, product_name=product.name, product_sku=product.sku, unit_price=product.price, quantity=quantity, total_price=line_total))
            product.stock -= quantity

        payment = Payment(
            order_id=order.id,
            payment_method=payment_method.value,
            gateway_name=payment_method.value,
            amount=total,
            currency=self.settings.payment_currency,
            status=payment_status.value,
            merchant_transaction_id=f"{payment_method.value[:2].upper()}{uuid.uuid4().hex[:18].upper()}",
        )
        self.db.add(payment)
        self.db.flush()
        self.db.add(PaymentAttempt(payment_id=payment.id, attempt_number=1, request_payload={"payment_method": payment_method.value, "idempotency_key": idempotency_key}, response_payload=None, status="pending"))
        self.db.add(Notification(user_id=user.id, title="Order placed", body=f"Your order {order.order_number} has been placed."))

        if payment_method == PaymentMethod.CASH_ON_DELIVERY:
            self.db.query(CartItem).filter(CartItem.user_id == user.id).delete()
            self.db.commit()
            self.db.refresh(order)
            self.db.refresh(payment)
            return self._to_response(order, payment, message="Cash on delivery order confirmed")

        initiation = await gateway.initiate_payment(order, user, merchant_transaction_id=payment.merchant_transaction_id)
        payment.gateway_name = initiation.gateway_name.value
        payment.gateway_transaction_id = initiation.gateway_transaction_id
        payment.gateway_reference = initiation.gateway_reference
        payment.response_code = initiation.response_code
        payment.response_message = initiation.response_message
        payment.gateway_payload = redact_payload(initiation.raw_request)
        payment.gateway_response = redact_payload(initiation.raw_response)
        payment.status = initiation.payment_status.value
        order.status = initiation.order_status.value
        order.payment_status = initiation.payment_status.value
        self.db.add(PaymentAttempt(payment_id=payment.id, attempt_number=2, request_payload=redact_payload(initiation.raw_request), response_payload=redact_payload(initiation.raw_response), status=payment.status))
        self.db.query(CartItem).filter(CartItem.user_id == user.id).delete()
        self.db.commit()
        self.db.refresh(order)
        self.db.refresh(payment)
        return self._to_response(order, payment, initiation.redirect_url, initiation.redirect_form, initiation.response_message, initiation.gateway_name, initiation.merchant_transaction_id)

    def _to_response(
        self,
        order: Order,
        payment: Payment | None,
        redirect_url: str | None = None,
        redirect_form: dict | None = None,
        message: str | None = None,
        gateway_name: GatewayName | None = None,
        transaction_id: str | None = None,
    ) -> PaymentRedirectResponse:
        return PaymentRedirectResponse(
            order_id=order.id,
            order_number=order.order_number,
            payment_id=payment.id if payment else 0,
            payment_method=PaymentMethod(order.payment_method),
            payment_status=PaymentStatus(payment.status if payment else order.payment_status),
            order_status=OrderStatus(order.status),
            redirect_url=redirect_url,
            redirect_form=redirect_form,
            message=message or "Checkout completed",
            gateway_name=gateway_name or (GatewayName(payment.gateway_name) if payment else None),
            transaction_id=transaction_id or (payment.merchant_transaction_id if payment else None),
        )

