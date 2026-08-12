from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from backend.app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

engine_kwargs = {}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, future=True, echo=False, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

