"""Seed a realistic, image-backed development catalog.

The source feed is DummyJSON's public product fixture API.  Source products
are expanded into category-appropriate variants so a 194-item feed can
provide a 500-item storefront without mismatching an item's name and photo.
Images are cached under ``uploads/catalog-seed`` and the import is idempotent
through the reserved ``DH-DJ-`` SKU prefix.

This command intentionally seeds catalog entities only.  It does not create
customers, orders, payments, refunds, or other transactional records.
"""

from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import httpx
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import ROOT_DIR, get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import Brand, Category, Product, ProductImage

SOURCE_URL = "https://dummyjson.com/products?limit=0"
SOURCE_DOCUMENTATION = "https://dummyjson.com/docs/products"
SEED_SKU_PREFIX = "DH-DJ-"
DEFAULT_COUNT = 500
PKR_PER_SOURCE_UNIT = 285.0
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_SUBDIRECTORY = "catalog-seed"


CATEGORY_META: dict[str, tuple[str, str, str]] = {
    "electronics": (
        "Electronics",
        "electronics",
        "Phones, computers, tablets and useful technology accessories.",
    ),
    "fashion": (
        "Fashion",
        "fashion",
        "Clothing, footwear, watches, bags and accessories for every wardrobe.",
    ),
    "home-living": (
        "Home & Living",
        "home-living",
        "Furniture, decor and practical kitchen essentials for modern homes.",
    ),
    "groceries": (
        "Groceries",
        "groceries",
        "Pantry staples, drinks, snacks and everyday household groceries.",
    ),
    "beauty-personal-care": (
        "Beauty & Personal Care",
        "beauty-personal-care",
        "Skincare, makeup and fragrances for daily personal care.",
    ),
    "sports-outdoors": (
        "Sports & Outdoors",
        "sports-outdoors",
        "Equipment and accessories for training, recreation and outdoor activity.",
    ),
    "automotive": (
        "Automotive",
        "automotive",
        "Vehicles, motorcycles and practical road-ready equipment.",
    ),
}

SOURCE_CATEGORY_GROUP: dict[str, str] = {
    "beauty": "beauty-personal-care",
    "fragrances": "beauty-personal-care",
    "skin-care": "beauty-personal-care",
    "furniture": "home-living",
    "home-decoration": "home-living",
    "kitchen-accessories": "home-living",
    "groceries": "groceries",
    "laptops": "electronics",
    "mobile-accessories": "electronics",
    "smartphones": "electronics",
    "tablets": "electronics",
    "mens-shirts": "fashion",
    "mens-shoes": "fashion",
    "mens-watches": "fashion",
    "sunglasses": "fashion",
    "tops": "fashion",
    "womens-bags": "fashion",
    "womens-dresses": "fashion",
    "womens-jewellery": "fashion",
    "womens-shoes": "fashion",
    "womens-watches": "fashion",
    "sports-accessories": "sports-outdoors",
    "motorcycle": "automotive",
    "vehicle": "automotive",
}

VARIANT_LABELS: dict[str, tuple[str, str, str]] = {
    "beauty": ("Natural Finish", "Classic Finish", "Professional Finish"),
    "fragrances": ("30 ml", "50 ml", "100 ml"),
    "skin-care": ("30 ml", "50 ml", "100 ml"),
    "furniture": ("Compact", "Standard", "Large"),
    "groceries": ("Single Pack", "Pack of 2", "Family Pack"),
    "home-decoration": ("Classic", "Modern", "Signature"),
    "kitchen-accessories": ("Single", "2-Piece Set", "Gift Set"),
    "laptops": ("8GB / 256GB", "16GB / 512GB", "32GB / 1TB"),
    "mens-shirts": ("Small", "Medium", "Large"),
    "mens-shoes": ("EU 40", "EU 42", "EU 44"),
    "mens-watches": ("Standard", "Gift Edition", "Collector Edition"),
    "mobile-accessories": ("Standard", "Plus", "Premium"),
    "motorcycle": ("Standard", "Comfort", "Premium"),
    "smartphones": ("128GB", "256GB", "512GB"),
    "sports-accessories": ("Standard", "Club", "Pro"),
    "sunglasses": ("Standard Fit", "Medium Fit", "Large Fit"),
    "tablets": ("128GB", "256GB", "512GB"),
    "tops": ("Small", "Medium", "Large"),
    "vehicle": ("Standard", "Comfort", "Premium"),
    "womens-bags": ("Classic", "Signature", "Gift Edition"),
    "womens-dresses": ("Small", "Medium", "Large"),
    "womens-jewellery": ("Standard", "Gift Box", "Premium Box"),
    "womens-shoes": ("EU 36", "EU 38", "EU 40"),
    "womens-watches": ("Standard", "Gift Edition", "Collector Edition"),
}

