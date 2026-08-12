"""Small, additive compatibility migrations for databases created before v1.1.

New production deployments should run Alembic migrations as part of deployment.
This compatibility step keeps existing DukaanHub SQLite installations usable while
the project is upgraded from the original ``create_all`` setup.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply_compatibility_migrations(engine: Engine) -> None:
    """Add the checkout columns introduced after the first public schema.

    Every statement is additive or idempotent, so it is safe during application
    startup. It deliberately does not delete or rewrite customer/order data.
    """
    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("orders")}
    with engine.begin() as connection:
        if "currency" not in columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'PKR'"))
        if "idempotency_key" not in columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN idempotency_key VARCHAR(80)"))

        # ``cod`` was emitted by the original frontend. Preserve old orders but
        # store the canonical value expected by the payment domain from now on.
        connection.execute(text("UPDATE orders SET payment_method = 'cash_on_delivery' WHERE payment_method = 'cod'"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_idempotency_key ON orders (idempotency_key)"))
