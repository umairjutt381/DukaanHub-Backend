from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    is_featured: bool


class BrandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    logo_url: str | None = None
    is_featured: bool