VARIANT_PRICE_MULTIPLIERS = (1.0, 1.12, 1.25)


@dataclass(frozen=True)
class CatalogPlan:
    source_id: int
    source_image_url: str
    local_image_url: str
    name: str
    slug: str
    sku: str
    description: str
    specifications: str
    tags: str
    price: float
    compare_at_price: float
    stock: int
    rating: float
    review_count: int
    category_slug: str
    brand_name: str
    is_featured: bool
    is_best_seller: bool
    is_new_arrival: bool
    is_deal: bool
    seo_title: str
    seo_description: str


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def _round_pkr(value: float) -> float:
    increment = 50 if value < 5_000 else 100 if value < 50_000 else 500
    return float(max(increment, round(value / increment) * increment))


def _specifications(source: dict[str, Any], variant_label: str) -> str:
    values = [f"Variant: {variant_label}"]
    dimensions = source.get("dimensions") or {}
    if all(dimensions.get(key) is not None for key in ("width", "height", "depth")):
        values.append(
            "Dimensions: "
            f"{dimensions['width']} × {dimensions['height']} × {dimensions['depth']} cm"
        )
    for label, key in (
        ("Warranty", "warrantyInformation"),
        ("Shipping", "shippingInformation"),
        ("Availability", "availabilityStatus"),
        ("Returns", "returnPolicy"),
    ):
        if source.get(key):
            values.append(f"{label}: {source[key]}")
    return "; ".join(values)


def validate_source_products(products: Any) -> list[dict[str, Any]]:
    if not isinstance(products, list) or not products:
        raise ValueError("The source response did not include any products")

    required = ("id", "title", "category", "price", "thumbnail")
    valid: list[dict[str, Any]] = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            raise ValueError(f"Source product {index} is not an object")
        missing = [key for key in required if product.get(key) in (None, "")]
        if missing:
            raise ValueError(f"Source product {index} is missing: {', '.join(missing)}")
        if product["category"] not in SOURCE_CATEGORY_GROUP:
            raise ValueError(f"Unsupported source category: {product['category']}")
        if not str(product["thumbnail"]).startswith("https://"):
            raise ValueError(f"Product {product['id']} does not have a secure image URL")
        valid.append(product)
    return valid


def fetch_source_products(source_url: str = SOURCE_URL) -> list[dict[str, Any]]:
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        response = client.get(source_url)
        response.raise_for_status()
    payload = response.json()
    return validate_source_products(payload.get("products") if isinstance(payload, dict) else None)


