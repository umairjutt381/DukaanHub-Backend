from backend.app.api.v1.routers.auth import _safe_return_to


def test_safe_return_to_accepts_internal_application_paths() -> None:
    assert _safe_return_to("/checkout?step=delivery") == "/checkout?step=delivery"


def test_safe_return_to_rejects_external_and_auth_paths() -> None:
    assert _safe_return_to("https://attacker.example") == "/account"
    assert _safe_return_to("//attacker.example/path") == "/account"
    assert _safe_return_to("/auth/google/callback") == "/account"
    assert _safe_return_to("/login") == "/account"
