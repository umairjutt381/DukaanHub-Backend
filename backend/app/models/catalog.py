from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    products = relationship("Product", back_populates="category")


class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    products = relationship("Product", back_populates="brand")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    specifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    compare_at_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_best_seller: Mapped[bool] = mapped_column(Boolean, default=False)
    is_new_arrival: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    product = relationship("Product", back_populates="images")

