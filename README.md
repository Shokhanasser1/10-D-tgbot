# Telegram Mini App Storefront

An e-commerce storefront that runs as a Telegram Mini App: catalog, cart, checkout with Stripe,
and order tracking. It launches with a cosmetics catalog but is built to take other niches
without code changes — products, categories and their attributes are all data.

This is **Spec 1 of 3**. The design lives in
[`docs/superpowers/specs/`](docs/superpowers/specs/2026-09-22-telegram-miniapp-storefront-design.md).
Not built yet: the courier/logistics engine with live GPS tracking (Spec 2) and the admin
panel UI (Spec 3). Until then, the catalog is managed through the internal API below, and
`Shipment` is a deliberately minimal placeholder for Spec 2 to extend.

| | |
|---|---|
| Backend | FastAPI (async), SQLAlchemy 2.0, PostgreSQL 16, Alembic |
| Frontend | React 19 + TypeScript + Vite, react-query, react-i18next (en / ru / uz) |
| Payments | Stripe Payment Element inside the Mini App, confirmed by webhook |
| Auth | Telegram `initData`, verified server-side (no passwords, no sessions) |

## Run everything with Docker

Requires Docker with Compose.

```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN (from @BotFather) and INTERNAL_API_TOKEN (a long random string).
docker compose up --build
```

The app is served at <http://localhost:8080>; the API is reachable at `/api/*` on the same
origin (nginx proxies it), so there is no CORS to configure. Migrations run on startup.

> **Telegram only opens HTTPS Mini Apps.** To try it in a real Telegram client, expose port 8080
> through a tunnel (e.g. `ngrok http 8080` or `cloudflared tunnel --url http://localhost:8080`),
> then in @BotFather set the bot's Mini App / menu button URL to the tunnel's `https://` address.
> Opened directly in a browser the app loads but every API call is rejected, because there is no
> `initData` to authenticate with.

### Add products

There is no admin UI yet. Either load a small demo catalog:

```bash
docker compose exec api python -m scripts.seed_demo_data
```

or manage the catalog through the token-protected internal API (send your `INTERNAL_API_TOKEN`
as `X-Internal-Token`). The interactive API docs are only served in local development
(`/docs` when `ENV=development`), never in the production-mode Docker stack:

```bash
TOKEN=...   # your INTERNAL_API_TOKEN
API=http://localhost:8080/api
H=(-H "X-Internal-Token: $TOKEN" -H "content-type: application/json")

curl "${H[@]}" -d '{"slug":"lipstick"}' $API/internal/categories
curl "${H[@]}" -d '{"category_id":1,"base_sku":"LIP-1","base_price":"19.99","status":"active"}' $API/internal/products
curl "${H[@]}" -d '{"product_id":1,"sku":"LIP-1-RED","price":"19.99","stock_qty":25,"attribute_values":{"shade":"red"}}' $API/internal/variants
curl "${H[@]}" -d '{"entity_type":"product","entity_id":1,"locale":"en","field":"name","value":"Velvet Lipstick"}' $API/internal/translations
```

A product only appears in the catalog when its `status` is `active`. Names and descriptions come
from translations (`en`, `ru`, `uz`) and fall back to `en` when a language is missing. Variants
carry the attribute values (`shade`, `size`, …) and the stock; the cart and orders reference
variants, not products.

### Stripe

Payments need Stripe keys in `.env` (use test-mode keys while developing): `STRIPE_SECRET_KEY`,
`STRIPE_PUBLISHABLE_KEY`, and `STRIPE_WEBHOOK_SECRET`. Without them the app runs and you can browse
and fill a cart, but checkout cannot create a payment.

An order becomes `paid` only when Stripe's webhook says so — never from the browser. Forward
webhooks locally with the Stripe CLI, and use its printed signing secret as `STRIPE_WEBHOOK_SECRET`:

```bash
stripe listen --forward-to localhost:8080/api/webhooks/stripe
```

In production, point a Stripe webhook endpoint at `https://<your-domain>/api/webhooks/stripe`
and subscribe it to `payment_intent.succeeded` and `payment_intent.payment_failed`. Test card:
`4242 4242 4242 4242`.

## Develop without Docker

Start only the database (or point `DATABASE_URL` at any Postgres 16):

```bash
docker compose up -d db
docker compose exec db psql -U postgres -c "CREATE DATABASE storefront_test;"   # used by pytest
```

**Backend** (Python 3.12+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # set TELEGRAM_BOT_TOKEN
alembic upgrade head
uvicorn app.main:app --reload                          # http://localhost:8000/docs
```

**Frontend** (Node 22+):

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                                            # http://localhost:5173
```

Outside Telegram there is no `initData`, so generate a signed one for the dev server. It is signed
with the bot token from `backend/.env` and expires after 24h:

```bash
cd backend && python -m scripts.make_dev_init_data
# paste the output into frontend/.env as VITE_DEV_MOCK_INIT_DATA, then restart `npm run dev`
```

The mock is only read by the dev server; production builds ignore it. Outside Telegram, action
buttons render in the page instead of on Telegram's native main button.

## Tests

```bash
cd backend && pytest                    # needs Postgres; includes a real migration round-trip
cd frontend && npm test                 # API is mocked with MSW; no backend needed
```

CI runs both, plus lint and the production build (`.github/workflows/ci.yml`).

## Layout

```
backend/app/
  api/routes/      HTTP layer — one router per resource
  services/        business logic (cart, checkout, orders, catalog, Stripe)
  models/          SQLAlchemy models        alembic/   migrations
  core/            initData verification, i18n, money, shipping pricing, errors
frontend/src/
  features/        catalog, cart, checkout, orders — each with api / hooks / components / screens
  shared/          Telegram SDK wrapper, API client, i18n, UI kit, design tokens
```

## Production notes

- Serve over HTTPS (Telegram requires it) and keep `.env` out of version control.
- Set a strong `INTERNAL_API_TOKEN` and `POSTGRES_PASSWORD`; the compose file refuses to start
  without the former. The database and API are published on `127.0.0.1` only.
- Prices and stock are read from the server at checkout — the browser is never trusted for amounts.
- Single currency (EUR) and flat-rate shipping with a free-over threshold
  (`SHIPPING_FLAT_RATE`, `FREE_SHIPPING_THRESHOLD`) for now.
