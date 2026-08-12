from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user, require_admin
from backend.app.db.session import get_db
from backend.app.domain.payments.enums import GatewayName, PaymentMethod
from backend.app.models import Order, Payment
from backend.app.schemas.payments import CheckoutRequest, CODCollectResponse, PaymentInitiateRequest, PaymentRedirectResponse, PaymentStatusResponse, RefundRequest, RefundResponse
from backend.app.services.checkout_service import CheckoutService
from backend.app.services.payment_service import PaymentService
from backend.app.services.payment_settings import get_payment_method_enabled
from backend.app.services.payments.factory import PaymentGatewayFactory
from backend.app.services.payments.utils import redact_payload

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()


async def _read_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return dict(form)
    if request.query_params:
        return dict(request.query_params)
    body = await request.body()
    if body:
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body.decode("utf-8", errors="ignore")}
    return {}


def _frontend_redirect(path: str, params: dict[str, Any] | None = None) -> RedirectResponse:
    query = ""
    if params:
        safe = {k: v for k, v in params.items() if v is not None}
        query = "?" + "&".join(f"{k}={v}" for k, v in safe.items())
    return RedirectResponse(url=f"{settings.frontend_base_url}{path}{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/orders/checkout", response_model=PaymentRedirectResponse)
async def checkout_order(payload: CheckoutRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return await CheckoutService(db).checkout(user, payload, payload.idempotency_key)


@router.post("/initiate", response_model=PaymentRedirectResponse)
async def initiate_payment(payload: PaymentInitiateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.id == payload.order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not get_payment_method_enabled(db, payload.payment_method):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{payload.payment_method.value} is currently disabled")
    gateway = PaymentGatewayFactory.get_gateway(payload.payment_method)
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        payment = Payment(order_id=order.id, payment_method=payload.payment_method.value, gateway_name=payload.payment_method.value, amount=order.total_amount, currency=order.currency, status="pending", merchant_transaction_id=f"{payload.payment_method.value[:2].upper()}{order.order_number}")
        db.add(payment)
        db.flush()
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
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    return PaymentRedirectResponse(order_id=order.id, order_number=order.order_number, payment_id=payment.id, payment_method=payload.payment_method, payment_status=payment.status, order_status=order.status, redirect_url=initiation.redirect_url, redirect_form=initiation.redirect_form, message=initiation.response_message or "Payment initiated", gateway_name=initiation.gateway_name, transaction_id=initiation.merchant_transaction_id)


@router.post("/jazzcash/callback")
async def jazzcash_callback(request: Request, db: Session = Depends(get_db)):
    payload = await _read_payload(request)
    result = await PaymentService(db).verify_and_apply_callback(GatewayName.JAZZCASH, payload, dict(request.headers))
    return result


@router.post("/easypaisa/callback")
async def easypaisa_callback(request: Request, db: Session = Depends(get_db)):
    payload = await _read_payload(request)
    result = await PaymentService(db).verify_and_apply_callback(GatewayName.EASYPAISA, payload, dict(request.headers))
    return result


@router.post("/card/webhook")
async def card_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await _read_payload(request)
    result = await PaymentService(db).verify_and_apply_callback(GatewayName.CARD, payload, dict(request.headers))
    return result


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook endpoint. The raw request body is required for signature verification."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook is not configured")
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature")
    raw_payload = await request.body()
    try:
        import stripe
        event = stripe.Webhook.construct_event(raw_payload, signature, settings.stripe_webhook_secret)
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe package is not installed") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook signature") from exc
    return PaymentService(db).apply_stripe_event(dict(event))


@router.get("/return/{gateway}")
async def payment_return(gateway: str, request: Request, db: Session = Depends(get_db)):
    payload = await _read_payload(request)
    try:
        gateway_name = GatewayName(gateway)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported payment gateway") from exc
    result = await PaymentService(db).verify_and_apply_callback(gateway_name, payload, dict(request.headers))
    if result["payment_status"] == "paid":
        return _frontend_redirect("/payment/success", {"order_id": result["order_id"], "order_number": result["order_number"], "gateway": gateway_name.value})
    if result["payment_status"] in {"cancelled", "failed", "expired"}:
        return _frontend_redirect(f"/payment/{result['payment_status']}", {"order_id": result["order_id"], "order_number": result["order_number"], "gateway": gateway_name.value})
    return _frontend_redirect("/payment/pending", {"order_id": result["order_id"], "order_number": result["order_number"], "gateway": gateway_name.value})


@router.get("/status/{order_id}", response_model=PaymentStatusResponse)
def payment_status(order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    result = PaymentService(db).get_status(order_id)
    return PaymentStatusResponse(**result)


@router.post("/admin/orders/{order_id}/cod/collect", response_model=CODCollectResponse)
def collect_cod(order_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    result = PaymentService(db).mark_cod_collected(order_id)
    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return CODCollectResponse(order_id=result["order_id"], payment_id=payment.id, payment_status=result["payment_status"], order_status=result["order_status"], message="COD payment marked as collected")


@router.post("/admin/payments/{payment_id}/refund", response_model=RefundResponse)
async def admin_refund(payment_id: int, payload: RefundRequest = Body(...), db: Session = Depends(get_db), _admin=Depends(require_admin)):
    result = await PaymentService(db).refund_payment(payment_id, payload.amount, payload.reason)
    return RefundResponse(**result)


@router.get("/admin/payments")
def list_payments(payment_method: str | None = None, status_filter: str | None = None, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    query = db.query(Payment).options(selectinload(Payment.attempts)).order_by(Payment.created_at.desc())
    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    return query.all()
