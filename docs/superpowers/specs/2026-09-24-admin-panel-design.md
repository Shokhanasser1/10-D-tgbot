# Admin Panel (Spec 3 of 3)

Status: Approved — implemented (see §14 for where the build refined the design)
Date: 2026-09-24
Builds on: [Spec 1 — Storefront](2026-09-22-telegram-miniapp-storefront-design.md),
[Spec 2 — Courier delivery](2026-09-24-courier-delivery-design.md) (both complete)

## 1. Purpose & Scope

Give the business a UI to run the shop: catalog, orders, couriers and deliveries, a summary, and
the admins themselves. Until now all of this was done with `curl` against `/internal/*` and a
static token.

It also closes two gaps found while designing this:

- **Stock is never decremented.** Checkout only checks `stock_qty >= qty`; nothing reduces it
  after payment, so overselling is possible and a cancellation has nothing to return.
- **Payment confirmation is not a guarded transition.** `mark_order_paid` reads then writes, and
  `cancelled` is not in `_PAST_PAYMENT`, so a redelivered `payment_intent.succeeded` would move a
  cancelled order back to `paid` (and, once stock is decremented, could decrement twice).

Out of scope: see §12.

## 2. Decisions

Confirmed with the product owner:

| Topic | Decision |
|---|---|
| Where | Both inside the Telegram Mini App and in a desktop browser, from one codebase. |
| Shape | An `/admin/*` section of the existing frontend, lazy-loaded. `/internal/*` stays the only admin API (no parallel API). |
| Who | Several admins with **three roles**: owner, catalog manager, dispatcher. |
| Sections | Summary, catalog, orders, couriers & deliveries (+ admins, owner only). |
| Photos | Uploaded as files to the server, stored on a docker volume, served by nginx. |
| Orders | View, plus **cancel with a full Stripe refund** before the courier picks the order up. |
| Stock | Decremented when payment succeeds; returned on cancellation. |

Assumptions — not confirmed, flagged for review:

- Summary days are counted in `SHOP_TIMEZONE`, default `UTC` (the owner has not chosen a zone).
- Low-stock threshold 5 (`LOW_STOCK_THRESHOLD`).
- Browser session lifetime 12 h; Login Widget `auth_date` accepted up to 24 h old.
- Refunds are always full; no partial refunds.

## 3. Roles & Permissions

| Area | owner | catalog_manager | dispatcher |
|---|---|---|---|
| Summary (revenue) | yes | — | — |
| Catalog, photos, translations | yes | yes | — |
| Orders: view | yes | — | yes |
| Orders: cancel + refund, retry refund | yes | — | yes |
| Couriers, deliveries, force release, courier map | yes | — | yes |
| Admins | yes | — | — |

The server enforces this on every endpoint. The frontend only uses the role to build the menu.

## 4. Data Model

New table `admins`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `telegram_id` | bigint, unique | |
| `role` | varchar | `owner` \| `catalog_manager` \| `dispatcher` (non-native enum, like the rest) |
| `display_name` | varchar(100) | |
| `is_active` | bool, default true | |
| `created_at` | timestamptz | |
| `created_by` | bigint, nullable | telegram_id of the owner who added them; null for bootstrap |

`orders` gains: `stock_shortfall` bool default false, `cancelled_at` timestamptz null,
`cancelled_by` bigint null (admin telegram_id; null when cancelled via `X-Internal-Token`),
`cancel_reason` varchar(500) null.

`payments` gains: `refund_status` varchar null (`pending` \| `succeeded` \| `failed`),
`stripe_refund_id` varchar null.

`ShipmentStatus` gains `cancelled` (VARCHAR storage, no type migration).

`product_images` gains `storage_key` varchar null — set for uploaded files, null for
URL-only images, so deletion knows whether there is a file to remove.

One Alembic revision for all of the above.

**Bootstrap.** `ADMIN_BOOTSTRAP_TELEGRAM_IDS` (comma-separated) is applied at startup: each ID with
no `admins` row gets one with role `owner`. It never changes existing rows, so removing an ID from
`.env` does not demote anyone and re-adding it does not re-activate a deactivated admin.

