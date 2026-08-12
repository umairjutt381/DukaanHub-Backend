from functools import lru_cache
import os
from pathlib import Path

from pydantic import model_validator
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

ROOT_DIR = Path(__file__).resolve().parents[3]
PaymentMethodEnabled = Annotated[bool | None, BeforeValidator(lambda value: None if value == "" else value)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DukaanHub API"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    database_url: str = os.environ.get("DATABASE_URL", f"sqlite:///{(ROOT_DIR / 'dukaanhub.db').as_posix()}")
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    upload_dir: str = str(ROOT_DIR / "uploads")
    admin_email: str = "admin@dukaanhub.com"
    admin_password: str = "Admin@12345"
    admin_full_name: str = "DukaanHub Owner"
    jazzcash_merchant_id: str = ""
    jazzcash_password: str = ""
    jazzcash_integrity_salt: str = ""
    jazzcash_payment_url: str = ""
    jazzcash_return_url: str = ""
    jazzcash_callback_url: str = ""
    easypaisa_store_id: str = ""
    easypaisa_username: str = ""
    easypaisa_password: str = ""
    easypaisa_hash_key: str = ""
    easypaisa_payment_url: str = ""
    easypaisa_return_url: str = ""
    easypaisa_callback_url: str = ""
    card_gateway_name: str = "hosted_card_gateway"
    card_payment_url: str = ""
    card_return_url: str = ""
    card_callback_url: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = ""
    stripe_cancel_url: str = ""
    payment_currency: str = "PKR"
    payment_gateway_timeout_seconds: int = 30
    payment_tax_rate: float = 0.05
    payment_shipping_fee: float = 250.0
    payment_cod_fee: float = 0.0
    payment_method_cash_on_delivery_enabled: PaymentMethodEnabled = True
    payment_method_jazzcash_enabled: PaymentMethodEnabled = True
    payment_method_easypaisa_enabled: PaymentMethodEnabled = True
    payment_method_card_enabled: PaymentMethodEnabled = True
    payment_method_stripe_enabled: PaymentMethodEnabled = False
    frontend_base_url: str = "http://localhost:3000"
    google_client_secrets_file: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _apply_payment_method_defaults(self):
        if self.payment_method_cash_on_delivery_enabled is None:
            self.payment_method_cash_on_delivery_enabled = True
        if self.payment_method_jazzcash_enabled is None:
            self.payment_method_jazzcash_enabled = True
        if self.payment_method_easypaisa_enabled is None:
            self.payment_method_easypaisa_enabled = True
        if self.payment_method_card_enabled is None:
            self.payment_method_card_enabled = True
        if self.payment_method_stripe_enabled is None:
            self.payment_method_stripe_enabled = False
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
