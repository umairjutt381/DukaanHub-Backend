import sys
import os
from pathlib import Path

# Add the project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the FastAPI app and expose it for Vercel
from backend.app.main import app as asgi_app
from backend.app.db.session import Base, engine
from backend.app.db.migrations import apply_compatibility_migrations
from backend.app.db.init_db import seed_data
from backend.app.db.session import SessionLocal

# Initialize database on first load in Vercel
if os.environ.get("VERCEL") == "1":
    Base.metadata.create_all(bind=engine)
    apply_compatibility_migrations(engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()

# Vercel expects the ASGI app to be available as the module-level variable named 'app'
app = asgi_app

# For Vercel serverless functions, we need to handle the ASGI app differently
# Vercel's Python runtime will call this module and expect an ASGI app
lambda_handler = app
