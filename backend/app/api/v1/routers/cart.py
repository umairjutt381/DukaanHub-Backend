from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import CartItem, Product
from backend.app.schemas.commerce import CartItemCreate
from backend.app.services.payment_settings import get_delivery_charge_amount

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("")
def get_cart(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = db.query(CartItem).options(selectinload(CartItem.product)).filter(CartItem.user_id == user.id).all()
    subtotal = sum((item.product.price * item.quantity) for item in items if item.product)
    shipping = get_delivery_charge_amount(db)
    return {
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "product": {
                    "id": item.product.id,
                    "name": item.product.name,
                    "slug": item.product.slug,
                    "sku": item.product.sku,
                    "price": item.product.price,
                    "compare_at_price": item.product.compare_at_price,
                } if item.product else None,
            }
            for item in items
        ],
        "subtotal": subtotal,
        "tax": round(subtotal * 0.05, 2),
        "shipping": shipping,
        "total": round(subtotal * 1.05 + shipping, 2),
    }


@router.post("/items")
def add_item(payload: CartItemCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    item = db.query(CartItem).filter(CartItem.user_id == user.id, CartItem.product_id == payload.product_id).first()
    if item:
        item.quantity += payload.quantity
    else:
        item = CartItem(user_id=user.id, product_id=payload.product_id, quantity=payload.quantity)
        db.add(item)
    db.commit()
    return {"message": "Added to cart"}


@router.patch("/items/{item_id}")
def update_item(item_id: int, quantity: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    item.quantity = max(1, quantity)
    db.commit()
    return {"message": "Cart updated"}


@router.delete("/items/{item_id}")
def remove_item(item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    db.delete(item)
    db.commit()
    return {"message": "Removed from cart"}
