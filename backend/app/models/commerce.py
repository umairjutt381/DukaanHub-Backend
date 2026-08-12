from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base


class Address(Base):
    __tablename__ = "addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(120), default="Pakistan")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    user = relationship("User", back_populates="addresses")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="wishlist_items")
    product = relationship("Product")


class CartItem(Base):
    __tablename__ = "cart_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product")


class Coupon(Base):
    __tablename__ = "coupons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    discount_type: Mapped[str] = mapped_column(String(20), default="percent")
    discount_value: Mapped[float] = mapped_column(Float, default=0)
    min_order_amount: Mapped[float] = mapped_column(Float, default=0)
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    payment_method: Mapped[str] = mapped_column(String(40), default="cash_on_delivery")
    payment_status: Mapped[str] = mapped_column(String(30), default="unpaid")
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    shipping_name: Mapped[str] = mapped_column(String(120), nullable=False)
    shipping_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    shipping_address: Mapped[str] = mapped_column(Text, nullable=False)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    shipping_charges: Mapped[float] = mapped_column(Float, default=0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(220), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    product = relationship("Product", back_populates="reviews")
    user = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="notifications")