**Invariant.** There is always at least one active owner. Deactivating or demoting the last active
owner is 409 `last_owner`. An admin cannot deactivate themselves (409 `self_deactivation`).

## 5. Authentication

Every admin request resolves to one `AdminPrincipal(telegram_id: int | None, role)`. Three ways in:

1. **Mini App:** `Authorization: tma <initData>`, verified exactly as for customers/couriers, plus
   an active `admins` row for that telegram_id. Unknown or inactive → 403.
2. **Browser:** Telegram Login Widget.
   - `POST /internal/auth/telegram` receives the widget payload. Verify `hash` =
     HMAC-SHA256(data-check-string, key = SHA256(bot_token)) with a constant-time compare, and
     `auth_date` no older than 24 h. Unknown or inactive admin → 403.
   - On success, set cookie `admin_session`: a value signed with `ADMIN_SESSION_SECRET`
     (itsdangerous `TimestampSigner`, new dependency) carrying the telegram_id; `HttpOnly`, `Secure`,
     `SameSite=Strict`, `Path=/api/internal`, max age 12 h. No server-side session table.
   - `POST /internal/auth/logout` clears it.
   - Rate limit on `/internal/auth/telegram`: 10 requests/min per IP, in-process.
   - Mutating requests authenticated by cookie must carry `X-Requested-With: admin`; this plus
     `SameSite=Strict` and same-origin nginx is the CSRF defence. Tokens and initData are exempt
     (they are not ambient credentials).
   - Requires the bot's domain set via BotFather `/setdomain` (documented in README).
3. **Scripts:** `X-Internal-Token` as today, treated as `owner` with `telegram_id=None`.

The `admins` row (`is_active`, `role`) is re-read on every request, so deactivation and role
changes apply immediately. `require_internal_token` is replaced by `require_admin(*roles)`.
`GET /internal/me` returns `{telegram_id, display_name, role}`.

Logs record telegram_id and action, never initData, widget payloads or cookies.

## 6. API

All under `/internal`, all behind `require_admin`. Existing endpoints keep their shape; only the
auth dependency changes. Role column uses O = owner, C = catalog_manager, D = dispatcher.

### 6.1 Catalog reads (O, C) — existing writes also become O, C

- `GET /categories`, `GET /attributes` — flat lists including inactive.
- `GET /products?status=&category_id=&q=&limit=50&offset=0` → `{items, total}`; `q` matches
  name (any translation) and variant SKU, case-insensitive. Item: id, name (in `Accept-Language`
  falling back to default), status, category, first image, min price, total stock.
- `GET /products/{id}` — everything the editor needs: product fields, variants, attribute values,
  images, translations for all languages.
- No deletion; products are archived via the existing `PATCH`.

### 6.2 Images (O, C)

- `POST /products/{id}/images` additionally accepts `multipart/form-data` (`file`, optional
  `variant_id`, `position`). The JSON URL form stays.
- Pillow is a new backend dependency.
- Validation: at most 10 MB (reject before reading further); Pillow must open and `verify()` it;
  format in {JPEG, PNG, WEBP}; `Image.MAX_IMAGE_PIXELS` 40 M. The client's filename and
  Content-Type are ignored.
- Processing: apply EXIF orientation, then drop all metadata; resize to 1600 px on the long side
  (never upscale); save WebP quality 85 as `MEDIA_ROOT/products/<uuid4>.webp`; `url` =
  `/media/products/<uuid4>.webp`, `storage_key` = relative path. Done in a thread
  (`asyncio.to_thread`).
- `PATCH /images/{id}` — `position`, `variant_id`.
- `DELETE /images/{id}` — deletes the row; if `storage_key` is set, deletes the file after commit
  (a missing file is not an error).
- Infrastructure: `media` docker volume mounted into `api` (read-write) and `web` (read-only);
  nginx `location /media/` serves files with `X-Content-Type-Options: nosniff`, only `.webp`.

