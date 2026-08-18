from functools import lru_cache
import os
from pathlib import Path

from pydantic import model_validator
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated
from typing import Literal

ROOT_DIR = Path(__file__).resolve().parents[3]
PaymentMethodEnabled = Annotated[bool | None, BeforeValidator(lambda value: None if value == "" else value)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DukaanHub API"
    environment: Literal["development", "test", "production"] = "development"
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
    payment_method_jazzcash_enabled: PaymentMethodEnabled = False
    payment_method_easypaisa_enabled: PaymentMethodEnabled = False
    payment_method_card_enabled: PaymentMethodEnabled = False
    payment_method_stripe_enabled: PaymentMethodEnabled = False
    frontend_base_url: str = "http://localhost:3000"
    google_client_secrets_file: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8001/api/v1/auth/google/callback"
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = 10.0
    email_from_address: str = ""
    email_from_name: str = "DukaanHub"
    email_admin_recipient: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _apply_payment_method_defaults(self):
        if self.payment_method_cash_on_delivery_enabled is None:
            self.payment_method_cash_on_delivery_enabled = True
        if self.payment_method_jazzcash_enabled is None:
            self.payment_method_jazzcash_enabled = False
        if self.payment_method_easypaisa_enabled is None:
            self.payment_method_easypaisa_enabled = False
        if self.payment_method_card_enabled is None:
            self.payment_method_card_enabled = False
        if self.payment_method_stripe_enabled is None:
            self.payment_method_stripe_enabled = False

        if self.is_production:
            if self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a random value of at least 32 characters in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must use a persistent production database, not SQLite")
            if self.admin_password == "Admin@12345" or len(self.admin_password) < 12:
                raise ValueError("ADMIN_PASSWORD must be changed to a strong value in production")
            if not self.frontend_base_url.startswith("https://"):
                raise ValueError("FRONTEND_BASE_URL must use HTTPS in production")
            if not self.google_redirect_uri.startswith("https://"):
                raise ValueError("GOOGLE_REDIRECT_URI must use HTTPS in production")
            if not self.cors_origin_list or any(origin == "*" or not origin.startswith("https://") for origin in self.cors_origin_list):
                raise ValueError("CORS_ORIGINS must contain explicit HTTPS origins in production")
            if self.cors_origin_regex:
                raise ValueError("CORS_ORIGIN_REGEX must be empty in production; list explicit origins instead")
            if not self.google_client_id or not self.google_client_secret:
                raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