def build_catalog_plans(products: list[dict[str, Any]], count: int) -> list[CatalogPlan]:
    products = validate_source_products(products)
    if count < 1:
        raise ValueError("Count must be at least 1")
    if count > len(products) * 3:
        raise ValueError(
            f"Count cannot exceed {len(products) * 3}; only three honest variants are created per source item"
        )

    plans: list[CatalogPlan] = []
    for position in range(count):
        source = products[position % len(products)]
        variant_index = position // len(products)
        source_category = str(source["category"])
        variant_label = VARIANT_LABELS[source_category][variant_index]
        source_id = int(source["id"])
        title = str(source["title"]).strip()
        name = f"{title} — {variant_label}"[:220]
        category_slug = SOURCE_CATEGORY_GROUP[source_category]
        multiplier = VARIANT_PRICE_MULTIPLIERS[variant_index]
        price = _round_pkr(float(source["price"]) * PKR_PER_SOURCE_UNIT * multiplier)
        discount = min(max(float(source.get("discountPercentage") or 0), 5.0), 35.0)
        compare_at_price = _round_pkr(price / (1 - discount / 100))
        if compare_at_price <= price:
            compare_at_price = _round_pkr(price * 1.1)

        source_tags = [str(tag).strip() for tag in source.get("tags") or [] if str(tag).strip()]
        tags = list(dict.fromkeys([*source_tags, source_category, category_slug, variant_label.lower()]))
        description = str(source.get("description") or "").strip()
        description = f"{description} Available in the {variant_label} configuration."[:3000]
        rating = min(5.0, max(0.0, round(float(source.get("rating") or 0), 1)))
        review_count = len(source.get("reviews") or [])
        stock = max(5, int(source.get("stock") or 0) + ((source_id * 7 + variant_index * 11) % 35))
        brand_name = str(source.get("brand") or "DukaanHub Select").strip()[:120]
        sku = f"{SEED_SKU_PREFIX}{source_id:04d}-{variant_index + 1:02d}"
        slug = slugify(f"{title}-{variant_label}-dj-{source_id}-{variant_index + 1}")[:260]
        local_image_url = f"/uploads/{IMAGE_SUBDIRECTORY}/dummyjson-{source_id:04d}.webp"

        plans.append(
            CatalogPlan(
                source_id=source_id,
                source_image_url=str(source["thumbnail"]),
                local_image_url=local_image_url,
                name=name,
                slug=slug,
                sku=sku,
                description=description,
                specifications=_specifications(source, variant_label),
                tags=",".join(tags)[:500],
                price=price,
                compare_at_price=compare_at_price,
                stock=stock,
                rating=rating,
                review_count=review_count,
                category_slug=category_slug,
                brand_name=brand_name,
                is_featured=position % 17 == 0,
                is_best_seller=rating >= 4.5 or position % 13 == 0,
                is_new_arrival=position % 7 == 0,
                is_deal=position % 4 == 0,
                seo_title=name[:255],
                seo_description=description[:500],
            )
        )

    if len({plan.sku for plan in plans}) != count:
        raise ValueError("Generated SKUs are not unique")
    if len({plan.slug for plan in plans}) != count:
        raise ValueError("Generated slugs are not unique")
    return plans


def _is_valid_webp(content: bytes) -> bool:
    return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"


def _download_image(url: str, destination: Path, refresh: bool) -> str:
    if destination.exists() and not refresh:
        existing = destination.read_bytes()
        if _is_valid_webp(existing):
            return "cached"

    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "DukaanHubCatalogSeeder/1.0"}) as client:
        response = client.get(url)
        response.raise_for_status()
    content = response.content
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB: {url}")
    if not _is_valid_webp(content):
        raise ValueError(f"Source did not return a valid WebP image: {url}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".webp.part")
    temporary.write_bytes(content)
    temporary.replace(destination)
    return "downloaded"


def prepare_images(plans: Iterable[CatalogPlan], upload_dir: Path, refresh: bool, workers: int) -> dict[str, int]:
    sources = {
        plan.source_id: (plan.source_image_url, upload_dir / IMAGE_SUBDIRECTORY / f"dummyjson-{plan.source_id:04d}.webp")
        for plan in plans
    }
    results: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_image, image_url, destination, refresh): source_id
            for source_id, (image_url, destination) in sources.items()
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            source_id = futures[future]
            try:
                results[future.result()] += 1
            except Exception as exc:
                raise RuntimeError(f"Could not prepare image for source product {source_id}: {exc}") from exc
            if completed % 25 == 0 or completed == len(futures):
                print(f"Prepared {completed}/{len(futures)} unique product images")
    return dict(results)


def _upsert_categories(db: Session, plans: list[CatalogPlan]) -> dict[str, Category]:
    needed_slugs = sorted({plan.category_slug for plan in plans})
    existing = {category.slug: category for category in db.query(Category).all()}
    for slug in needed_slugs:
        name, canonical_slug, description = CATEGORY_META[slug]
        category = existing.get(canonical_slug)
        if category is None:
            category = Category(name=name, slug=canonical_slug)
            db.add(category)
            existing[canonical_slug] = category
        category.name = name
        category.description = description
        category.is_featured = True
    db.flush()
    return {slug: existing[slug] for slug in needed_slugs}