### 6.3 Orders (O, D)

- `GET /orders?status=&q=&from=&to=&shortfall=&limit=50&offset=0` → `{items, total}`; `status`
  repeatable; `q` is an order id or a telegram_id; dates are inclusive days in `SHOP_TIMEZONE`.
  Item: id, status, total, placed_at, customer name, `stock_shortfall`, `refund_status`.
- `GET /orders/{id}` — items, delivery address incl. phone/notes/pin, payment (status, refund
  status), shipment (status, courier first name + id), cancellation fields.
- `POST /orders/{id}/cancel {reason: str 1–500}` — see §7.2.
- `POST /orders/{id}/refund` — retry a refund whose `refund_status` is `failed`; otherwise 409
  `invalid_state`.

### 6.4 Couriers & deliveries (O, D)

Existing `POST/GET/PATCH /couriers`, `GET /shipments`, `POST /shipments/{id}/release`, plus:

- `GET /couriers/locations` — for each courier holding an active delivery: id, first name,
  latitude, longitude, updated_at, `is_stale`, active delivery count. Same data-minimisation rules
  as Spec 2: only latest positions, only couriers with an active delivery.

### 6.5 Summary (O)

`GET /stats/summary?period=today|7d|30d`:

- `revenue`, `orders_count`, `average_order` — orders with `placed_at` in the period whose payment
  succeeded, excluding orders with `refund_status` `pending|succeeded`.
- `status_counts` — current count per order status (not period-bound).
- `low_stock` — variants of non-archived products with `stock_qty <= LOW_STOCK_THRESHOLD`,
  lowest first, max 20.
- `top_products` — top 5 by quantity over the same orders as revenue.

"today" = since local midnight in `SHOP_TIMEZONE`; `7d`/`30d` include today.

### 6.6 Admins (O)

- `GET /admins`, `POST /admins {telegram_id, role, display_name}` (409 if exists),
  `PATCH /admins/{id} {role?, display_name?, is_active?}` with the §4 invariant.

## 7. Domain Changes

### 7.1 Payment confirmation and stock

`mark_order_paid` becomes a guarded transition:
`UPDATE orders SET status='paid' WHERE id=:id AND status='pending_payment' RETURNING id`.
If no row is returned the event is a duplicate or late (including for cancelled orders) and is
ignored. Otherwise, in the same transaction: payment → `succeeded`, shipment created, and for each
order item, in variant-id order, `UPDATE variants SET stock_qty = stock_qty - :qty WHERE id=:vid
RETURNING stock_qty`. Any negative result sets `orders.stock_shortfall = true`. The payment is
never rejected for stock: the customer has already paid, and the owner decides (typically cancel +
refund).

### 7.2 Cancellation

Allowed when order is `paid|processing` and the shipment is `processing|assigned`. Otherwise 409
`invalid_state` (in particular once the courier has picked up: `shipped`).

Transaction, in the Spec 2 lock order **courier → shipment → order → variants**:

1. Read the shipment's `courier_id` unlocked; if set, `SELECT … FOR UPDATE` the courier.
2. Guarded `UPDATE shipments SET status='cancelled', courier_id=NULL WHERE id=… AND status IN
   ('processing','assigned') [AND courier_id=:seen] RETURNING`. No row → rollback, 409
   `invalid_state` (a courier picked it up or claimed it concurrently).
3. Guarded `UPDATE orders SET status='cancelled', cancelled_at, cancelled_by, cancel_reason WHERE
   id=… AND status IN ('paid','processing') RETURNING`.
4. Return stock: `stock_qty = stock_qty + qty` per item, variant-id order.
5. If the courier now holds no active delivery, purge their location (reuse `courier_state`).
6. Set `payments.refund_status='pending'`; commit.

### 7.3 Refund

