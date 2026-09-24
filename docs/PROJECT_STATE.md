# Project state (handoff)

Snapshot: 2026-09-24, branch `main`, HEAD `8f9c581`, 26 commits, **no git remote, nothing pushed**.
Working tree was clean at the time of writing. Written for another engineer or AI picking this up cold.

## 1. What this is

A **Telegram Mini App e-commerce platform**. It launches with cosmetics but is meant to take other
niches through data (categories, attributes, translations), not code changes. The owner runs their
**own couriers** (no third-party carrier). Work was split into three specs:

| Spec | Scope | Status |
|---|---|---|
| 1 Storefront | catalog, cart, Stripe checkout, orders, en/ru/uz, light minimalist UI | **done**, committed |
| 2 Own courier delivery + live GPS | courier pool/claim, Telegram Live Location tracking, delivery pin, customer map | **done**, committed (10 commits `9a386c6`..`8f9c581`) |
| 3 Admin panel | UI for catalog, couriers, orders | **not started** |

Designs are in `docs/superpowers/specs/`. Spec 2's §16 "Implementation notes" lists where the build
refined the design; read it before trusting the rest of that document. `README.md` covers running,
Stripe, and the whole courier setup (section "Couriers & tracking").

The product owner writes transliterated Russian; the working language with them is Russian, while code,
docs and commit messages are English.

## 2. Stack

- **Backend** `backend/`: FastAPI (async), SQLAlchemy 2.0 async + asyncpg, Alembic, PostgreSQL 16,
  pydantic-settings, ruff (line length 100). Python 3.12 in Docker/CI, 3.14 locally.
- **Frontend** `frontend/`: React 19, TypeScript strict, Vite, react-router v7, react-query,
  react-i18next (en/ru/uz), CSS Modules, Leaflet 1.9 + react-leaflet 5, oxlint, prettier,
  Vitest + Testing Library + MSW (`onUnhandledRequest: 'error'`).
- **Runtime** `docker-compose.yml`: `db` (Postgres), `api`, `web` (nginx serving the SPA and proxying
  `/api/` to the API, so the browser is same-origin and needs no CORS).
- **Auth**: Telegram `initData`, verified server-side with HMAC (`Authorization: tma <initData>`).
  No passwords or sessions. `/internal/*` uses a static `X-Internal-Token`.
- **CI** `.github/workflows/ci.yml`: backend `ruff check app tests scripts` + `pytest --cov`;
  frontend `npm run lint`, `npm run build` (runs `tsc -b`, which also type-checks tests), `npm test`.

## 3. Verified state

- Backend: **253 tests pass**, 97% coverage, ruff clean. Alembic head **`6293a99b0b9c`**.
- Frontend: **233 tests pass**, lint/prettier/`tsc`/build clean.
- Manually verified against a real API + database over HTTP (whole courier flow), and in a real
  browser (map tiles, markers, pin tap, courier claim flow, live marker update).
- **Not verified**: a real Telegram client with a real bot webhook over HTTPS; `docker compose build`
  of the updated images (only `docker compose config` was run).

## 4. Repository map

```
backend/app/
  api/routes/     catalog, cart, checkout, orders, webhooks (stripe + telegram), courier,
                  internal (catalog admin), internal_couriers ; api/deps.py = auth dependencies
  services/       business logic. dispatch_service (claim/release/pickup/deliver/force_release),
                  courier_state (locks, location upsert/purge), courier_service (pool/deliveries reads),
                  courier_admin_service, location_service (webhook ingestion), tracking_service,
                  order_service, checkout_service, stripe_service, catalog(_admin)_service, cart_service
  models/         SQLAlchemy models; enums.py has ShipmentStatus / ACTIVE_SHIPMENT_STATUSES
  schemas/        pydantic I/O models
  core/           initData verification, exceptions + global handlers, geo, money, shipping pricing
backend/scripts/  make_dev_init_data, seed_demo_data, seed_courier_demo, set_telegram_webhook
backend/tests/    courier_factories.py = shared fixtures/factories for courier tests
frontend/src/
  features/       catalog, cart, checkout, orders, courier  (api / hooks / components / screens)
  shared/         api client, telegram wrapper, i18n, map (Leaflet, lazy-loaded), time, ui kit, styles
  test/           MSW handlers, fixtures, mocks (reactLeaflet, courierBackend), setup
```

## 5. HTTP API (as of HEAD)

