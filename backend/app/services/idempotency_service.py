from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models import Order


class IdempotencyService:
    def __init__(self, db: Session):
        self.db = db

    def get_order(self, user_id: int, idempotency_key: str) -> Order | None:
        if not idempotency_key:
            return None
        return self.db.query(Order).filter(Order.user_id == user_id, Order.idempotency_key == idempotency_key).first()