After the commit: `stripe.Refund.create_async(payment_intent=…, idempotency_key=
f"refund-order-{order_id}")`. Success → store `stripe_refund_id` (status stays `pending` unless
Stripe already reports `succeeded`). Stripe error → `refund_status='failed'`, logged; the cancel
request still returns 200 with that status so the UI shows "Retry refund". Retrying reuses the same
idempotency key, so Stripe never refunds twice.

The Stripe webhook additionally handles `refund.updated` / `refund.failed`: look up the payment by
`payment_intent`, set `refund_status` to `succeeded` or `failed`. Unknown intents are ignored.

Committing the cancellation before calling Stripe means money is never refunded for an order the
database still shows as out for delivery.

## 8. Frontend

`features/admin`, routes under `/admin/*`, loaded with `React.lazy` so shoppers never download it.
Reuses the ui kit, api client, i18n (en/ru/uz, parity test covers admin keys), map components.

**Auth.** Inside Telegram (initData present) the api client sends `tma` as today. Otherwise the
client uses the cookie (`credentials: 'same-origin'`, `X-Requested-With: admin` on mutations);
on 401 it shows the Login Widget screen (`VITE_TELEGRAM_BOT_USERNAME`). 403 from `/me` → "No
access" screen. The menu is built from `/me.role`.

**Layout.** Phone: bottom tabs. Desktop (≥ 900 px): left sidebar, wider tables. Same light
minimalist style as the storefront.

**Screens.**

- **Summary** (O): period switch; revenue / orders / average cards; status counts linking to the
  filtered order list; low stock linking to the product; top 5. No charts.
- **Catalog** (O, C): product list with search and status/category filters (photo, name, price,
  stock); product editor in blocks — basics (category, status), translations (EN/RU/UZ tabs),
  variants (inline price/stock/SKU rows), attributes, photos (upload, drag to reorder, delete);
  categories and attributes as simple lists with create/edit forms.
- **Orders** (O, D): list with status/date filters, id search, "Out of stock" and "Refund failed"
  badges, 10 s polling; order detail with items, customer, address, pin map, courier, status
  history, "Cancel and refund" (confirm dialog with required reason; disabled with explanation
  once picked up), "Retry refund".
- **Couriers** (O, D): courier list (add by telegram_id, deactivate, active delivery count);
  active deliveries with "Remove from courier" (existing force release); map of courier positions, stale ones grey, 10 s
  polling.
- **Admins** (O): list, add by telegram_id with role, change role, deactivate.

Destructive actions (cancel, force release, deactivate) always confirm. Forms validate with the
server's rules; error codes map to readable messages (e.g. `invalid_state` on cancel → "The courier
has already picked this order up").

## 9. Errors

Existing global mapping: 401 not authenticated, 403 wrong role/not an admin, 404 not found, 409
conflict with `code` (`invalid_state`, `last_owner`, `self_deactivation`, `already_exists`), 400
bad input (including rejected images), 413 image too large, 429 login rate limit.

## 10. Configuration

New variables: `ADMIN_BOOTSTRAP_TELEGRAM_IDS`, `ADMIN_SESSION_SECRET` (required when the web
image is built for browsers; startup fails if empty and `ENV != development`), `MEDIA_ROOT`
(default `/data/media`), `SHOP_TIMEZONE` (default `UTC`), `LOW_STOCK_THRESHOLD` (5),
`VITE_TELEGRAM_BOT_USERNAME` (reuses `TELEGRAM_BOT_USERNAME` at build time). Added to
`.env.example`, compose and README.

## 11. Testing

Backend (pytest):

- Auth: widget hash valid/forged/expired; cookie valid/tampered/expired; deactivated admin loses
  access on the next request; `X-Requested-With` required for cookie mutations; rate limit.
- Role × endpoint matrix (parametrised).
- Bootstrap idempotent; last-owner and self-deactivation guards.
- Stock: decrement on payment, duplicate webhook, late webhook after cancel, negative → shortfall.
- Cancellation in every order/shipment state; race with a concurrent pickup and claim using the
  independent-session fixtures from `test_courier_concurrency.py`; courier location purge.
