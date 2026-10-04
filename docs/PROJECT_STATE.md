# Project state (handoff)

Snapshot: 2026-10-04 (after Spec 7, the free production deploy (§1b), Specs 8 to 11: the marketplace), branch `main`, pushed to the **public** repository https://github.com/Shokhanasser1/10-D-tgbot.
Sections 3–9 were last fully revised on 2026-09-29 (Spec 6); Spec 7 changes are summarised where they matter.
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
| 4 Stock reservation | reserve `stock_qty` at checkout, 15-min hold, expiry sweeper, cart restore, refund of late payments | **done**, committed (`2100f11`) |
| 5 Telegram notifications | outbox table + background sender; customers, couriers, owners/dispatchers | **done**, committed (`0dd7657`) |
| 6 Payments in Uzbekistan | Click/Payme via Telegram Payments, cash on delivery, UZS; Stripe kept as an option | **done**, committed (`b6813c5`) |
| 7 Admin roles + password sign-in | six roles (owner, manager, catalog_manager, dispatcher, accountant, viewer) mapped to permissions in `app/core/permissions.py`; login + password (scrypt, lockout after 5 tries), password re-entry within 15 min for money and admin management | **done**, committed (`123290e`, `daa805e`) |
| 8 Role-based launch | opening the bot sends admins to `/admin`, couriers to `/courier`, everyone else to the shop; Shop/Courier/Admin switch buttons; frontend only (`app/launch.ts`, `LaunchGate`, `CourierShell`). Stage A of the marketplace roadmap (B sellers, C multi-seller orders, D money) in the spec | **done**, committed (`c3ea1db`..`85c1220`) |
| 9 Sellers and their products (marketplace stage B) | `sellers` table; every product has a seller (migration gives old products a "Main shop"); seller = admin role confined to its own products by `app/services/seller_scope.py` (another seller's rows answer 404); new permissions `taxonomy.edit`, `sellers.manage`; `/internal/sellers`; storefront shows and filters by seller; one seller per cart (`cart_other_seller`, `replace_cart`) | **done**, committed (`5ed4a4e`..`ab7390c`), **not deployed** |
| 10 Orders per seller (marketplace stage C) | `orders.seller_id` (from the cart at checkout); `shipments.ready_at` (null = the seller is preparing): the pool and the claim only take ready shipments; `POST /internal/orders/{id}/ready` (`orders.prepare`: owner, manager, dispatcher, the order's seller); payment notifies the seller, ready notifies the couriers with the pickup; `/internal/seller/orders` without customer data; courier pool/deliveries carry `pickup` | **done**, committed (`9d44ff4`..`b586522`), **not deployed** |
| 11 Sellers' money (marketplace stage D) | `sellers.commission_percent` (default 10) copied to `orders.commission_percent` at checkout; `seller_earnings` written once on delivery (`earnings_service`); `seller_payouts` recorded by hand (`payouts.manage`: owner, accountant, 🔒), never above the balance (`exceeds_balance`); ledgers for the platform (`/internal/sellers/{id}/ledger`) and the seller (`/internal/seller/earnings`) | **done**, committed (`fb42219`..`9b2ce32`), **not deployed** |
| Free hosting | Mini App on Cloudflare Pages, backend on JustRunMy.App, DB on Supabase, photos in R2 | **live** since 2026-10-04 (`fd8c75b`, `3ebf23b`, fixes after), see §1b |

Designs are in `docs/superpowers/specs/` (Spec 7: `2026-09-29-admin-roles-and-password-login-design.md`; Spec 8: `2026-10-04-role-based-launch-design.md`, Spec 9: `2026-10-04-sellers-and-products-design.md`, Spec 10: `2026-10-04-seller-orders-design.md`, Spec 11: `2026-10-04-seller-money-design.md`, plans in `docs/superpowers/plans/`). Spec 2's §16, Spec 3's §14 and Spec 4's §12, Spec 5's §11 and Spec 6's §13 "Implementation notes" list
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
- Docker stack (`db`, `api`, `web`) is **stopped** (since 2026-10-01); production now runs on free hosting (§1b).
  When started, it serves :8080 (api on 127.0.0.1:8000); dev mode needs `docker compose stop api web` first.
- Gitignored deploy files in the root: `.env.justrunmy` (the backend's production variables; its `DATABASE_URL`
  still has a password placeholder, the real one lives only in the JustRunMy panel) and `.env.r2` (R2 keys).
- The owner pasted the real bot token into chat; they were advised to `/revoke` it in @BotFather and update
  root `.env`. Not yet confirmed done.
- **Still manual (owner's accounts needed):** https tunnel + BotFather Menu Button, `/setdomain` for browser
  admin sign-in, Stripe test keys + webhook with `payment_intent.*` and `refund.created|updated|failed`.

## 1b. Production on free hosting (live since 2026-10-04)

Owner-facing guide in Russian: `docs/DEPLOY_FREE_RU.md`.

- **Mini App**: Cloudflare Pages project `ecosmetics-shop`, https://ecosmetics-shop.pages.dev. Deploy with
  `npm --prefix frontend run deploy:pages` (wrangler is logged in on this machine). The Pages Function
  `frontend/functions/api/[[path]].ts` proxies `/api/*` to the `BACKEND_URL` Pages secret and **strips `/api`**
  (FastAPI serves from `/`; nginx does the same in compose); it only swaps the path on a copy of `BACKEND_URL`,
  so `/api//other.host` cannot reach another host (`proxy.test.ts`). `/media/*` is read from the R2 binding `MEDIA`.
- **Backend**: JustRunMy.App app 66718, https://ecosmetics-api.k.onjrnm.vip (container from `backend/`, port 8000,
  0.15 vCPU / 0.15 GB). Deployed by pushing `git subtree split --prefix backend` to the app's git remote (the push
  URL with credentials is on the panel's Git Push page, not stored locally). Env vars are set in the panel.
  Logs: panel → application → Diagnostics → Live container output (the owner cannot copy from it; ask for a screenshot).
- **Database**: Supabase project `otzhnhdivutcpyralbch` (Frankfurt), session pooler
  `aws-1-eu-central-1.pooler.supabase.com:5432`; migrations run on container start. Products and photos from the
  local machine were **not** migrated, so the production catalog may be empty.
- **Photos**: R2 bucket `ecosmetics-media` (`MEDIA_STORAGE=r2`).
- **Bot**: webhook is `https://ecosmetics-shop.pages.dev/api/webhooks/telegram`, so moving the backend only needs a
  new `BACKEND_URL` + `deploy:pages`.
- **Keeping it alive (owner)**: JustRunMy stops free apps unless **Reset timer** is pressed every ~36 h; the free tier
  **ends 2026-10-19** (then about $1/month, or move the backend, e.g. Render free + an external ping). Decide before then.
- **What took it down on 2026-10-04**, for diagnosis next time: (1) the timer expired → the host answers plain-text
  `404 page not found`; (2) `TELEGRAM_WEBHOOK_SECRET` pasted into the panel with a trailing `\n` → settings
  validation crash → 502; other secrets may still carry a silent `\n` (offered, not done: strip whitespace in
  `Settings`); (3) the Pages proxy forwarded `/api/...` unchanged → FastAPI 404 (fixed). A `530` on `/api/...`
  means `BACKEND_URL` points at a dead `trycloudflare` quick tunnel.
- **Production config gaps**: the panel has no `DEFAULT_CURRENCY`, `CASH_ON_DELIVERY_ENABLED` or
  `TELEGRAM_PAYMENT_PROVIDER_TOKEN`, so it runs the EUR defaults and checkout shows "Payments are not set up".
  Ask the owner before changing.
- **Waiting to deploy (Specs 8 to 11)**: the owner asked to finish the marketplace stages first and
  deploy them together. Spec 9 needs the backend redeployed too (its migration runs on container
  start). Production has no products, so the migration creates no "Main shop": add a seller under
  **Sellers** before creating products.
- Auto mode blocks Claude from writing secrets (`wrangler pages secret put`); the owner runs it with `!` in the prompt.

## 2. Stack

- **Backend** `backend/`: FastAPI (async), SQLAlchemy 2.0 async + asyncpg, Alembic, PostgreSQL 16,
  pydantic-settings, ruff (line length 100). Python 3.12 in Docker/CI, 3.14 locally.
- **Frontend** `frontend/`: React 19, TypeScript strict, Vite, react-router v7, react-query,
  react-i18next (en/ru/uz), CSS Modules, Leaflet 1.9 + react-leaflet 5, oxlint, prettier,
  Vitest + Testing Library + MSW (`onUnhandledRequest: 'error'`).
- **Runtime** `docker-compose.yml`: `db` (Postgres), `api`, `web` (nginx serving the SPA and proxying
  `/api/` to the API, so the browser is same-origin and needs no CORS).
- **Auth**: Telegram `initData`, verified server-side with HMAC (`Authorization: tma <initData>`).
  Customers and couriers have no passwords; admins also sign in with login + password (Spec 7). `/internal/*` (the admin API) accepts `X-Internal-Token` (scripts; acts as owner),
  initData of an active admin, or a signed `admin_session` cookie from the Telegram Login Widget.
- **CI** `.github/workflows/ci.yml`: backend `ruff check app tests scripts` + `pytest --cov`;
  frontend `npm run lint`, `npm run build` (runs `tsc -b`, which also type-checks tests), `npm test`.

## 3. Verified state

- Backend: **702 tests pass** (2026-10-04, after Spec 11, against the compose `db` container), ruff clean. Alembic head **`c2d3e4f5a6b7`** (seller money). Earlier: 504 tests passed locally and inside the production image. The suite also
  passes inside the production image (Python 3.12, SQLAlchemy 2.1, stripe 11), which differs from the
  local Python 3.14 / SQLAlchemy 2.0 / stripe 15 set-up.
- Frontend: **411 tests pass** (2026-10-04, after Spec 11; incl. the Pages proxy tests in `functions/`), lint/prettier/`tsc`/build clean (one pre-existing oxlint warning in
  `router.tsx`).
- Manually verified against a real API + database over HTTP (whole courier flow), and in a real
  browser (map tiles, markers, pin tap, courier claim flow, live marker update).
- Admin panel verified in a browser against the real API + DB (summary, cancel, photo upload, phone
  layout, courier map); production images built and run (upload through nginx, `/media/` served).
- Spec 4 verified in the rebuilt Docker stack: migration applied on startup, the sweeper expired an overdue
  order (stock back, items back in the cart), checkout without Stripe keys answers 502 `payment_unavailable`
  and keeps the cart.
- Spec 5 verified in Docker against the real Bot API: an expired order queued a message with a button, the
  sender posted it and Telegram's "chat not found" marked it `undeliverable` (test user, nobody messaged).
- Spec 6 verified in Docker: an invalid provider token makes the real Bot API answer PAYMENT_PROVIDER_INVALID,
  the API returns 502 and keeps the cart; a cash order goes straight to the pool and a cancel refunds nothing.
  Test notifications were deleted before re-enabling the sender. A real Click/Payme test payment is not done yet.
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
                  order_admin_service (list/detail/cancel/refund), stats_service,
                  reservation_service (expiry sweeper, Spec 4), bot_service (/start reply),
                  notification_templates/_service/_events/_sender (Spec 5 outbox)
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
(`X-Telegram-Bot-Api-Secret-Token`; empty `TELEGRAM_WEBHOOK_SECRET` means 404). The Telegram webhook
answers `/start` in a private chat by returning a `sendMessage` (greeting + web_app button to `WEBAPP_URL`)
as its response body; every other update gets `{"status": "ok"}`.

Checkout: 409 `code=insufficient_stock` when a line cannot be reserved (nothing written); 502
`code=payment_unavailable` for any Stripe error (global handler). The response includes `reserved_until`.
`GET /orders/{id}` also returns `reserved_until`, `cancel_reason`, `refund_status`.

Admin, `/internal/*` (roles O=owner, C=catalog_manager, D=dispatcher; the internal token counts as O).
Spec 7 replaced these three roles with six roles and per-route permissions: `app/core/permissions.py` is the
source of truth, and the role letters below show the Spec 6 state.
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

**Lifecycle.** `Shipment` and `Order` move together (since Spec 10 a `processing` shipment is only in
the pool, and claimable, once its seller set `ready_at`):
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

**Stock reservation (Spec 4).** Checkout subtracts `stock_qty` (guarded UPDATE per variant, ascending id)
and sets `orders.reserved_until = now + RESERVATION_TTL_MINUTES`, commits, *then* calls Stripe; a Stripe
failure cancels the order (`payment_setup_failed`) and restores stock and cart. A lifespan task
(`reservation_service.run_sweeper`, every `RESERVATION_SWEEP_SECONDS`) expires overdue unpaid orders:
cancel the PaymentIntent first (if Stripe says it succeeded/processing, leave the order alone), then a
guarded UPDATE to `cancelled`/`payment_expired`, stock back, payment `canceled`, items back to the active
cart (archived products skipped). `mark_order_paid` no longer takes stock for orders with `reserved_until`
(legacy orders with NULL keep the take-at-payment + `stock_shortfall` path); a payment for a cancelled
order with no refund yet is refunded in full (key `late-payment-<id>`).

**Notifications (Spec 5).** Services call `notification_events.<event>(db, ...)` inside their own transaction,
before `commit`, only on the branch where the guarded UPDATE matched; rows land in `notifications` with a unique
`dedupe_key`. `notification_sender.run_sender` (started by `app.main.background_tasks` when
`NOTIFICATION_SEND_SECONDS > 0` and a bot token is set) leases 25 due rows at a time, sends, and records
sent / undeliverable / failed / retry with backoff. Anything that changes order state should enqueue its event.

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
`SHOP_TIMEZONE` (UTC), `LOW_STOCK_THRESHOLD` (5); Spec 4: `RESERVATION_TTL_MINUTES` (15),
`RESERVATION_SWEEP_SECONDS` (60, 0 = off); `WEBAPP_URL` (public https address for the /start button and notification buttons);
Spec 5: `NOTIFICATION_SEND_SECONDS` (2, 0 = off); backend-only `ADMIN_COOKIE_SECURE` (false for local
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

Backend tests inside the production image (catches dependency drift; run from the repo root in Git Bash):

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps --user root --entrypoint sh   -v "$(pwd -W)/backend/tests:/app/tests" -e ENV=development   -e TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/storefront_test api   -c "pip install -q 'pytest>=8.3,<9' 'pytest-asyncio>=0.24,<1' 'faker>=30,<31' && python -m pytest -q"
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

**Next session starts here:** Specs 1–7 are built and the shop is live on free hosting (§1b). Nearest deadline:
**decide where the backend lives before 2026-10-19**, when JustRunMy's free tier ends. Then: put real products into the
production database, set the Uzbek payment config in the JustRunMy panel (below), and have the owner send `/start`
to the bot and walk through an order. What is left needs the owner's accounts and decisions rather than code.
The owner asked on 2026-09-29 to "finish to an MVP"; that was taken as approval of Spec 4 §4–§9.

Offered on 2026-10-04, not accepted yet: make `Settings` strip leading/trailing whitespace from env values, so a
pasted `\n` cannot break secrets silently (it also helps students who copy from Notepad).

**Owner's switch-over to the Uzbek set-up (not done by us, their `.env` and data):** set `DEFAULT_CURRENCY=UZS`,
`SHIPPING_FLAT_RATE=20000`, `FREE_SHIPPING_THRESHOLD=300000`, `CASH_ON_DELIVERY_ENABLED=true`, the Click or Payme
provider token from @BotFather, `WEBAPP_URL`; re-run `set_telegram_webhook` (it now asks for `pre_checkout_query`);
re-enter catalog prices in sums (the local demo DB still has EUR-era prices; `seed_demo_data` now seeds sums).
Without any payment method configured the checkout shows "Payments are not set up in this shop yet".

What remains:

1. Try the real thing once: HTTPS tunnel (`ngrok`/`cloudflared`) → `python -m scripts.set_telegram_webhook https://<origin>`
   (also sets the bot's menu button; put the same origin in `WEBAPP_URL` for the /start button)
   → a real courier account sharing Live Location from a phone. `--info` shows Telegram's `last_error_message`.
   For the admin panel in a browser: BotFather `/setdomain` to the tunnel's domain, then sign in at `/admin`.
2. Stripe: subscribe the webhook endpoint to `refund.created|updated|failed` and run a test-mode refund.
3. Before real traffic: set `MAP_TILE_URL`/`MAP_ATTRIBUTION` for a proper tile provider; strong `INTERNAL_API_TOKEN`,
   `ADMIN_SESSION_SECRET` and `POSTGRES_PASSWORD`; serve over HTTPS; back up the `media` volume with the database.
4. Students run the project **without Docker**: [`ZAPUSK_BEZ_DOCKER.md`](../ZAPUSK_BEZ_DOCKER.md) (native PostgreSQL,
   `scripts.create_databases`). Keep that path working: the demo seed and `backend/.env.example` defaults are part of it.
5. Not asked for, but likely next: a notification history block in the admin order page, deleting variants, an audit log beyond "who cancelled", charts in the summary.

## 11. Assumptions the product owner has not explicitly confirmed

Single currency (EUR), flat-rate shipping (€4.99, free over €50), price taken at checkout time; the owner
registers couriers manually; at most 3 active deliveries per courier; "Delivered" is a plain button (no PIN or
proof of delivery); OpenStreetMap tiles via Leaflet. Spec 3: summary in UTC until `SHOP_TIMEZONE` is set,
low-stock threshold 5, refunds always in full, browser sessions last 12 h.

**Out of scope by design (Spec 2 §14):** dispatcher UI, Telegram notifications to customers, proof of delivery,
failed deliveries/returns, routes/ETA/geocoding, courier shifts, earnings, location history, multiple warehouses.
