# Telegram Mini App Storefront

An e-commerce storefront that runs as a Telegram Mini App: catalog, cart, checkout with Stripe,
and order tracking. It launches with a cosmetics catalog but is built to take other niches
without code changes — products, categories and their attributes are all data.

This is built in three specs, designs in [`docs/superpowers/specs/`](docs/superpowers/specs/):

1. **Storefront** (done) — catalog, cart, Stripe checkout, orders.
   [Design](docs/superpowers/specs/2026-09-22-telegram-miniapp-storefront-design.md)
2. **Own courier delivery with live tracking** (done) — couriers claim paid orders from a pool,
   share a Telegram Live Location, and the customer follows them on a map.
   [Design](docs/superpowers/specs/2026-09-24-courier-delivery-design.md)
3. **Admin panel** (done) — catalog, orders with cancel and refund, couriers, a summary and
   admin accounts with roles, inside the Mini App and in a desktop browser.
   [Design](docs/superpowers/specs/2026-09-24-admin-panel-design.md)

| | |
|---|---|
| Backend | FastAPI (async), SQLAlchemy 2.0, PostgreSQL 16, Alembic |
| Frontend | React 19 + TypeScript + Vite, react-query, react-i18next (en / ru / uz) |
| Payments | Stripe Payment Element inside the Mini App, confirmed by webhook |
| Delivery | Own couriers, GPS from Telegram Live Location, Leaflet + OpenStreetMap maps |
| Auth | Telegram `initData`, verified server-side; admins in a browser sign in with the Telegram Login Widget |

## Run everything with Docker

A step-by-step launch guide in Russian, written for teaching (bot, `.env`, HTTPS tunnel, admin
sign-in, Stripe payments and refunds, troubleshooting): [`docs/LAUNCH_GUIDE_RU.md`](docs/LAUNCH_GUIDE_RU.md).

Requires Docker with Compose.

```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN (from @BotFather), INTERNAL_API_TOKEN and ADMIN_SESSION_SECRET
# (long random strings), and your own Telegram ID in ADMIN_BOOTSTRAP_TELEGRAM_IDS.
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

Use the admin panel (see [Admin panel](#admin-panel)), load a small demo catalog:

```bash
docker compose exec api python -m scripts.seed_demo_data
```

or script it against the token-protected internal API (send your `INTERNAL_API_TOKEN`
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

## Couriers & tracking

Couriers use the same Mini App: once a Telegram account is registered as a courier, a truck icon
appears in the header. They take paid orders from a shared pool, mark them picked up and
delivered, and share a **Live Location** in the bot chat. Customers see the courier's name on
their order and, while it is out for delivery, the courier on a map.

**1. Register a courier** (in the admin panel under Couriers, or with the internal API). `name` is
shown to customers, so enter a first name only:

```bash
curl "${H[@]}" -d '{"telegram_id":123456789,"name":"Ali","phone":"+998901112233"}' $API/internal/couriers
curl "${H[@]}" -X PATCH -d '{"is_active":false}' $API/internal/couriers/1   # stop a courier working
curl "${H[@]}" $API/internal/couriers
```

A courier's Telegram ID is what `@userinfobot` (or the `id` in their `initData`) reports. A
deactivated courier loses access immediately and their stored position is deleted.

**2. Let the bot receive locations.** Mini Apps cannot read GPS in the background, so the
courier shares a Live Location with the bot and Telegram delivers each update to a webhook:

```bash
# .env: TELEGRAM_WEBHOOK_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
#       TELEGRAM_BOT_USERNAME=your_bot
docker compose up -d --build
docker compose exec api python -m scripts.set_telegram_webhook https://<your-public-origin>
docker compose exec api python -m scripts.set_telegram_webhook --info    # check last_error_message
```

The public origin must be HTTPS (locally, use `ngrok`/`cloudflared`). A Telegram bot can have
**one** update consumer: the webhook and `getUpdates` polling are mutually exclusive, so do not
run another process that polls this bot. With `TELEGRAM_WEBHOOK_SECRET` empty the endpoint is
off and answers 404. Telegram only sends the secret back in the
`X-Telegram-Bot-Api-Secret-Token` header, and requests without it are rejected with 403.

**3. The courier's day.** Open the truck icon → **Available** → *Take this order*. The order moves
to **My deliveries** with the full address, phone, notes and a maps link. Under **My deliveries**
a panel explains sharing the location: in the bot chat, paperclip → *Location* → *Share Live
Location* → the longest duration. *Picked up* starts the customer-visible tracking; *Delivered*
finishes it. *Give back* returns an order to the pool until it has been picked up.

**4. The customer's view.** At checkout the customer may tap the map (or "Use my location") to drop
a delivery pin; it is optional. The order page shows a timeline (payment received → courier
assigned → out for delivery → delivered) and polls every 5 s while the courier is on the way.
A position older than `LOCATION_STALE_SECONDS` is drawn faded with "updated N min ago" — Telegram
only sends an update when the courier moves, so a courier standing still looks stale.

**Stuck orders.** If a courier disappears with an order, take it off them in the admin panel
(Couriers → Deliveries), or with the internal API:

```bash
curl "${H[@]}" "$API/internal/shipments?status=assigned&status=shipped"   # who holds what
curl "${H[@]}" -X POST $API/internal/shipments/7/release                    # back into the pool
```

**Trying it without a phone.** Seed a courier and a waiting order, then post a location to the
webhook yourself (this is exactly what Telegram sends):

```bash
docker compose exec api python -m scripts.seed_courier_demo --courier 222 --customer 111 --lat 52.52 --lng 13.405
curl -X POST $API/webhooks/telegram -H "X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET"   -H "content-type: application/json"   -d '{"update_id":1,"message":{"message_id":1,"date":1,"from":{"id":222,"is_bot":false,"first_name":"Ali"},"chat":{"id":222,"type":"private"},"location":{"latitude":52.51,"longitude":13.40,"live_period":3600}}}'
```

Positions are only stored for a courier who currently holds a delivery, only the latest one is
kept (no history), and it is deleted when their last delivery ends.

**Maps.** Tiles come from OpenStreetMap by default. Its public server is for light use only —
before real traffic, set `MAP_TILE_URL` (and `MAP_ATTRIBUTION` as your provider requires) in
`.env` and rebuild the web image. Leaflet is loaded lazily, so it does not add to the storefront's
first load. Do not send a `Referrer-Policy: no-referrer` header: OSM's tile servers reject
requests without a Referer.

**Privacy.** Customers see the courier's first name and position only — never a phone number or
Telegram ID. A customer with an order out for delivery can see where the courier is until *that*
order is delivered, including while the courier serves other customers, so keep `name` to a
first name and tell couriers their live location is shared this way.

## Admin panel

The panel lives at `/admin` of the same app. Admins who open the Mini App see a gear icon in the
top bar; in a desktop browser, go to `https://<your domain>/admin` and sign in with Telegram.

