from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_current_user, require_admin
from backend.app.db.session import get_db
from backend.app.models import Order
from backend.app.schemas.commerce import OrderCreate, OrderRead
from backend.app.schemas.payments import CheckoutRequest, PaymentRedirectResponse
from backend.app.services.checkout_service import CheckoutService
from backend.app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead)
def create_order(payload: OrderCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return OrderService(db).create_order(user, payload)


@router.post("/checkout", response_model=PaymentRedirectResponse)
async def checkout_order(payload: CheckoutRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return await CheckoutService(db).checkout(user, payload, payload.idempotency_key)


@router.get("/me", response_model=list[OrderRead])
def my_orders(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Order).options(selectinload(Order.items)).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()


@router.get("/{order_number}", response_model=OrderRead)
def get_order(order_number: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    query = db.query(Order).options(selectinload(Order.items)).filter(Order.order_number == order_number)
    if user.role != "admin":
        query = query.filter(Order.user_id == user.id)
    order = query.first()
    return order


@router.get("/track/{order_number}", response_model=OrderRead)
def track_order(order_number: str, db: Session = Depends(get_db)):
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.order_number == order_number).first()
    return order


@router.patch("/{order_number}/status", response_model=OrderRead)
def update_status(order_number: str, status: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.order_number == order_number).first()
    order.status = status
    db.commit()
    db.refresh(order)
    return order
