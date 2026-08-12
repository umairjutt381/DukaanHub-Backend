# DukaanHub Backend

FastAPI backend for DukaanHub.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn backend.app.main:app --reload --port 8000
```

## Vercel

Import this repository as a separate Vercel project with the repository root
as Root Directory. The included `vercel.json` deploys `api/index.py` and
routes `/api/*` to FastAPI.

Configure `DATABASE_URL` with a managed PostgreSQL connection string,
`SECRET_KEY`, `CORS_ORIGINS` with the frontend URL, and `FRONTEND_BASE_URL`.
Do not use SQLite for production because Vercel filesystem storage is
ephemeral.
# DukaanHub-Backend
