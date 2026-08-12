from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Brand, Category, Product


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, q: str | None = None, category: str | None = None, brand: str | None = None,
             featured: bool | None = None, best_seller: bool | None = None, new_arrival: bool | None = None,
             deal: bool | None = None, limit: int = 20, offset: int = 0) -> tuple[list[Product], int]:
        query = self.db.query(Product).options(selectinload(Product.images), selectinload(Product.category), selectinload(Product.brand)).filter(Product.is_active == True)  # noqa: E712
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like), Product.tags.ilike(like)))
        if category:
            query = query.join(Category).filter(Category.slug == category)
        if brand:
            query = query.join(Brand).filter(Brand.slug == brand)
        if featured is True:
            query = query.filter(Product.is_featured == True)  # noqa: E712
        if best_seller is True:
            query = query.filter(Product.is_best_seller == True)  # noqa: E712
        if new_arrival is True:
            query = query.filter(Product.is_new_arrival == True)  # noqa: E712
        if deal is True:
            query = query.filter(Product.is_deal == True)  # noqa: E712
        total = query.count()
        items = query.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

