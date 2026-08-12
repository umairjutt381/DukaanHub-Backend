"""Request payloads used by the admin API routes."""

from pydantic import BaseModel


class CategoryPayload(BaseModel):
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    is_featured: bool = False


class BrandPayload(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None
    is_featured: bool = False


class CouponPayload(BaseModel):
    code: str
    discount_type: str = "percent"
    discount_value: float = 0
    min_order_amount: float = 0
    max_discount_amount: float | None = None
    is_active: bool = True


class SettingPayload(BaseModel):
    key: str
    value: str


class PaymentMethodTogglePayload(BaseModel):
    enabled: bool


class ProductImagePayload(BaseModel):
    url: str
    is_primary: bool = True
    sort_order: int = 0
