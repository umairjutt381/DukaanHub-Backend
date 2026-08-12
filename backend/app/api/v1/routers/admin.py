from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import require_admin
from backend.app.domain.payments.enums import PaymentMethod
from backend.app.db.session import get_db
from backend.app.models import Brand, Category, ContactMessage, Coupon, Order, Product, ProductImage, Review, User, WebsiteSetting
from backend.app.schemas.admin import (
    BrandPayload,
    CategoryPayload,
    CouponPayload,
    PaymentMethodTogglePayload,
    ProductImagePayload,
    SettingPayload,
)
from backend.app.services.payment_settings import list_payment_method_states, set_payment_method_enabled
from backend.app.services.upload_service import UploadService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0)).scalar()
    return {
        "revenue": revenue,
        "orders": db.query(Order).count(),
        "products": db.query(Product).count(),
        "customers": db.query(User).filter(User.role == "customer").count(),
        "categories": db.query(Category).count(),
        "brands": db.query(Brand).count(),
        "recent_orders": [
            {"id": order.id, "order_number": order.order_number, "status": order.status, "total_amount": order.total_amount, "created_at": order.created_at}
            for order in db.query(Order).order_by(Order.created_at.desc()).limit(5).all()
        ],
        "inventory_status": [
            {"id": product.id, "name": product.name, "stock": product.stock}
            for product in db.query(Product).order_by(Product.stock.asc()).limit(10).all()
        ],
    }


@router.get("/products")
def list_products(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.category), selectinload(Product.brand))
        .order_by(Product.created_at.desc())
        .all()
    )


@router.get("/categories")
def list_categories(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(Category).order_by(Category.name.asc()).all()


@router.post("/categories")
def create_category(payload: CategoryPayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    return {"message": "Category created"}


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryPayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    db.commit()
    return {"message": "Category updated"}


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    category = db.get(Category, category_id)
    if category:
        db.delete(category)
        db.commit()
    return {"message": "Category deleted"}


@router.get("/brands")
def list_brands(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(Brand).order_by(Brand.name.asc()).all()


@router.post("/brands")
def create_brand(payload: BrandPayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    brand = Brand(**payload.model_dump())
    db.add(brand)
    db.commit()
    return {"message": "Brand created"}


@router.put("/brands/{brand_id}")
def update_brand(brand_id: int, payload: BrandPayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    for key, value in payload.model_dump().items():
        setattr(brand, key, value)
    db.commit()
    return {"message": "Brand updated"}


@router.delete("/brands/{brand_id}")
def delete_brand(brand_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    brand = db.get(Brand, brand_id)
    if brand:
        db.delete(brand)
        db.commit()
    return {"message": "Brand deleted"}


@router.get("/orders")
def list_orders(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc()).all()


@router.get("/customers")
def list_customers(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(User).filter(User.role == "customer").order_by(User.created_at.desc()).all()


@router.get("/coupons")
def list_coupons(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(Coupon).order_by(Coupon.code.asc()).all()


@router.post("/coupons")
def create_coupon(payload: CouponPayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    db.add(Coupon(**payload.model_dump()))
    db.commit()
    return {"message": "Coupon created"}


@router.delete("/coupons/{coupon_id}")
def delete_coupon(coupon_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    coupon = db.get(Coupon, coupon_id)
    if coupon:
        db.delete(coupon)
        db.commit()
    return {"message": "Coupon deleted"}


@router.get("/messages")
def list_messages(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).all()


@router.get("/reviews")
def list_reviews(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(Review).order_by(Review.created_at.desc()).all()


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(WebsiteSetting).all()


@router.put("/settings")
def upsert_setting(payload: SettingPayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    setting = db.query(WebsiteSetting).filter(WebsiteSetting.key == payload.key).first()
    if setting:
        setting.value = payload.value
    else:
        db.add(WebsiteSetting(key=payload.key, value=payload.value))
    db.commit()
    return {"message": "Setting saved"}


@router.post("/upload")
async def upload(file: UploadFile = File(...), _admin=Depends(require_admin)):
    url = await UploadService().save_file(file)
    return {"url": url}


@router.get("/payment-methods")
def payment_methods(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return list_payment_method_states(db)


@router.put("/payment-methods/{payment_method}")
def toggle_payment_method(payment_method: str, payload: PaymentMethodTogglePayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        method = PaymentMethod(payment_method)
    except ValueError as exc:
        raise HTTPException(400, "Unsupported payment method") from exc
    set_payment_method_enabled(db, method, payload.enabled)
    return {"payment_method": method.value, "enabled": payload.enabled}


@router.post("/products/{product_id}/images")
def add_product_image(product_id: int, payload: ProductImagePayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    if payload.is_primary:
        db.query(ProductImage).filter(ProductImage.product_id == product_id).update({"is_primary": False})
    image = ProductImage(product_id=product_id, **payload.model_dump())
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.put("/product-images/{image_id}")
def update_product_image(image_id: int, payload: ProductImagePayload, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    image = db.get(ProductImage, image_id)
    if not image:
        raise HTTPException(404, "Product image not found")
    if payload.is_primary:
        db.query(ProductImage).filter(ProductImage.product_id == image.product_id).update({"is_primary": False})
    for key, value in payload.model_dump().items():
        setattr(image, key, value)
    db.commit()
    db.refresh(image)
    return image


@router.delete("/product-images/{image_id}")
def delete_product_image(image_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    image = db.get(ProductImage, image_id)
    if image:
        db.delete(image)
        db.commit()
    return {"message": "Product image deleted"}
