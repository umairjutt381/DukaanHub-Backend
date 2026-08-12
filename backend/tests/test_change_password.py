import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.security import get_password_hash, verify_password
from backend.app.db.session import Base
from backend.app.models import User
from backend.app.schemas.auth import ChangePasswordRequest
from backend.app.services.auth_service import AuthService


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def user(db: Session) -> User:
    account = User(
        full_name="Password Test",
        email="password@example.com",
        hashed_password=get_password_hash("CurrentPass123"),
        role="customer",
        is_active=True,
        is_verified=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_change_password_rejects_incorrect_current_password(db: Session, user: User) -> None:
    with pytest.raises(HTTPException) as exc_info:
        AuthService(db).change_password(user, "WrongPass123", "ReplacementPass123")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Current password is incorrect"
    assert verify_password("CurrentPass123", user.hashed_password)


def test_change_password_rejects_password_reuse(db: Session, user: User) -> None:
    with pytest.raises(HTTPException) as exc_info:
        AuthService(db).change_password(user, "CurrentPass123", "CurrentPass123")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "New password must be different from the current password"


def test_change_password_rejects_password_below_project_minimum() -> None:
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="CurrentPass123", new_password="short")


def test_change_password_updates_credentials(db: Session, user: User) -> None:
    AuthService(db).change_password(user, "CurrentPass123", "ReplacementPass123")
    db.refresh(user)

    assert not verify_password("CurrentPass123", user.hashed_password)
    assert verify_password("ReplacementPass123", user.hashed_password)

    token, authenticated_user = AuthService(db).login(user.email, "ReplacementPass123")
    assert token
    assert authenticated_user.id == user.id
