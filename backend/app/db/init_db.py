from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import get_password_hash
from backend.app.models import Brand, Category, Product, ProductImage, User


def seed_data(db: Session) -> None:
    settings = get_settings()
    admin = db.query(User).filter(User.email == settings.admin_email).first()
    if not admin:
        admin = User(
            full_name=settings.admin_full_name,
            email=settings.admin_email,
            hashed_password=get_password_hash(settings.admin_password),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)

    if not db.query(Category).first():
        categories = [
            Category(name="Electronics", slug="electronics", description="Devices and accessories", is_featured=True),
            Category(name="Fashion", slug="fashion", description="Apparel and style", is_featured=True),
            Category(name="Home & Living", slug="home-living", description="Home essentials", is_featured=True),
            Category(name="Groceries", slug="groceries", description="Daily essentials", is_featured=True),
        ]
        db.add_all(categories)

    if not db.query(Brand).first():
        brands = [
            Brand(name="DukaanHub Select", slug="dukaanhub-select", is_featured=True),
            Brand(name="Premium Choice", slug="premium-choice", is_featured=True),
        ]
        db.add_all(brands)

    db.flush()
    if not db.query(Product).first():
        category = db.query(Category).filter(Category.slug == "electronics").first()
        brand = db.query(Brand).filter(Brand.slug == "dukaanhub-select").first()
        product = Product(
            name="Smart Wireless Headphones",
            slug="smart-wireless-headphones",
            sku="DHK-1001",
            description="Premium noise-isolating headphones with long battery life.",
            price=12999,
            compare_at_price=15999,
            stock=24,
            category_id=category.id if category else None,
            brand_id=brand.id if brand else None,
            is_featured=True,
            is_best_seller=True,
            is_new_arrival=True,
            is_deal=True,
            tags="headphones,audio,wireless",
            specifications="Battery: 40h; Connectivity: Bluetooth 5.3; Warranty: 1 year",
        )
        db.add(product)
        db.flush()
        db.add(ProductImage(product_id=product.id, url="/brand/dukaanhub-logo.png", is_primary=True, sort_order=1))

    db.commit()

