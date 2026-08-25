from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.payments.enums import PaymentMethod
from backend.app.schemas.common import PHONE_REGEX


class AddressCreate(BaseModel):
    label: str
    full_name: str
    phone: str = Field(pattern=PHONE_REGEX)
    line1: str
    line2: str | None = None
    city: str
    state: str | None = None
    postal_code: str
    country: str = "Pakistan"
    is_default: bool = False


class AddressRead(BaseModel):
    """Address response schema.

    Keep output validation separate from input validation. Older addresses may
    contain values that were accepted before phone validation was introduced;
    returning those records must not make the checkout page fail with a 500.
    New and updated addresses still use the strict ``AddressCreate`` schema.
    """

    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    full_name: str
    phone: str
    line1: str
    line2: str | None = None
    city: str
    state: str | None = None
    postal_code: str
    country: str = "Pakistan"
    is_default: bool = False


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    quantity: int


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    product_name: str
    product_sku: str
    unit_price: float
    quantity: int
    total_price: float


class OrderCreate(BaseModel):
    payment_method: PaymentMethod
    shipping_name: str
    shipping_phone: str = Field(pattern=PHONE_REGEX)
    shipping_address: str
    billing_address: str | None = None
    notes: str | None = None
    coupon_code: str | None = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    status: str
    payment_method: str
    payment_status: str
    subtotal: float
    tax: float
    shipping_charges: float
    discount_amount: float
    total_amount: float
    items: list[OrderItemRead] = []


class ReviewCreate(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    comment: str | None = None
