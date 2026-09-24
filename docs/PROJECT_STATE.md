# Project state (handoff)

Snapshot: 2026-09-24 (updated after Spec 4 design), branch `main`, **no git remote, nothing pushed**.
Working tree was clean at the time of writing. Written for another engineer or AI picking this up cold.

## 1. What this is

A **Telegram Mini App e-commerce platform**. It launches with cosmetics but is meant to take other
niches through data (categories, attributes, translations), not code changes. The owner runs their
**own couriers** (no third-party carrier). Work was split into three specs:

| Spec | Scope | Status |
|---|---|---|
| 1 Storefront | catalog, cart, Stripe checkout, orders, en/ru/uz, light minimalist UI | **done**, committed |
| 2 Own courier delivery + live GPS | courier pool/claim, Telegram Live Location tracking, delivery pin, customer map | **done**, committed (10 commits `9a386c6`..`8f9c581`) |
| 3 Admin panel | roles, catalog, orders with cancel + refund, couriers + map, summary, admins | **done**, committed |
| 4 Stock reservation | reserve `stock_qty` at checkout, 15-min hold, expiry sweeper, cart restore, refund of late payments | **designed, not implemented** |

Designs are in `docs/superpowers/specs/`. Spec 2's §16 and Spec 3's §14 "Implementation notes" list
where the build refined each design; read them before trusting the rest of those documents.
`README.md` covers running, Stripe, the courier setup ("Couriers & tracking") and the admin panel
("Admin panel": first owner, roles, browser sign-in, refunds, photos).

The product owner writes transliterated Russian; the working language with them is Russian, while code,
docs and commit messages are English. Exception: two teaching docs are in Russian on purpose —
`docs/LAUNCH_GUIDE_RU.md` (full launch: bot, `.env`, tunnel, admin sign-in, Stripe, troubleshooting) and
`INSTRUKTSII_ZAPUSKA_SERVEROV.md` in the root (running locally: dev mode vs Docker, checks, tests).
The owner teaches students with this project, so explanations should say *why*, not only *what*.

## 1a. Local machine state (as of this snapshot)

- Root `.env` exists (gitignored): real bot token for **@ecosmetics10bot**, generated `INTERNAL_API_TOKEN`,
  `ADMIN_SESSION_SECRET`, `TELEGRAM_WEBHOOK_SECRET`; owner `ADMIN_BOOTSTRAP_TELEGRAM_IDS=665823713`;
  `SHOP_TIMEZONE=Asia/Tashkent`; map centred on Tashkent. `POSTGRES_PASSWORD` left at the default on purpose:
  the `pgdata` volume was created with it (changing it needs `ALTER USER`, see the launch guide §4.3).
- `backend/.env` (dev, fake bot token) gained admin settings: owner 665823713, `ADMIN_COOKIE_SECURE=false`,
  `MEDIA_ROOT=./media`, `SHOP_TIMEZONE=Asia/Tashkent`.
- Docker stack (`db`, `api`, `web`) was left **running** in production mode on :8080 (api on 127.0.0.1:8000).
  Dev mode needs `docker compose stop api web` first (same port 8000).
- The owner pasted the real bot token into chat; they were advised to `/revoke` it in @BotFather and update
  root `.env`. Not yet confirmed done.
