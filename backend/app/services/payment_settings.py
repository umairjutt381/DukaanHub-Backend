from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.domain.payments.enums import PaymentMethod
from backend.app.models import WebsiteSetting


SETTING_KEY_PREFIX = "payment_method_"


def _setting_key(payment_method: PaymentMethod) -> str:
    return f"{SETTING_KEY_PREFIX}{payment_method.value}_enabled"


def get_payment_method_enabled(db: Session, payment_method: PaymentMethod) -> bool:
    settings = get_settings()
    default_enabled = {
        PaymentMethod.CASH_ON_DELIVERY: settings.payment_method_cash_on_delivery_enabled,
        PaymentMethod.JAZZCASH: settings.payment_method_jazzcash_enabled,
        PaymentMethod.EASYPAISA: settings.payment_method_easypaisa_enabled,
        PaymentMethod.CARD: settings.payment_method_card_enabled,
        PaymentMethod.STRIPE: settings.payment_method_stripe_enabled and bool(settings.stripe_secret_key),
    }[payment_method]
    record = db.query(WebsiteSetting).filter(WebsiteSetting.key == _setting_key(payment_method)).first()
    if record is None:
        return default_enabled
    return record.value.lower() in {"1", "true", "yes", "enabled", "on"}


def set_payment_method_enabled(db: Session, payment_method: PaymentMethod, enabled: bool) -> None:
    key = _setting_key(payment_method)
    record = db.query(WebsiteSetting).filter(WebsiteSetting.key == key).first()
    if record:
        record.value = "true" if enabled else "false"
    else:
        db.add(WebsiteSetting(key=key, value="true" if enabled else "false"))
    db.commit()


def list_payment_method_states(db: Session) -> dict[str, bool]:
    return {method.value: get_payment_method_enabled(db, method) for method in PaymentMethod}


def get_delivery_charge_amount(db: Session | None = None) -> float:
    settings = get_settings()
    if db is not None:
        record = db.query(WebsiteSetting).filter(WebsiteSetting.key == "delivery_charge").first()
        if record and record.value:
            try:
                return float(record.value)
            except ValueError:
                pass
    return settings.payment_shipping_fee
