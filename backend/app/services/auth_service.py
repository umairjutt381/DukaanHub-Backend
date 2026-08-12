from datetime import timedelta
import secrets
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import create_access_token, get_password_hash, verify_password
from backend.app.models import User


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, full_name: str, email: str, password: str, phone: str | None = None) -> User:
        if self.db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user = User(
            full_name=full_name,
            email=email.lower(),
            phone=phone,
            hashed_password=get_password_hash(password),
            role="customer",
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(self, email: str, password: str, remember_me: bool = False) -> tuple[str, User]:
        user = self.db.query(User).filter(User.email == email.lower()).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        settings = get_settings()
        expires = timedelta(days=settings.refresh_token_expire_days if remember_me else 1)
        token = create_access_token(subject=str(user.id), expires_delta=expires, extra={"role": user.role})
        return token, user

    def login_or_create_google_user(self, email: str, full_name: str) -> tuple[str, User]:
        normalized_email = email.strip().lower()
        user = self.db.query(User).filter(User.email == normalized_email).first()

        if user and not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

        if not user:
            user = User(
                full_name=full_name.strip() or normalized_email.split("@", 1)[0],
                email=normalized_email,
                phone=None,
                hashed_password=get_password_hash(secrets.token_urlsafe(48)),
                role="customer",
                is_active=True,
                is_verified=True,
            )
            self.db.add(user)
        else:
            user.is_verified = True
            if not user.full_name and full_name.strip():
                user.full_name = full_name.strip()

        self.db.commit()
        self.db.refresh(user)
        token = create_access_token(subject=str(user.id), extra={"role": user.role})
        return token, user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        if verify_password(new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from the current password",
            )

        user.hashed_password = get_password_hash(new_password)
        self.db.add(user)
        self.db.commit()