Customer (initData): `GET /catalog/categories|products|products/{id}`, `GET/POST /cart/items`,
`PATCH/DELETE /cart/items/{id}`, `POST /checkout`, `GET /orders`, `GET /orders/{id}`,
`GET /orders/{id}/tracking`.

Courier (initData + active courier row, else 403): `GET /courier/me|pool|deliveries`,
`POST /courier/deliveries/{shipment_id}/claim|release|pickup|deliver`.

Webhooks: `POST /webhooks/stripe` (signature), `POST /webhooks/telegram`
(`X-Telegram-Bot-Api-Secret-Token`; empty `TELEGRAM_WEBHOOK_SECRET` means 404).

Owner (`X-Internal-Token`): catalog writes `POST /internal/categories|products|variants|attributes|translations`,
`POST /internal/products/{id}/images`, `PATCH` for categories/products/variants/attributes;
couriers `POST/GET /internal/couriers`, `PATCH /internal/couriers/{id}`;
shipments `GET /internal/shipments?status=` (repeatable, default active) and
`POST /internal/shipments/{id}/release`.

Swagger (`/docs`) is served only when `ENV=development`.

## 6. Domain rules worth knowing before changing anything

**Lifecycle.** `Shipment` and `Order` move together:
`processing/paid` -claim-> `assigned/processing` -pickup-> `shipped/shipped` -deliver-> `delivered/delivered`;
release (only before pickup) goes back to `processing/paid`. The Stripe webhook creates the shipment.
`mark_order_paid` ignores orders already past payment (a redelivered Stripe event must not regress a
`shipped` order).

**Concurrency.** Every transition is a guarded `UPDATE … WHERE status=… [AND courier_id=…] RETURNING`.
Lock order everywhere: **courier row (`SELECT … FOR UPDATE`) → shipment → order → location**. The owner's
`force_release` reads the courier unlocked, then locks it first. Guarded UPDATEs bypass the SQLAlchemy
identity map, so services return schemas built from column selects, never stale ORM entities; after a
partial write that fails, `await db.rollback()` before raising.

**Errors.** Service layer raises domain errors mapped globally: NotFound 404, Conflict 409 (optional
`code`: `shipment_taken`, `delivery_limit_reached`, `invalid_state`), Forbidden 403, BadRequest 400,
InvalidInitData 401, IntegrityError 400. 422 bodies contain only `type`/`loc`/`msg` (never the input).
Someone else's order/shipment is 404, never 403, so existence is not revealed.

**Location privacy (data minimisation).** Only the latest position per courier, only for couriers who
hold an active delivery, deleted when their last delivery ends or on deactivation. A customer sees the
courier's first name and position only while their own order is `shipped`; never a phone or Telegram ID.
The pool shows city/street/item count only; full address, phone and notes appear after claiming.

**GPS transport.** Mini Apps cannot read GPS in the background, so couriers share a Telegram *Live
Location* in the bot chat; Telegram posts each update to the webhook (first `message`, then
`edited_message`). One update consumer per bot: webhook and `getUpdates` are mutually exclusive.
`is_stale` is computed server-side (`LOCATION_STALE_SECONDS`, default 120); a stationary courier looks
stale because Telegram only sends updates on movement.

**Delivery pin.** Optional `latitude`/`longitude` on checkout, both-or-neither, strict in-range numbers.
`GET /orders/{id}` returns them to the owner. Older orders without the keys still load.

**Frontend polling.** No WebSocket. Order: 2 s while `pending_payment`, 10 s while paid/processing/shipped.
Tracking: 5 s while `shipped`, 10 s while waiting, stops after delivery. Courier pool 10 s, deliveries 5 s.
Timeline labels ("Payment received / Courier assigned / Out for delivery / Order delivered") differ on
purpose from `orders.status.*` labels; `locales.test.ts` fails CI on missing keys/placeholders in any language.

## 7. Configuration

Root `.env` (copy `.env.example`): `TELEGRAM_BOT_TOKEN`, `INTERNAL_API_TOKEN` (both required by compose),
Stripe keys (optional), `POSTGRES_*`, `SHIPPING_FLAT_RATE` (4.99), `FREE_SHIPPING_THRESHOLD` (50.00),
ports, and for Spec 2: `TELEGRAM_WEBHOOK_SECRET` (charset `A-Za-z0-9_-`, 1–256; empty = webhook off),
`TELEGRAM_BOT_USERNAME`, `MAX_ACTIVE_DELIVERIES_PER_COURIER` (3), `LOCATION_STALE_SECONDS` (120),
and `MAP_TILE_URL` / `MAP_DEFAULT_CENTER` / `MAP_ATTRIBUTION` (baked into the web image as `VITE_MAP_*`;
empty = public OpenStreetMap, which is for light use only).
`backend/.env` and `frontend/.env` exist locally with fake dev values and are gitignored.

