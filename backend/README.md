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
cp .env.example .env
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```

The API is then available at:

- `http://127.0.0.1:8001/docs` — interactive OpenAPI documentation
- `http://127.0.0.1:8001/api/v1/health` — health check

The frontend's local environment points to this API at port `8001`.

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

Settings are loaded from the repository-root `.env` file. Copy `.env.example`
to `.env` to get the supported keys.

`DATABASE_URL` defaults to the local SQLite database at `dukaanhub.db`.
PostgreSQL can be used by setting `DATABASE_URL` to a PostgreSQL SQLAlchemy
URL and installing a compatible PostgreSQL driver. Do not commit credentials
or real payment-gateway secrets.

Local startup creates the configured database tables and seeds default data.
Serverless production imports never mutate or seed the database; initialize or
migrate the production database as a separate deployment step.

## Production configuration

Set `ENVIRONMENT=production`. Production startup intentionally fails when the
JWT secret is weak, SQLite is selected, the frontend URL is not HTTPS, or CORS
contains wildcard/non-HTTPS origins. At minimum configure:

```env
ENVIRONMENT=production
SECRET_KEY=<random-value-of-at-least-32-characters>
DATABASE_URL=postgresql+psycopg2://...
FRONTEND_BASE_URL=https://dukaan-hub-frontend.vercel.app
CORS_ORIGINS=https://dukaan-hub-frontend.vercel.app
CORS_ORIGIN_REGEX=
GOOGLE_CLIENT_ID=<google-web-client-id>
GOOGLE_CLIENT_SECRET=<google-web-client-secret>
GOOGLE_REDIRECT_URI=https://your-stable-backend-domain/api/v1/auth/google/callback
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<smtp-account>
SMTP_PASSWORD=<smtp-app-password>
SMTP_USE_TLS=true
EMAIL_FROM_ADDRESS=<verified-sender-address>
EMAIL_FROM_NAME=DukaanHub
EMAIL_ADMIN_RECIPIENT=<optional-store-notification-address>
```

Register that exact `GOOGLE_REDIRECT_URI` in Google Cloud Console. Register the
frontend production origin as an authorized JavaScript origin. Preview URLs
need separate explicit CORS and Google entries; do not use a temporary Vercel
deployment URL as the production API base.

Transactional email is sent after a new account is registered, after an
order is created, and when an administrator updates an order status. Customers receive welcome, order-confirmation, and order-status messages;
when `EMAIL_ADMIN_RECIPIENT` is set, the store also receives new-account and
new-order notifications. SMTP delivery runs as a background task and a mail
provider failure is logged without failing signup or checkout.

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