- Refund: Stripe mocked success/failure/retry; idempotency key; `refund.*` webhooks.
- Images: oversize, non-image, disguised extension, decompression bomb, EXIF removed, resize,
  delete removes the file.
- Summary: day boundaries in a non-UTC zone, refunds excluded.

Frontend (Vitest + MSW): menu per role, login/no-access screens, product editor and translations,
image upload, order cancel flow and error mapping, couriers map, admins. Coverage not below the
current level.

## 12. Non-Goals

Charts · full audit log (only cancellation authorship is recorded) · partial refunds · editing
order contents · Telegram notifications · bulk product import · per-admin custom permissions ·
cancelling after pickup (failed deliveries/returns remain out of scope as in Spec 2).

## 13. Build Order

Each step is one commit with tests green.

1. `admins` table, roles, `require_admin`, Mini App + browser login, `/me`, migration.
2. Catalog read endpoints.
3. Image upload, `/media/` volume and nginx.
4. Guarded payment confirmation + stock decrement.
5. Orders list/detail, cancellation, refund, refund webhooks.
6. Summary, admins management, courier locations endpoint.
7. Frontend: `/admin` shell, auth screens, role menu.
8. Frontend: catalog.
9. Frontend: orders, couriers, map.
10. Frontend: summary, admins.
11. README, `.env.example`, implementation notes in this spec.

## 14. Implementation notes

Where the build refined the design above:

- **Sessions** are signed with a small HMAC helper (`core/admin_session.py`) instead of
  itsdangerous: one dependency fewer for three lines of code. The cookie's `Path` is `/`, not
  `/api/internal`: in development the API is on another origin without the `/api` prefix.
  `ADMIN_COOKIE_SECURE` (default true) exists so local http development can sign in.
- `ADMIN_SESSION_SECRET` is enforced by `Settings` (startup fails outside `ENV=development`) and by
  compose (`:?`). Browser sign-in answers 503 if the secret is empty in development.
- **401 vs 403** on `/internal/*`: no credentials is now 401 (it was 403); a wrong token or a
  non-admin stays 403. Existing tests were updated accordingly.
- **Admin management** endpoints shipped in phase 1 with the identity work, not phase 6.
- **Payment confirmation** only moves `pending_payment -> paid`; a late event for a cancelled
  order is ignored. Stock moves in `stock_service`, variant rows in ascending id order.
- **Cancellation** retries its read-lock-update sequence up to three times when a courier claims
  or releases the order in between, so the owner does not get a spurious 409 for an order that is
  still cancellable. Shipment `courier_id` is cleared on cancel.
- **Refund retries** use a new idempotency key (`refund-order-<id>-retry-<uuid>`): Stripe replays a
  stored error for a reused key for 24 h, which would make "retry" useless. A double refund is still
  impossible because Stripe caps refunds at the charged amount. The refund carries
  `metadata.order_id`; `refund.*` webhooks match on `payment_intent` and never downgrade a
  `succeeded` refund.
- **Couriers**: `GET /internal/couriers` gained `active_deliveries`. The deliveries tab offers the
  existing force release for picked-up orders too (the escape hatch for a vanished courier), with a
  stronger warning.
- **Photos** are reordered with earlier/later buttons rather than drag and drop: they work the same
  with touch, mouse and keyboard. nginx needed `client_max_body_size 11m` on `/api/` (its default
  of 1 MB would have rejected most phone photos). Dev: Vite proxies `/media` to the API and the API
  serves `MEDIA_ROOT` itself when `ENV=development`.
- **Entry point**: inside Telegram there is no address bar, so the storefront's top bar shows a
  gear icon to admins (`features/admin/entry.ts`, outside the lazily loaded admin chunk).
- The four frontend phases landed as one commit.
- **Verified** against a real database and API in a browser (summary, cancel with a failing Stripe
  key, photo upload, phone layout, courier map) and with the production Docker images (upload
  through nginx, `/media/` served as `image/webp`). **Not verified:** the Telegram Login Widget
  on a real domain, and real Stripe refunds.