## 8. How to run and test

```bash
docker compose up -d db                       # Postgres; also needs DB `storefront_test` for pytest
cd backend && alembic upgrade head && uvicorn app.main:app --reload
cd backend && ruff check app tests scripts && pytest -q --cov=app
cd frontend && npm install && npm run dev     # bind Vite with --host 127.0.0.1 if curl-ing it
cd frontend && npm run lint && npm test && npm run build
python -m scripts.make_dev_init_data <telegram_id>    # signed initData for dev outside Telegram
python -m scripts.seed_demo_data                      # demo catalog
python -m scripts.seed_courier_demo --courier 222 --customer 111 --lat 52.52 --lng 13.405
```

Manual end-to-end recipe: run uvicorn with per-process overrides instead of editing `.env`
(`TELEGRAM_WEBHOOK_SECRET=... TELEGRAM_BOT_USERNAME=... CORS_ORIGINS='["http://127.0.0.1:5173","http://127.0.0.1:5174",…]'`),
two Vite servers (customer 5173, courier 5174) each with `VITE_DEV_MOCK_INIT_DATA` for a different Telegram ID,
register the courier via `POST /internal/couriers`, seed an order, then POST a location update to
`/webhooks/telegram` with the secret header (payload example in README).

## 9. Environment gotchas (Windows dev machine)

- Docker Desktop is not running after a session resume; start it, wait for `docker info`, then `docker compose up -d db`.
  Backend tests need Postgres and fail with `ConnectionRefusedError` otherwise.
- Git Bash rewrites args starting with `/` (use `MSYS_NO_PATHCONV=1`). Git Bash `/tmp` differs from Windows Python's `/tmp`.
- `cat > f <<'EOF'` with quotes in the body sometimes fails to parse in the tool shell; write files with an editor tool.
- `ruff format .` / `prettier --write .` on whole trees touch unrelated files; format only what you changed.
- Tests: `db_session` is one connection in one outer transaction (savepoints), so real two-session races need the
  independent-session fixtures in `test_courier_concurrency.py` (they commit and TRUNCATE afterwards).
  Non-native enums are stored as VARCHAR, so adding an enum value needs no type migration.
- `tsc -b` type-checks test files too and `erasableSyntaxOnly` forbids TS `enum`; use string unions.
- A hidden/automation browser tab pauses react-query polling; screenshots of the automation browser are unreliable here.

## 10. Open items and suggested next steps

1. **Spec 3 — admin panel.** New feature: run the `brainstorming` skill and get the design approved before code.
   Important finding for its design: the catalog admin API is **write-only** (`POST/PATCH` under `/internal`,
   no `GET` lists for categories/products/variants/attributes/translations, and no order listing). Only couriers
   and shipments have `GET`. An admin UI will need read endpoints (and probably an order list/detail view for the
   owner) before it can show anything. It should call the same `/internal/*` endpoints, not a parallel API.
2. Try the real thing once: HTTPS tunnel (`ngrok`/`cloudflared`) → `python -m scripts.set_telegram_webhook https://<origin>`
   → a real courier account sharing Live Location from a phone. `--info` shows Telegram's `last_error_message`.
3. `docker compose build && up` with the updated Dockerfile/compose, then `curl -X POST localhost:8080/api/webhooks/telegram`
   (expect 404 with an empty secret, 403 with a wrong one).
4. Before real traffic: set `MAP_TILE_URL`/`MAP_ATTRIBUTION` for a proper tile provider; use strong `INTERNAL_API_TOKEN`
   and `POSTGRES_PASSWORD`; serve over HTTPS.
5. Push: there is no remote yet. Decide where the repository lives before CI can run.

## 11. Assumptions the product owner has not explicitly confirmed

Single currency (EUR), flat-rate shipping (€4.99, free over €50), price taken at checkout time; the owner
registers couriers manually; at most 3 active deliveries per courier; "Delivered" is a plain button (no PIN or
proof of delivery); OpenStreetMap tiles via Leaflet.

**Out of scope by design (Spec 2 §14):** dispatcher UI, Telegram notifications to customers, proof of delivery,
failed deliveries/returns, routes/ETA/geocoding, courier shifts, earnings, location history, multiple warehouses.
