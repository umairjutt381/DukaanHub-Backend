import pytest

from backend.scripts.seed_catalog import (
    SEED_SKU_PREFIX,
    build_catalog_plans,
    slugify,
    validate_source_products,
)


def source_product(product_id: int, title: str, category: str) -> dict:
    return {
        "id": product_id,
        "title": title,
        "category": category,
        "price": 99.95,
        "discountPercentage": 12,
        "rating": 4.4,
        "stock": 18,
        "brand": "Example Brand",
        "description": f"A useful {title.lower()} for everyday use.",
        "thumbnail": f"https://cdn.example.com/{product_id}.webp",
        "tags": [category],
        "reviews": [{"rating": 5}, {"rating": 4}],
        "dimensions": {"width": 10, "height": 20, "depth": 5},
        "warrantyInformation": "1 year warranty",
        "shippingInformation": "Ships in 2 days",
        "availabilityStatus": "In Stock",
        "returnPolicy": "14 days return policy",
    }


def test_slugify_normalizes_names() -> None:
    assert slugify("Crème & Coffee Set") == "creme-coffee-set"


def test_build_catalog_plans_creates_unique_matching_variants() -> None:
    source = [
        source_product(1, "Aurora Phone", "smartphones"),
        source_product(2, "Everyday Face Cream", "skin-care"),
    ]

    plans = build_catalog_plans(source, 5)

    assert len(plans) == 5
    assert len({plan.sku for plan in plans}) == 5
    assert len({plan.slug for plan in plans}) == 5
    assert all(plan.sku.startswith(SEED_SKU_PREFIX) for plan in plans)
    assert plans[0].name == "Aurora Phone — 128GB"
    assert plans[2].name == "Aurora Phone — 256GB"
    assert plans[0].local_image_url == plans[2].local_image_url
    assert plans[0].category_slug == "electronics"
    assert plans[1].category_slug == "beauty-personal-care"
    assert all(plan.compare_at_price > plan.price for plan in plans)
    assert all(plan.stock > 0 for plan in plans)


def test_validate_source_products_rejects_mismatched_feed_shape() -> None:
    with pytest.raises(ValueError, match="missing"):
        validate_source_products([{"id": 1, "title": "No photo"}])


def test_build_catalog_plans_rejects_more_than_three_variants() -> None:
    with pytest.raises(ValueError, match="three honest variants"):
        build_catalog_plans([source_product(1, "Aurora Phone", "smartphones")], 4)
