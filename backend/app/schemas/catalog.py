from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import BrandRead, CategoryRead


class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    is_primary: bool
    sort_order: int


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    sku: str
    description: str
    specifications: str | None = None
    tags: str | None = None
    price: float
    compare_at_price: float | None = None
    stock: int
    rating: float
    review_count: int
    is_featured: bool
    is_best_seller: bool
    is_new_arrival: bool
    is_deal: bool
    is_active: bool
    seo_title: str | None = None
    seo_description: str | None = None
    images: list[ProductImageRead] = Field(default_factory=list)
    category: CategoryRead | None = None
    brand: BrandRead | None = None


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    slug: str = Field(min_length=2, max_length=260)
    sku: str = Field(min_length=2, max_length=80)
    description: str
    specifications: str | None = None
    tags: str | None = None
    price: float
    compare_at_price: float | None = None
    stock: int = 0
    category_id: int | None = None
    brand_id: int | None = None
    is_featured: bool = False
    is_best_seller: bool = False
    is_new_arrival: bool = False
    is_deal: bool = False
    seo_title: str | None = None
    seo_description: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    sku: str | None = None
    description: str | None = None
    specifications: str | None = None
    tags: str | None = None
    price: float | None = None
    compare_at_price: float | None = None
    stock: int | None = None
    category_id: int | None = None
    brand_id: int | None = None
    is_featured: bool | None = None
    is_best_seller: bool | None = None
    is_new_arrival: bool | None = None
    is_deal: bool | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    is_active: bool | None = None