**First owner.** Put your Telegram ID (ask @userinfobot) in `ADMIN_BOOTSTRAP_TELEGRAM_IDS` and
restart the API: it creates an owner account for every listed ID that has none. It never changes
existing accounts, so removing an ID later demotes nobody. Everyone else is added from the panel.

**Roles.**

| | Owner | Catalog manager | Dispatcher |
|---|:-:|:-:|:-:|
| Summary (revenue, low stock, top products) | ✓ | | |
| Catalog: products, variants, photos, translations, categories, attributes | ✓ | ✓ | |
| Orders: list, detail, cancel with refund | ✓ | | ✓ |
| Couriers, active deliveries, live map | ✓ | | ✓ |
| Admins | ✓ | | |

The API enforces this on every request, and re-reads the admin's role each time, so a
deactivation or role change applies at once. There is always at least one active owner.

**Browser sign-in** uses the [Telegram Login Widget](https://core.telegram.org/widgets/login):

1. In @BotFather, `/setdomain` for your bot to the panel's domain (HTTPS).
2. Set `TELEGRAM_BOT_USERNAME` (the widget is built from it) and `ADMIN_SESSION_SECRET`.
3. Sign-in sets a 12-hour `HttpOnly`, `SameSite=Strict` cookie. Local development over plain
   http also needs `ADMIN_COOKIE_SECURE=false` in `backend/.env`.

**Cancelling an order** is possible until the courier has picked it up. The order and its
delivery become *cancelled*, the stock goes back, and the customer is refunded in full through
Stripe. Add the `refund.created`, `refund.updated` and `refund.failed` events to your Stripe
webhook endpoint so the panel shows the refund's final state; a refund Stripe refused can be
retried from the order.

**Stock** is taken off each variant when a payment succeeds. Checkout checks stock but does not
reserve it, so two customers can pay for the last unit: the order is then flagged *out of stock*
in the panel for the owner to resolve (typically cancel and refund).

**Photos** uploaded in the panel (JPEG, PNG or WebP, up to 10 MB) are stripped of metadata,
including the GPS position phones embed, shrunk to 1600 px and stored as WebP in the `media`
volume, which nginx serves under `/media/`. Back that volume up with the database.

**Summary** days are counted in `SHOP_TIMEZONE` (default UTC; e.g. `Asia/Tashkent`).

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

For the admin panel locally, also set `ADMIN_BOOTSTRAP_TELEGRAM_IDS`, `ADMIN_COOKIE_SECURE=false`
and `MEDIA_ROOT=./media` in `backend/.env`. A mock `initData` (below) for a bootstrapped ID opens
the panel at <http://localhost:5173/admin> without the widget; the dev server proxies `/media/`
to the API.

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
  services/        business logic (cart, checkout, orders, catalog, Stripe, dispatch, tracking)
  models/          SQLAlchemy models        alembic/   migrations
  core/            initData verification, i18n, money, shipping pricing, errors
frontend/src/
  features/        catalog, cart, checkout, orders, courier, admin — each with api / hooks / components / screens
  shared/          Telegram SDK wrapper, API client, i18n, maps (Leaflet), UI kit, design tokens
```

## Production notes

- Serve over HTTPS (Telegram requires it) and keep `.env` out of version control.
- Set a strong `INTERNAL_API_TOKEN`, `ADMIN_SESSION_SECRET` and `POSTGRES_PASSWORD`; the compose
  file refuses to start without the first two. The database and API are published on `127.0.0.1` only.
- Prices and stock are read from the server at checkout — the browser is never trusted for amounts.
- Single currency (EUR) and flat-rate shipping with a free-over threshold
  (`SHIPPING_FLAT_RATE`, `FREE_SHIPPING_THRESHOLD`) for now.
