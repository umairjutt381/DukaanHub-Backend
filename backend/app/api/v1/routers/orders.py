from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_current_user, require_admin
from backend.app.db.session import get_db
from backend.app.models import Order, User
from backend.app.schemas.commerce import OrderCreate, OrderRead
from backend.app.schemas.payments import CheckoutRequest, PaymentRedirectResponse
from backend.app.services.checkout_service import CheckoutService
from backend.app.services.email_service import send_order_emails, send_order_status_email
from backend.app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead)
def create_order(background_tasks: BackgroundTasks, payload: OrderCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = OrderService(db).create_order(user, payload)
    background_tasks.add_task(
        send_order_emails,
        user.email,
        user.full_name,
        order.order_number,
        order.total_amount,
        order.currency,
        [(item.product_name, item.quantity, item.total_price) for item in order.items],
    )
    return order


@router.post("/checkout", response_model=PaymentRedirectResponse)
async def checkout_order(background_tasks: BackgroundTasks, payload: CheckoutRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = await CheckoutService(db).checkout(user, payload, payload.idempotency_key)
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.id == result.order_id).first()
    if order:
        background_tasks.add_task(
            send_order_emails,
            user.email,
            user.full_name,
            order.order_number,
            order.total_amount,
            order.currency,
            [(item.product_name, item.quantity, item.total_price) for item in order.items],
        )
    return result


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
def update_status(background_tasks: BackgroundTasks, order_number: str, status: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.order_number == order_number).first()
    order.status = status
    db.commit()
    db.refresh(order)
    customer = db.get(User, order.user_id)
    if customer:
        background_tasks.add_task(send_order_status_email, customer.email, customer.full_name, order.order_number, order.status)
    return order
