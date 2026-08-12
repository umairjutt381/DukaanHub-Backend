import asyncio

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.db.migrations import apply_compatibility_migrations
from backend.app.domain.payments.enums import PaymentMethod
from backend.app.models import CartItem, Order, Payment, Product, User
from backend.app.domain.payments.enums import GatewayName
from backend.app.services.payment_service import PaymentService
from backend.app.services.payments.stripe_checkout import amount_in_minor_units
from backend.app.schemas.payments import CheckoutRequest
from backend.app.services.checkout_service import CheckoutService


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_cod_checkout_is_idempotent_and_uses_canonical_payment_method(db: Session) -> None:
    customer = User(full_name="Checkout customer", email="checkout@example.com", hashed_password="not-used")
    product = Product(
        name="Checkout product", slug="checkout-product", sku="CHECKOUT-1",
        description="A product used to verify checkout.", price=1000, stock=3,
    )
    db.add_all([customer, product])
    db.flush()
    db.add(CartItem(user_id=customer.id, product_id=product.id, quantity=2))
    db.commit()

    request = CheckoutRequest(
        payment_method=PaymentMethod.CASH_ON_DELIVERY,
        shipping_name="Checkout customer",
        shipping_phone="03001234567",
        shipping_address="Test street, Lahore",
        idempotency_key="checkout-test-key",
    )

    first = asyncio.run(CheckoutService(db).checkout(customer, request, request.idempotency_key))
    second = asyncio.run(CheckoutService(db).checkout(customer, request, request.idempotency_key))

    assert first.order_id == second.order_id
    order = db.get(Order, first.order_id)
    assert order is not None
    assert order.payment_method == PaymentMethod.CASH_ON_DELIVERY.value
    assert order.currency == "PKR"
    assert order.idempotency_key == "checkout-test-key"
    assert order.payment_status == "pending"
    assert db.query(CartItem).filter(CartItem.user_id == customer.id).count() == 0
    db.refresh(product)
    assert product.stock == 1


def test_compatibility_migration_upgrades_legacy_order_records(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, payment_method VARCHAR(40))"))
        connection.execute(text("INSERT INTO orders (id, payment_method) VALUES (1, 'cod')"))

    apply_compatibility_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("orders")}
    assert {"currency", "idempotency_key"}.issubset(columns)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT payment_method, currency FROM orders WHERE id = 1")).one()
    assert row == ("cash_on_delivery", "PKR")
    engine.dispose()


def test_stripe_payment_event_marks_the_matching_order_paid(db: Session) -> None:
    customer = User(full_name="Stripe customer", email="stripe@example.com", hashed_password="not-used")
    db.add(customer)
    db.flush()
    order = Order(
        order_number="DH-STRIPE-TEST", user_id=customer.id, payment_method="stripe",
        shipping_name="Stripe customer", shipping_phone="03001234567", shipping_address="Test street",
        total_amount=1000, currency="PKR",
    )
    db.add(order)
    db.flush()
    db.add(Payment(
        order_id=order.id, payment_method="stripe", gateway_name=GatewayName.STRIPE.value,
        amount=1000, currency="PKR", merchant_transaction_id="ST-TEST", gateway_transaction_id="cs_test_123",
    ))
    db.commit()

    result = PaymentService(db).apply_stripe_event({
        "id": "evt_test_123", "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_123", "payment_status": "paid", "payment_intent": "pi_test_123"}},
    })

    assert result["payment_status"] == "paid"
    assert result["order_status"] == "confirmed"
    assert PaymentService(db).apply_stripe_event({
        "id": "evt_test_123", "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_123", "payment_status": "paid"}},
    })["payment_status"] == "paid"


def test_stripe_amount_conversion_uses_minor_units() -> None:
    assert amount_in_minor_units(1000) == 100000
    assert amount_in_minor_units(10.995) == 1100
