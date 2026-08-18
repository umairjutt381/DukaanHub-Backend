import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def production_settings(**overrides):
    values = {
        "environment": "production",
        "secret_key": "a" * 48,
        "database_url": "postgresql+psycopg2://user:password@db.example/dukaanhub",
        "admin_password": "A-strong-production-password-123",
        "frontend_base_url": "https://store.example",
        "cors_origins": "https://store.example",
        "cors_origin_regex": "",
        "google_client_id": "client.apps.googleusercontent.com",
        "google_client_secret": "secret",
        "google_redirect_uri": "https://api.example/api/v1/auth/google/callback",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_accept_explicit_secure_configuration() -> None:
    assert production_settings().is_production


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("secret_key", "change-me-in-production"),
        ("database_url", "sqlite:///./dukaanhub.db"),
        ("admin_password", "Admin@12345"),
        ("frontend_base_url", "http://store.example"),
        ("cors_origins", "*"),
        ("google_redirect_uri", "http://api.example/api/v1/auth/google/callback"),
    ],
)
def test_production_settings_reject_unsafe_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        production_settings(**{field: value})
