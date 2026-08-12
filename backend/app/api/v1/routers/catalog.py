from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from backend.app.db.session import get_db
from backend.app.models import Brand, Category, Product
from backend.app.repositories.product_repository import ProductRepository
from backend.app.schemas.common import BrandRead, CategoryRead
from backend.app.schemas.catalog import ProductCreate, ProductRead, ProductUpdate
from backend.app.core.deps import require_admin

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryRead])
def categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name.asc()).all()


@router.get("/brands", response_model=list[BrandRead])
def brands(db: Session = Depends(get_db)):
    return db.query(Brand).order_by(Brand.name.asc()).all()


@router.get("/products", response_model=dict)
def products(
    q: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    featured: bool | None = None,
    best_seller: bool | None = None,
    new_arrival: bool | None = None,
    deal: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    items, total = ProductRepository(db).list(q, category, brand, featured, best_seller, new_arrival, deal, limit=page_size, offset=(page - 1) * page_size)
    serialized = [
        {
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
            "is_active": product.is_active,
            "seo_title": product.seo_title,
            "seo_description": product.seo_description,
            "images": [{"id": image.id, "url": image.url, "is_primary": image.is_primary, "sort_order": image.sort_order} for image in product.images],
            "category": {"id": product.category.id, "name": product.category.name, "slug": product.category.slug} if product.category else None,
            "brand": {"id": product.brand.id, "name": product.brand.name, "slug": product.brand.slug} if product.brand else None,
        }
        for product in items
    ]
    return {"items": serialized, "total": total, "page": page, "page_size": page_size}


@router.get("/products/by-ids", response_model=list[ProductRead])
def products_by_ids(
    ids: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
):
    """Return complete product records for a small, explicit set of IDs."""
    if len(ids) > 100:
        raise HTTPException(400, "A maximum of 100 product IDs is allowed per request")
    if not ids:
        return []

    unique_ids = list(dict.fromkeys(ids))
    products = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.category), selectinload(Product.brand))
        .filter(Product.id.in_(unique_ids), Product.is_active == True)  # noqa: E712
        .all()
    )
    products_by_id = {product.id: product for product in products}
    return [products_by_id[product_id] for product_id in unique_ids if product_id in products_by_id]


@router.get("/products/{slug}", response_model=ProductRead)
def product_detail(slug: str, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.category), selectinload(Product.brand))
        .filter(Product.slug == slug, Product.is_active == True)  # noqa: E712
        .first()
    )
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@router.post("/products", response_model=ProductRead)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    product = db.get(Product, product_id)
    if product:
        db.delete(product)
        db.commit()
    return {"message": "Product deleted"}