def _upsert_brands(db: Session, plans: list[CatalogPlan]) -> dict[str, Brand]:
    brand_counts = Counter(plan.brand_name for plan in plans)
    featured_names = {name for name, _ in brand_counts.most_common(10)}
    existing_by_name = {brand.name: brand for brand in db.query(Brand).all()}
    existing_slugs = {brand.slug for brand in existing_by_name.values()}

    for name in sorted(brand_counts):
        brand = existing_by_name.get(name)
        if brand is None:
            base_slug = slugify(name) or "brand"
            brand_slug = base_slug
            suffix = 2
            while brand_slug in existing_slugs:
                brand_slug = f"{base_slug}-{suffix}"
                suffix += 1
            brand = Brand(name=name, slug=brand_slug)
            db.add(brand)
            existing_by_name[name] = brand
            existing_slugs.add(brand_slug)
        if name in featured_names:
            brand.is_featured = True
    db.flush()
    return {name: existing_by_name[name] for name in brand_counts}


def upsert_catalog(db: Session, plans: list[CatalogPlan]) -> tuple[int, int]:
    categories = _upsert_categories(db, plans)
    brands = _upsert_brands(db, plans)
    existing_products = {
        product.sku: product
        for product in (
            db.query(Product)
            .options(selectinload(Product.images))
            .filter(Product.sku.like(f"{SEED_SKU_PREFIX}%"))
            .all()
        )
    }

    created = 0
    updated = 0
    for plan in plans:
        product = existing_products.get(plan.sku)
        if product is None:
            product = Product(sku=plan.sku, name=plan.name, slug=plan.slug, description=plan.description, price=plan.price)
            db.add(product)
            existing_products[plan.sku] = product
            created += 1
        else:
            updated += 1

        product.name = plan.name
        product.slug = plan.slug
        product.description = plan.description
        product.specifications = plan.specifications
        product.tags = plan.tags
        product.price = plan.price
        product.compare_at_price = plan.compare_at_price
        product.stock = plan.stock
        product.rating = plan.rating
        product.review_count = plan.review_count
        product.category = categories[plan.category_slug]
        product.brand = brands[plan.brand_name]
        product.is_featured = plan.is_featured
        product.is_best_seller = plan.is_best_seller
        product.is_new_arrival = plan.is_new_arrival
        product.is_deal = plan.is_deal
        product.is_active = True
        product.seo_title = plan.seo_title
        product.seo_description = plan.seo_description

        if len(product.images) != 1 or product.images[0].url != plan.local_image_url:
            product.images[:] = [
                ProductImage(url=plan.local_image_url, is_primary=True, sort_order=0)
            ]
        else:
            product.images[0].is_primary = True
            product.images[0].sort_order = 0

    db.commit()
    return created, updated


def create_sqlite_backup() -> Path | None:
    settings = get_settings()
    database_url = make_url(settings.database_url)
    if not database_url.drivername.startswith("sqlite") or not database_url.database:
        return None
    source = Path(database_url.database)
    if not source.exists():
        return None
    backup_dir = ROOT_DIR / ".backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"dukaanhub-before-catalog-seed-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(source, destination)
    return destination


def _summary(plans: list[CatalogPlan]) -> str:
    return (
        f"{len(plans)} products, "
        f"{len({plan.category_slug for plan in plans})} categories, "
        f"{len({plan.brand_name for plan in plans})} brands, "
        f"{len({plan.source_id for plan in plans})} unique matching images"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of product records to upsert")
    parser.add_argument("--dry-run", action="store_true", help="Validate and plan without downloading images or writing the database")
    parser.add_argument("--refresh-images", action="store_true", help="Download source images again even when a valid cached file exists")
    parser.add_argument("--workers", type=int, default=8, choices=range(1, 17), metavar="1-16", help="Concurrent image downloads")
    parser.add_argument("--source-url", default=SOURCE_URL, help="Compatible product feed URL")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"Loading source products from {args.source_url}")
    products = fetch_source_products(args.source_url)
    plans = build_catalog_plans(products, args.count)
    print(f"Validated plan: {_summary(plans)}")
    print(f"Source documentation: {SOURCE_DOCUMENTATION}")

    if args.dry_run:
        print("Dry run complete; no images or database records were changed")
        return 0

    settings = get_settings()
    image_results = prepare_images(plans, Path(settings.upload_dir), args.refresh_images, args.workers)
    backup = create_sqlite_backup()
    if backup:
        print(f"SQLite backup created at {backup}")

    db = SessionLocal()
    try:
        created, updated = upsert_catalog(db, plans)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "Catalog seed complete: "
        f"{created} created, {updated} updated; "
        f"{image_results.get('downloaded', 0)} images downloaded, "
        f"{image_results.get('cached', 0)} images reused"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
