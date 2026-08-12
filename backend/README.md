# DukaanHub Backend

The DukaanHub backend is a FastAPI application that powers catalog, account,
cart, order, payment, and administration APIs. It uses SQLAlchemy for
persistence and SQLite by default.

## Run locally

Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env .env
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API is then available at:

- `http://127.0.0.1:8000/docs` — interactive OpenAPI documentation
- `http://127.0.0.1:8000/api/v1/health` — health check

The frontend's local environment points to this API at port `8000`.

## Development catalog

Populate the local store with 500 realistic demo products and matching,
locally cached product images:

```bash
.venv/bin/python -m backend.scripts.seed_catalog --count 500 --dry-run
.venv/bin/python -m backend.scripts.seed_catalog --count 500
```

The importer uses the public [DummyJSON product fixture feed](https://dummyjson.com/docs/products),
creates category-appropriate variants, and stores images under
`uploads/catalog-seed/`. It is idempotent: rerunning it updates the same
`DH-DJ-` products instead of adding duplicates. It seeds catalog records only
and never fabricates customers, orders, payments, refunds, or webhook events.

## Configuration

Settings are loaded from the repository-root `.env` file. Copy
`../.env` to get the supported keys.

`DATABASE_URL` defaults to the local SQLite database at `dukaanhub.db`.
PostgreSQL can be used by setting `DATABASE_URL` to a PostgreSQL SQLAlchemy
URL and installing a compatible PostgreSQL driver. Do not commit credentials
or real payment-gateway secrets.

On startup the application creates the configured database tables and seeds
the default data. Change `SECRET_KEY` and the default admin credentials before
any production deployment.

## Project layout

```text
backend/
├── app/
│   ├── api/v1/routers/  # HTTP endpoints and dependency injection
│   ├── core/            # Settings, security, and dependencies
│   ├── db/              # SQLAlchemy engine/session and seed data
│   ├── domain/          # Domain-level values such as payment enums
│   ├── models/          # SQLAlchemy models
│   ├── repositories/    # Query and persistence helpers
│   ├── schemas/         # Pydantic request and response models
│   └── services/        # Business logic and payment integrations
├── main.py              # ASGI entry-point export
└── requirements.txt
```

Keep routers thin: request and response models belong in `app/schemas`, while
business logic belongs in services or repositories.

## Stripe Checkout

Stripe is disabled by default. After installing dependencies, set these only in
your deployment's secret manager or local `.env` file (never commit them):

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
PAYMENT_METHOD_STRIPE_ENABLED=true
FRONTEND_BASE_URL=https://your-store.example
```

Create a Stripe webhook endpoint at
`https://your-api.example/api/v1/payments/stripe/webhook` for
`checkout.session.completed`, `checkout.session.async_payment_succeeded`,
`checkout.session.async_payment_failed`, and `checkout.session.expired`.
Set `NEXT_PUBLIC_ENABLE_STRIPE_PAYMENTS=true` in `frontend/.env.local` only
after the backend key and webhook have been configured. The browser redirects
to Stripe Checkout; card data does not reach DukaanHub.
