import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.models import CartItem, Coupon, Notification, Order, OrderItem, Product, User
from backend.app.domain.payments.enums import PaymentMethod
from backend.app.services.payment_settings import get_delivery_charge_amount


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def create_order(self, user: User, payload, shipping_charges: float | None = None, tax_rate: float = 0.05) -> Order:
        cart_items = self.db.query(CartItem).filter(CartItem.user_id == user.id).all()
        if not cart_items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        subtotal = 0.0
        items_payload = []
        for item in cart_items:
            product = self.db.get(Product, item.product_id)
            if not product or product.stock < item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for {product.name if product else item.product_id}")
            line_total = product.price * item.quantity
            subtotal += line_total
            items_payload.append((product, item.quantity, line_total))

        coupon_discount = 0.0
        if payload.coupon_code:
            coupon = self.db.query(Coupon).filter(Coupon.code == payload.coupon_code.upper(), Coupon.is_active == True).first()  # noqa: E712
            if coupon:
                if subtotal >= coupon.min_order_amount:
                    raw = subtotal * (coupon.discount_value / 100.0) if coupon.discount_type == "percent" else coupon.discount_value
                    coupon_discount = min(raw, coupon.max_discount_amount) if coupon.max_discount_amount else raw

        if shipping_charges is None:
            shipping_charges = get_delivery_charge_amount(self.db)
        tax = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax + shipping_charges - coupon_discount, 2)
        order = Order(
            order_number=f"DH-{uuid.uuid4().hex[:10].upper()}",
            user_id=user.id,
            status="pending",
            payment_method=payload.payment_method.value,
            payment_status="pending" if payload.payment_method == PaymentMethod.CASH_ON_DELIVERY else "unpaid",
            shipping_name=payload.shipping_name,
            shipping_phone=payload.shipping_phone,
            shipping_address=payload.shipping_address,
            billing_address=payload.billing_address,
            notes=payload.notes,
            subtotal=subtotal,
            tax=tax,
            shipping_charges=shipping_charges,
            discount_amount=coupon_discount,
            total_amount=total,
        )
        self.db.add(order)
        self.db.flush()
        for product, qty, line_total in items_payload:
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_sku=product.sku,
                    unit_price=product.price,
                    quantity=qty,
                    total_price=line_total,
                )
            )
            product.stock -= qty
        self.db.query(CartItem).filter(CartItem.user_id == user.id).delete()
        self.db.add(Notification(user_id=user.id, title="Order placed", body=f"Your order {order.order_number} has been placed."))
        self.db.commit()
        self.db.refresh(order)
        return self.db.query(Order).options(selectinload(Order.items)).filter(Order.id == order.id).first()
