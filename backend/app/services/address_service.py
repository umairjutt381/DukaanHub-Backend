from sqlalchemy.orm import Session

from backend.app.models import Address, User


def remember_checkout_address(
    db: Session,
    user: User,
    full_name: str,
    phone: str,
    address: str,
) -> Address:
    """Remember a checkout address and make the first one the default."""
    existing = (
        db.query(Address)
        .filter(
            Address.user_id == user.id,
            Address.full_name == full_name,
            Address.phone == phone,
            Address.line1 == address,
        )
        .first()
    )
    if existing:
        return existing

    has_default = db.query(Address).filter(Address.user_id == user.id, Address.is_default.is_(True)).first() is not None
    saved = Address(
        user_id=user.id,
        label="Default address" if not has_default else "Delivery address",
        full_name=full_name,
        phone=phone,
        line1=address,
        line2=None,
        city="",
        state=None,
        postal_code="",
        country="Pakistan",
        is_default=not has_default,
    )
    db.add(saved)
    db.flush()
    return saved