- **Still manual (owner's accounts needed):** https tunnel + BotFather Menu Button, `/setdomain` for browser
  admin sign-in, Stripe test keys + webhook with `payment_intent.*` and `refund.created|updated|failed`.

## 2. Stack

- **Backend** `backend/`: FastAPI (async), SQLAlchemy 2.0 async + asyncpg, Alembic, PostgreSQL 16,
  pydantic-settings, ruff (line length 100). Python 3.12 in Docker/CI, 3.14 locally.
- **Frontend** `frontend/`: React 19, TypeScript strict, Vite, react-router v7, react-query,
  react-i18next (en/ru/uz), CSS Modules, Leaflet 1.9 + react-leaflet 5, oxlint, prettier,
  Vitest + Testing Library + MSW (`onUnhandledRequest: 'error'`).
- **Runtime** `docker-compose.yml`: `db` (Postgres), `api`, `web` (nginx serving the SPA and proxying
  `/api/` to the API, so the browser is same-origin and needs no CORS).
- **Auth**: Telegram `initData`, verified server-side with HMAC (`Authorization: tma <initData>`).
  No passwords. `/internal/*` (the admin API) accepts `X-Internal-Token` (scripts; acts as owner),
  initData of an active admin, or a signed `admin_session` cookie from the Telegram Login Widget.
- **CI** `.github/workflows/ci.yml`: backend `ruff check app tests scripts` + `pytest --cov`;
  frontend `npm run lint`, `npm run build` (runs `tsc -b`, which also type-checks tests), `npm test`.

## 3. Verified state

- Backend: **403 tests pass**, 97% coverage, ruff clean. Alembic head **`bbb147ebf681`**.
- Frontend: **306 tests pass**, lint/prettier/`tsc`/build clean (one pre-existing oxlint warning in
  `router.tsx`).
- Manually verified against a real API + database over HTTP (whole courier flow), and in a real
  browser (map tiles, markers, pin tap, courier claim flow, live marker update).
- Admin panel verified in a browser against the real API + DB (summary, cancel, photo upload, phone
  layout, courier map); production images built and run (upload through nginx, `/media/` served).
- **Not verified**: a real Telegram client with a real bot webhook over HTTPS; the Login Widget on a
  real domain; real Stripe refunds.

## 4. Repository map

```
backend/app/
  api/routes/     catalog, cart, checkout, orders, webhooks (stripe + telegram), courier,
                  internal_products, internal_couriers, internal_orders, internal_stats,
                  internal_admins, internal_auth ; api/deps.py = auth, AdminPrincipal, require_admin
  services/       business logic. dispatch_service (claim/release/pickup/deliver/force_release),
                  courier_state (locks, location upsert/purge), courier_service (pool/deliveries reads),
                  courier_admin_service, location_service (webhook ingestion), tracking_service,
                  order_service, checkout_service, stripe_service, catalog(_admin)_service, cart_service,
                  admin_service, catalog_admin_query_service, image_service, stock_service,
                  order_admin_service (list/detail/cancel/refund), stats_service
  models/         SQLAlchemy models; enums.py has ShipmentStatus / ACTIVE_SHIPMENT_STATUSES / AdminRole
  schemas/        pydantic I/O models
  core/           initData + Login Widget verification, admin_session, images (Pillow), rate_limit,
                  exceptions + global handlers, geo, money, shipping pricing
backend/scripts/  make_dev_init_data, seed_demo_data, seed_courier_demo, set_telegram_webhook
backend/tests/    courier_factories.py / admin_factories.py = shared fixtures and factories
frontend/src/
  features/       catalog, cart, checkout, orders, courier, admin  (api / hooks / components / screens)
                  admin is lazy-loaded at /admin/*; only admin/entry.ts is in the main chunk
  shared/         api client, telegram wrapper, i18n, map (Leaflet, lazy-loaded), time, ui kit, styles
  test/           MSW handlers, fixtures, adminFixtures, mocks (reactLeaflet, courierBackend,
                  adminBackend), setup
```

## 5. HTTP API (as of HEAD)

Customer (initData): `GET /catalog/categories|products|products/{id}`, `GET/POST /cart/items`,
`PATCH/DELETE /cart/items/{id}`, `POST /checkout`, `GET /orders`, `GET /orders/{id}`,
`GET /orders/{id}/tracking`.

Courier (initData + active courier row, else 403): `GET /courier/me|pool|deliveries`,
`POST /courier/deliveries/{shipment_id}/claim|release|pickup|deliver`.

Webhooks: `POST /webhooks/stripe` (signature), `POST /webhooks/telegram`
(`X-Telegram-Bot-Api-Secret-Token`; empty `TELEGRAM_WEBHOOK_SECRET` means 404).

Admin, `/internal/*` (roles O=owner, C=catalog_manager, D=dispatcher; the internal token counts as O).
No credentials is 401; wrong token, non-admin or wrong role is 403.
- identity: `POST /internal/auth/telegram` (widget payload → cookie), `POST /internal/auth/logout`,
  `GET /internal/me` (any role); `GET/POST /internal/admins`, `PATCH /internal/admins/{id}` (O).
- catalog (O, C): `GET /internal/categories|attributes`, `GET /internal/products?status=&category_id=&q=&limit=&offset=`,
  `GET /internal/products/{id}`; writes `POST /internal/categories|products|variants|attributes|translations`,
  `PATCH` for categories/products/variants/attributes, `POST /internal/products/{id}/images` (JSON url **or**
  multipart upload), `PATCH/DELETE /internal/images/{id}`.
- orders (O, D): `GET /internal/orders?status=&q=&from=&to=&shortfall=`, `GET /internal/orders/{id}`,
  `POST /internal/orders/{id}/cancel {reason}`, `POST /internal/orders/{id}/refund` (retry a failed refund).
- couriers (O, D): `POST/GET /internal/couriers` (list has `active_deliveries`), `PATCH /internal/couriers/{id}`,
  `GET /internal/couriers/locations`, `GET /internal/shipments?status=`, `POST /internal/shipments/{id}/release`.
- `GET /internal/stats/summary?period=today|7d|30d` (O).

Swagger (`/docs`) is served only when `ENV=development`.

## 6. Domain rules worth knowing before changing anything

**Lifecycle.** `Shipment` and `Order` move together:
`processing/paid` -claim-> `assigned/processing` -pickup-> `shipped/shipped` -deliver-> `delivered/delivered`;
release (only before pickup) goes back to `processing/paid`. The Stripe webhook creates the shipment.
`mark_order_paid` is one guarded `pending_payment -> paid` UPDATE that also takes stock (a variant going
negative sets `orders.stock_shortfall`); replays and late events, including for cancelled orders, change
nothing. **Cancel** (admin, only before pickup): order + shipment → `cancelled`, stock returned, commit,
then a full Stripe refund (`payments.refund_status` pending/succeeded/failed; `refund.*` webhooks finish it).

**Concurrency.** Every transition is a guarded `UPDATE … WHERE status=… [AND courier_id=…] RETURNING`.
Lock order everywhere: **courier row (`SELECT … FOR UPDATE`) → shipment → order → variants (by id) → location**. The owner's
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
empty = public OpenStreetMap, which is for light use only). Spec 3: `ADMIN_SESSION_SECRET` (required by
compose and outside `ENV=development`), `ADMIN_BOOTSTRAP_TELEGRAM_IDS` (owners created on startup),
`SHOP_TIMEZONE` (UTC), `LOW_STOCK_THRESHOLD` (5); backend-only `ADMIN_COOKIE_SECURE` (false for local
http), `MEDIA_ROOT` (`/data/media` in Docker, the `media` volume shared with nginx); frontend
`VITE_TELEGRAM_BOT_USERNAME` (baked from `TELEGRAM_BOT_USERNAME`).
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

