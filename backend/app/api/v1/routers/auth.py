import json
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user
from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.models import User
from backend.app.schemas.auth import AuthResponse, ChangePasswordRequest, LoginRequest, PasswordResetConfirmRequest, PasswordResetRequest, RegisterRequest
from backend.app.schemas.common import MessageResponse, UserRead
from backend.app.services.auth_service import AuthService
from backend.app.services.email_service import send_password_reset_email, send_registration_emails
from backend.app.models.password_reset import PasswordResetToken

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _safe_return_to(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or parsed.path in {"/login", "/register"} or parsed.path.startswith("/auth/"):
        return "/"
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
def register(background_tasks: BackgroundTasks, payload: RegisterRequest, db: Session = Depends(get_db)):
    user = AuthService(db).register(payload.full_name, payload.email, payload.password, payload.phone)
    background_tasks.add_task(send_registration_emails, user.email, user.full_name)
    token = create_access_token(subject=str(user.id), extra={"role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token, user = AuthService(db).login(payload.email, payload.password, payload.remember_me)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(background_tasks: BackgroundTasks, payload: PasswordResetRequest, db: Session = Depends(get_db)):
    # Always return the same message so account existence cannot be enumerated.
    user = db.query(User).filter(User.email == str(payload.email).strip().lower()).first()
    if user and user.is_active:
        raw_token = secrets.token_urlsafe(48)
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).update({"used_at": datetime.utcnow()})
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=get_settings().password_reset_expire_minutes),
        ))
        db.commit()
        reset_url = f"{get_settings().frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
        background_tasks.add_task(send_password_reset_email, user.email, user.full_name, reset_url)
    return {"message": "If an account exists for that email, a password reset link has been sent."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    now = datetime.utcnow()
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid or has expired.")
    user = db.query(User).filter(User.id == reset.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid or has expired.")
    user.hashed_password = AuthService(db).set_password(user, payload.new_password)
    reset.used_at = now
    db.commit()
    return {"message": "Password reset successfully. You can now sign in."}


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
        secure=settings.secure_cookies or request.url.scheme == "https",
        samesite="lax",
        path="/api/v1/auth/google",
    )
    response.set_cookie(
        "dukaanhub_google_return_to",
        safe_return_to,
        max_age=600,
        httponly=True,
        secure=settings.secure_cookies or request.url.scheme == "https",
        samesite="lax",
        path="/api/v1/auth/google",
    )
    return response


@router.get("/google/callback")
def google_callback(
    background_tasks: BackgroundTasks,
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

    is_new_account = db.query(User).filter(User.email == email).first() is None
    token, user = AuthService(db).login_or_create_google_user(email, str(profile.get("name") or ""))
    if is_new_account:
        background_tasks.add_task(send_registration_emails, user.email, user.full_name)
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
