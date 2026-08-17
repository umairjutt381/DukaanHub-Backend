import logging
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.routers.admin import router as admin_router
from backend.app.api.v1.routers.auth import router as auth_router
from backend.app.api.v1.routers.cart import router as cart_router
from backend.app.api.v1.routers.catalog import router as catalog_router
from backend.app.api.v1.routers.health import router as health_router
from backend.app.api.v1.routers.misc import router as misc_router
from backend.app.api.v1.routers.orders import router as orders_router
from backend.app.api.v1.routers.payments import router as payments_router
from backend.app.core.config import get_settings
from backend.app.db.init_db import seed_data
from backend.app.db.migrations import apply_compatibility_migrations
from backend.app.db.session import Base, engine, SessionLocal
from backend.app.models import *  # noqa: F401,F403

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("dukaanhub")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="DukaanHub production-ready commerce API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skip static file mounting in serverless environment (Vercel)
# Static files should be served from a CDN or separate storage
if os.environ.get("VERCEL") != "1":
    uploads_path = Path(settings.upload_dir)
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    brand_path = ROOT_DIR / "public" / "brand"
    if brand_path.is_dir():
        app.mount("/brand", StaticFiles(directory=str(brand_path)), name="brand")

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(catalog_router, prefix=settings.api_v1_prefix)
app.include_router(cart_router, prefix=settings.api_v1_prefix)
app.include_router(orders_router, prefix=settings.api_v1_prefix)
app.include_router(payments_router, prefix=settings.api_v1_prefix)
app.include_router(misc_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)


# Skip startup event in serverless environment (Vercel)
# Database initialization should be handled via migrations
if os.environ.get("VERCEL") != "1":
    @app.on_event("startup")
    def startup_event():
        Base.metadata.create_all(bind=engine)
        apply_compatibility_migrations(engine)
        db = SessionLocal()
        try:
            seed_data(db)
            logger.info("Database initialized and seeded.")
        finally:
            db.close()


@app.get("/")
def root():
    return {"name": "DukaanHub API", "docs": "/docs", "health": "/api/v1/health"}
