import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.v1.routers.catalog import categories, products
from backend.app.api.v1.routers.misc import home
from backend.app.db.session import Base
from backend.app.models import Brand, Category, Product, ProductImage


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_public_storefront_endpoints_return_serializable_catalog_data(db: Session) -> None:
    category = Category(name="Electronics", slug="electronics", is_featured=True)
    brand = Brand(name="DukaanHub", slug="dukaanhub", is_featured=True)
    db.add_all([category, brand])
    db.flush()
    product = Product(
        name="Storefront product", slug="storefront-product", sku="STOREFRONT-1",
        description="A product for the public storefront test.", price=1000, stock=10,
        is_active=True, is_featured=True, is_deal=True, is_new_arrival=True,
        category_id=category.id, brand_id=brand.id,
    )
    db.add(product)
    db.flush()
    db.add(ProductImage(product_id=product.id, url="/brand/dukaanhub-logo.png", is_primary=True))
    db.commit()

    catalog = products(page=1, page_size=20, db=db)
    homepage = home(db)

    assert len(categories(db)) == 1
    assert catalog["total"] == 1
    assert catalog["items"][0]["slug"] == "storefront-product"
    assert homepage["featured_products"][0]["images"][0]["url"] == "/brand/dukaanhub-logo.png"