Admin panel by hand: uvicorn with `ADMIN_BOOTSTRAP_TELEGRAM_IDS=500 ADMIN_SESSION_SECRET=x ADMIN_COOKIE_SECURE=false
MEDIA_ROOT=./media`, Vite with `VITE_DEV_MOCK_INIT_DATA` for ID 500 and `VITE_API_BASE_URL=http://127.0.0.1:8000`,
then open `http://127.0.0.1:5173/admin` (the mock initData signs you in; the widget is only for real domains).

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

**Next session starts here:** Spec 4 (stock reservation) is designed in
`docs/superpowers/specs/2026-09-24-stock-reservation-design.md`. The owner confirmed §2 (15-min hold;
on expiry cancel + return items to the cart; payment after expiry is always refunded) and approach A
(subtract `stock_qty` at checkout). §4–§9 are drafted but not yet reviewed with the owner. Next:
walk the owner through §4–§9, then write the implementation plan, then implement test-first.
The owner explicitly said not to implement yet.

Specs 1–3 are built. What remains besides Spec 4:

1. Try the real thing once: HTTPS tunnel (`ngrok`/`cloudflared`) → `python -m scripts.set_telegram_webhook https://<origin>`
   → a real courier account sharing Live Location from a phone. `--info` shows Telegram's `last_error_message`.
   For the admin panel in a browser: BotFather `/setdomain` to the tunnel's domain, then sign in at `/admin`.
2. Stripe: subscribe the webhook endpoint to `refund.created|updated|failed` and run a test-mode refund.
3. Before real traffic: set `MAP_TILE_URL`/`MAP_ATTRIBUTION` for a proper tile provider; strong `INTERNAL_API_TOKEN`,
   `ADMIN_SESSION_SECRET` and `POSTGRES_PASSWORD`; serve over HTTPS; back up the `media` volume with the database.
4. Push: there is no remote yet. Decide where the repository lives before CI can run.
5. Not asked for, but likely next: deleting variants, an audit log beyond "who cancelled", charts in the summary.

## 11. Assumptions the product owner has not explicitly confirmed

Single currency (EUR), flat-rate shipping (€4.99, free over €50), price taken at checkout time; the owner
registers couriers manually; at most 3 active deliveries per courier; "Delivered" is a plain button (no PIN or
proof of delivery); OpenStreetMap tiles via Leaflet. Spec 3: summary in UTC until `SHOP_TIMEZONE` is set,
low-stock threshold 5, refunds always in full, browser sessions last 12 h.

**Out of scope by design (Spec 2 §14):** dispatcher UI, Telegram notifications to customers, proof of delivery,
failed deliveries/returns, routes/ETA/geocoding, courier shifts, earnings, location history, multiple warehouses.
