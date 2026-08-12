from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.deps import get_current_user, require_admin
from backend.app.db.session import get_db
from backend.app.models import Address, Brand, Category, ContactMessage, Notification, Product, Review, WishlistItem
from backend.app.schemas.commerce import AddressCreate, AddressRead, ReviewCreate
from backend.app.schemas.system import ContactMessageCreate, NewsletterSubscribe

router = APIRouter(tags=["misc"])


@router.post("/contact")
def contact(payload: ContactMessageCreate, db: Session = Depends(get_db)):
    db.add(ContactMessage(**payload.model_dump()))
    db.commit()
    return {"message": "Message sent successfully"}


@router.post("/newsletter")
def newsletter(payload: NewsletterSubscribe):
    return {"message": f"Subscribed {payload.email} to newsletter"}


@router.get("/home")
def home(db: Session = Depends(get_db)):
    def serialize_product(product: Product) -> dict:
        return {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "sku": product.sku,
            "description": product.description,
            "specifications": product.specifications,
            "tags": product.tags,
            "price": product.price,
            "compare_at_price": product.compare_at_price,
            "stock": product.stock,
            "rating": product.rating,
            "review_count": product.review_count,
            "is_featured": product.is_featured,
            "is_best_seller": product.is_best_seller,
            "is_new_arrival": product.is_new_arrival,
            "is_deal": product.is_deal,
            "images": [{"id": i.id, "url": i.url, "is_primary": i.is_primary, "sort_order": i.sort_order} for i in product.images],
            "brand": {"id": product.brand.id, "name": product.brand.name, "slug": product.brand.slug} if product.brand else None,
            "category": {"id": product.category.id, "name": product.category.name, "slug": product.category.slug} if product.category else None,
        }

    featured = db.query(Product).filter(Product.is_featured == True).limit(8).all()  # noqa: E712
    deals = db.query(Product).filter(Product.is_deal == True).limit(8).all()  # noqa: E712
    new_arrivals = db.query(Product).filter(Product.is_new_arrival == True).limit(8).all()  # noqa: E712
    return {
        "hero": {"title": "Premium shopping, one trusted hub.", "subtitle": "Discover elegant essentials at DukaanHub."},
        "categories": [{"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url, "is_featured": c.is_featured} for c in db.query(Category).filter(Category.is_featured == True).all()],  # noqa: E712
        "brands": [{"id": b.id, "name": b.name, "slug": b.slug, "logo_url": b.logo_url, "is_featured": b.is_featured} for b in db.query(Brand).filter(Brand.is_featured == True).all()],  # noqa: E712
        "featured_products": [serialize_product(product) for product in featured],
        "deals": [serialize_product(product) for product in deals],
        "new_arrivals": [serialize_product(product) for product in new_arrivals],
        "recently_viewed": [],
        "reviews": [],
    }


@router.get("/wishlist")
def wishlist(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = db.query(WishlistItem).filter(WishlistItem.user_id == user.id).all()
    return {
        "items": [
            {
                "id": item.id,
                "product": {
                    "id": item.product.id,
                    "name": item.product.name,
                    "slug": item.product.slug,
                    "sku": item.product.sku,
                    "description": item.product.description,
                    "price": item.product.price,
                    "compare_at_price": item.product.compare_at_price,
                    "stock": item.product.stock,
                    "rating": item.product.rating,
                    "review_count": item.product.review_count,
                    "is_featured": item.product.is_featured,
                    "is_best_seller": item.product.is_best_seller,
                    "is_new_arrival": item.product.is_new_arrival,
                    "is_deal": item.product.is_deal,
                    "images": [{"id": i.id, "url": i.url, "is_primary": i.is_primary, "sort_order": i.sort_order} for i in item.product.images],
                },
            }
            for item in items
        ]
    }


@router.post("/wishlist/{product_id}")
def toggle_wishlist(product_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(WishlistItem).filter(WishlistItem.user_id == user.id, WishlistItem.product_id == product_id).first()
    if item:
        db.delete(item)
        db.commit()
        return {"message": "Removed from wishlist"}
    db.add(WishlistItem(user_id=user.id, product_id=product_id))
    db.commit()
    return {"message": "Added to wishlist"}


@router.get("/addresses", response_model=list[AddressRead])
def list_addresses(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Address).filter(Address.user_id == user.id).all()


@router.post("/addresses", response_model=AddressRead)
def create_address(payload: AddressCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if payload.is_default:
        db.query(Address).filter(Address.user_id == user.id).update({"is_default": False})
    address = Address(user_id=user.id, **payload.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [
        {"id": n.id, "title": n.title, "body": n.body, "is_read": n.is_read, "created_at": n.created_at}
        for n in db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).all()
    ]


@router.post("/reviews")
def create_review(payload: ReviewCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    review = Review(user_id=user.id, **payload.model_dump())
    db.add(review)
    db.commit()
    return {"message": "Review submitted"}


@router.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.name.ilike(f"%{q}%")).limit(10).all()
    return {"suggestions": [p.name for p in products]}
