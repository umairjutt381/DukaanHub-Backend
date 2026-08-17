import json
import secrets
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user
from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.schemas.auth import AuthResponse, ChangePasswordRequest, LoginRequest, RegisterRequest
from backend.app.schemas.common import MessageResponse, UserRead
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _safe_return_to(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/account"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or parsed.path in {"/login", "/register"} or parsed.path.startswith("/auth/"):
        return "/account"
    return value


def _callback_redirect(callback_url: str, return_to: str, error: str) -> RedirectResponse:
    params = urlencode({"error": error, "return_to": return_to})
    return RedirectResponse(f"{callback_url}?{params}", status_code=status.HTTP_302_FOUND)


def _google_credentials() -> tuple[str, str]:
    settings = get_settings()
    if settings.google_client_id and settings.google_client_secret:
        return settings.google_client_id, settings.google_client_secret
    if not settings.google_client_secrets_file:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    try:
        payload = json.loads(Path(settings.google_client_secrets_file).expanduser().read_text(encoding="utf-8"))
        credentials = payload.get("web") or payload.get("installed") or {}
        client_id = credentials["client_id"]
        client_secret = credentials["client_secret"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in configuration is invalid") from exc
    return client_id, client_secret


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = AuthService(db).register(payload.full_name, payload.email, payload.password, payload.phone)
    token = create_access_token(subject=str(user.id), extra={"role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token, user = AuthService(db).login(payload.email, payload.password, payload.remember_me)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/google/start")
def google_start(request: Request, return_to: str | None = Query(default=None)):
    client_id, _ = _google_credentials()
    settings = get_settings()
    oauth_state = secrets.token_urlsafe(32)
    safe_return_to = _safe_return_to(return_to)
    params = {
        "client_id": client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": oauth_state,
        "prompt": "select_account",
        "access_type": "online",
    }
    response = RedirectResponse(f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        "dukaanhub_google_oauth_state",
        oauth_state,
        max_age=600,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/api/v1/auth/google",
    )
    response.set_cookie(
        "dukaanhub_google_return_to",
        safe_return_to,
        max_age=600,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/api/v1/auth/google",
    )
    return response


@router.get("/google/callback")
def google_callback(
    code: str | None = Query(default=None),
    state_value: str | None = Query(default=None, alias="state"),
    error: str | None = Query(default=None),
    oauth_state: str | None = Cookie(default=None, alias="dukaanhub_google_oauth_state"),
    oauth_return_to: str | None = Cookie(default=None, alias="dukaanhub_google_return_to"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    callback_url = f"{settings.frontend_base_url.rstrip('/')}/auth/google/callback"
    return_to = _safe_return_to(oauth_return_to)
    if error:
        return _callback_redirect(callback_url, return_to, "access_denied")
    if not code or not state_value or not oauth_state or not secrets.compare_digest(state_value, oauth_state):
        return _callback_redirect(callback_url, return_to, "invalid_state")

    client_id, client_secret = _google_credentials()
    try:
        with httpx.Client(timeout=15.0) as client:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            google_access_token = token_response.json()["access_token"]
            user_response = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {google_access_token}"})
            user_response.raise_for_status()
            profile = user_response.json()
    except (httpx.HTTPError, KeyError, ValueError):
        return _callback_redirect(callback_url, return_to, "google_exchange_failed")

    email = str(profile.get("email") or "").strip().lower()
    if not email or not profile.get("email_verified"):
        return _callback_redirect(callback_url, return_to, "email_not_verified")

    token, _ = AuthService(db).login_or_create_google_user(email, str(profile.get("name") or ""))
    response = RedirectResponse(f"{callback_url}?{urlencode({'return_to': return_to})}#access_token={token}", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("dukaanhub_google_oauth_state", path="/api/v1/auth/google")
    response.delete_cookie("dukaanhub_google_return_to", path="/api/v1/auth/google")
    return response


@router.get("/me", response_model=UserRead)
def me(user=Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    AuthService(db).change_password(user, payload.current_password, payload.new_password)
    return {"message": "Password updated successfully"}
