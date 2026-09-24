# Own Courier Delivery & Live Tracking (Spec 2 of 3)

Status: Draft — awaiting review
Date: 2026-09-24
Builds on: [Spec 1 — Storefront](2026-09-22-telegram-miniapp-storefront-design.md) (complete)

## 1. Purpose & Scope

The business runs its **own** courier service (not a third-party carrier). This spec adds:

- courier identities and a courier-facing section of the Mini App,
- a pool of paid orders that couriers claim themselves,
- live GPS tracking of the courier, shown to the customer on their order,
- delivery status feeding back into the existing order view.

It plugs into the seam Spec 1 left on purpose: the minimal `Shipment` row created by the Stripe
payment webhook, and the order detail screen that already polls order status.

Out of scope: see §14. In particular there is no dispatcher and no admin UI (Spec 3).

## 2. Decisions

Confirmed with the product owner:

| Topic | Decision |
|---|---|
| Assignment | Couriers **claim** orders from a shared pool. No dispatcher role. |
| GPS transport | Mini App for orders and status; location comes from Telegram **Live Location** shared with the bot, delivered to a backend webhook. Mini-App-only geolocation was rejected: it stops when the window is backgrounded or the screen locks. |
| Delivery point | The **customer** places a pin at checkout (optional step). No server-side geocoding, so no address is sent to a third party (GDPR). |

Assumptions made in this spec — not yet confirmed, flagged for review:

- The owner registers couriers by hand through the internal API.
- A paid order enters the pool immediately; there is no separate "packed" step.
- A courier may hold at most **3** active deliveries (configurable).
- "Delivered" is a single button press; no proof-of-delivery code.
- Live updates use **short polling (5 s)**, not SSE/WebSocket. Rationale: it matches the existing
  order-status polling, needs no new infrastructure, and is ample for tens of couriers.
  Only the transport would change if this is ever outgrown; clients read state from one endpoint.
- Map tiles come from OpenStreetMap through Leaflet (no API key). The tile URL is configurable
  because OSM's public servers are not meant for heavy traffic.

## 3. Lifecycle

```
processing ──claim──▶ assigned ──pickup──▶ shipped ──deliver──▶ delivered
     ▲                   │
     └──────release──────┘            (no release after pickup)
```

`Shipment.status` and `Order.status` move together:

| Event | Shipment | Order |
|---|---|---|
| payment confirmed (existing, Spec 1) | `processing` | `paid` |
| courier claims | `assigned` | `processing` |
| courier releases | `processing` | `paid` |
| courier picks up | `shipped` | `shipped` |
| courier delivers | `delivered` | `delivered` |

Every transition is one guarded `UPDATE … WHERE status = <expected> [AND courier_id = <me>]`
inside a transaction that also updates the order. A transition whose guard fails returns **409**
(wrong state) and an unknown or someone else's shipment returns **404**. This makes claiming
race-safe: two couriers pressing "claim" on the same order produce exactly one winner.

## 4. Data Model

New tables:

- **Courier** `(id, telegram_id BIGINT unique, name, phone, is_active, created_at, updated_at)`.
  Couriers are deactivated, never deleted.
- **CourierLocation** `(courier_id PK → Courier, latitude, longitude, updated_at)` — at most one
  row per courier: the **latest** position only. No history is kept.

Changes to `Shipment`:

- `status` gains the value `assigned`. The column is already a non-native enum stored as
  `VARCHAR(20)` without a DB constraint, so this needs no type migration.
- `courier_id` becomes a real foreign key to `Courier` (`ON DELETE RESTRICT`); it was a plain
  nullable integer for exactly this purpose. Existing rows are all `NULL`.
- New nullable timestamps: `assigned_at`, `picked_up_at`, `delivered_at`.
- `tracking_status` stays as is and unused.

`Order.delivery_address` (JSONB) gains optional `latitude` / `longitude`. No schema change; the
Python type hint widens to allow floats.

One Alembic revision covers all of the above.

## 5. Courier Identity & Authorization

- A courier is identified by Telegram user ID, using the same `initData` authentication as
  customers. No separate login.
- A new dependency `get_current_courier` wraps `get_current_telegram_user`, then loads the active
  `Courier` for that ID. A non-courier gets **403**.
- The owner manages couriers via the existing token-protected internal API:
  `POST /internal/couriers`, `PATCH /internal/couriers/{id}` (rename, change phone, activate /
  deactivate), `GET /internal/couriers`. Deactivating a courier blocks all `/courier/*` calls and
  location ingestion immediately.
- A deactivated or vanished courier would otherwise leave orders stuck with no way out, so the
  owner also gets `POST /internal/shipments/{shipment_id}/release`. It returns an `assigned` or
  `shipped` shipment to the pool (`processing`; order back to `paid`), clears the courier and
  deletes that courier's location if it was their last active delivery. It is a manual escape
  hatch only, not a returns or failed-delivery flow (§14).

## 6. Courier API (authenticated courier)

| Endpoint | Purpose |
|---|---|
| `GET /courier/me` | Profile plus `bot_username` (for the "share Live Location" link). 403 for non-couriers, which is how the frontend decides whether to show the courier section. |
| `GET /courier/pool` | Unclaimed paid orders, oldest first. Shows only `shipment_id`, `order_id`, city, street, item count, `placed_at`. **No phone, notes or coordinates.** |
| `GET /courier/deliveries` | The courier's active shipments (`assigned` / `shipped`) with full detail: complete address, phone, notes, coordinates if the customer set a pin, items as `name × qty`, plus `location_updated_at` so the courier can see whether GPS is arriving. No money amounts (payment is already taken). |
| `POST /courier/deliveries/{shipment_id}/claim` | Pool → assigned. Locks the courier's row (`SELECT … FOR UPDATE`) so the concurrent-delivery limit holds under simultaneous claims. 409 if taken, if the limit is reached, or if not in `processing`. |
| `POST …/{shipment_id}/release` | assigned → back to the pool. |
| `POST …/{shipment_id}/pickup` | assigned → shipped. |
| `POST …/{shipment_id}/deliver` | shipped → delivered. |

When a courier's last active shipment ends (delivered or released), their `CourierLocation` row is
deleted.

## 7. Location Ingestion (Telegram webhook)

`POST /webhooks/telegram`, authenticated by the `X-Telegram-Bot-Api-Secret-Token` header compared
in constant time with `TELEGRAM_WEBHOOK_SECRET`. If that setting is empty the route responds 404
(feature disabled). A wrong secret returns 403.

Telegram delivers the first location as a `message` and every later live-location update as an
`edited_message`, both carrying `location.latitude/longitude`. The handler:

1. Accepts only updates from a **private chat** whose sender is an **active courier**.
2. Accepts the position only if that courier has at least one `assigned` or `shipped` shipment;
   otherwise it is ignored. Working couriers only — nothing is stored about an idle courier.
3. Validates ranges and upserts the courier's single `CourierLocation` row (last write wins).
4. Returns **200** for every well-formed update, including ignored ones, so Telegram does not
   retry. Unparseable bodies get 400.

The bot does not reply to messages. Courier feedback comes from `location_updated_at` in
`GET /courier/deliveries`.

`scripts/set_telegram_webhook.py <public-https-url>` registers the webhook (`setWebhook` with the
secret token and `allowed_updates = ["message", "edited_message"]`). Telegram requires HTTPS. The
existing nginx `/api/` proxy already routes `/api/webhooks/telegram` to the API. A bot can have
only one update consumer; the webhook replaces any `getUpdates` polling on the same bot token.

## 8. Customer Tracking API

`GET /orders/{order_id}/tracking` (authenticated customer; only the order's owner, otherwise 404):

```
{ status,                       // shipment status, or null if no shipment yet
  courier: { name } | null,     // only while assigned / shipped; never the phone
  courier_location: { latitude, longitude, updated_at, is_stale } | null,
  destination: { latitude, longitude } | null,
  picked_up_at, delivered_at }
```

`courier_location` is returned **only while the shipment is `shipped`** and only if a position
exists. `is_stale` is computed on the server: the position is older than `LOCATION_STALE_SECONDS`
(default 120). Once delivered the location no longer exists (§6).

`GET /orders/{id}` is unchanged; it already exposes `shipment_status`.

## 9. Checkout: Delivery Point

`DeliveryAddressIn` gets optional `latitude` (−90…90) and `longitude` (−180…180), validated as
**both or neither**. Spec 1's address fields and the existing validation remain. An order without a
pin is fully valid; it simply has no destination marker for the courier or customer.

## 10. Frontend

New dependencies: `leaflet`, `react-leaflet`, `@types/leaflet`. Markers use `divIcon` /
`CircleMarker`, avoiding Leaflet's default-icon bundling problem. Attribution
"© OpenStreetMap contributors" is always shown. Config: `VITE_MAP_TILE_URL` (default OSM),
`VITE_MAP_DEFAULT_CENTER` (starting view when the user's location is unavailable).

- **Checkout — `MapPicker`.** Tap the map to place or move the pin; "Use my location" calls
  `navigator.geolocation`. Optional and non-blocking; tapping the map always works even if the
  location permission is denied.
- **Courier section (`/courier`).** The top-bar entry is shown only when `GET /courier/me`
  succeeds. Two tabs: **Pool** and **My deliveries**. Each delivery shows address, phone
  (`tel:` link), notes, a button that opens the address in the device's maps app, items, and the
  status action (Claim → Picked up → Delivered, or Release). A panel explains how to share Live
  Location (attach → Location → Share Live Location, choose the longest duration) with a button
  that opens the bot chat, and shows "GPS: last update N s ago" from `location_updated_at`.
- **Customer tracking.** The order detail screen gains a tracking card: a four-step timeline
  (Paid → Courier assigned → Out for delivery → Delivered) and, while `shipped`, a map with the
  courier marker and the destination pin, refreshed every 5 s. States: no location yet, stale
  ("updated N min ago"), delivered.
- **Polling.** `useOrder` keeps its 2 s poll while `pending_payment` and additionally polls every
  10 s while `paid` / `processing` / `shipped`, so status changes appear without a reload. Tracking
  polls every 5 s only while `shipped`.
- **i18n.** New `courier.*` and `tracking.*` strings in en / ru / uz.

## 11. Privacy & Security

- **Data minimisation:** only the latest position, only for couriers with an active delivery, and
  it is deleted when the last active delivery ends. A customer sees the courier's position only
  for their own order, only while it is out for delivery.
- **Contact details:** the customer's phone and notes are shown to a courier only **after** they
  claim the order; the pool shows city and street. The customer sees the courier's first name,
  never their phone.
- **Webhook:** constant-time secret check; only registered, active couriers in private chats are
  honoured; coordinate ranges validated.
- **Authorization:** every courier action verifies `courier_id` equals the caller in the same
  guarded `UPDATE`. Other users' orders and shipments return 404, not 403, so their existence is
  not revealed.
- **Third parties:** the only new external service is OSM tile fetching by the user's browser,
  which sees tile coordinates and the user's IP but no address or order data. No geocoding.

## 12. Error Handling

| Situation | Behaviour |
|---|---|
| Claim of an already-taken order | 409; the client refreshes the pool. |
| Claim over the concurrent-delivery limit | 409 with a message the UI shows. |
| Action from the wrong state or on someone else's shipment | 409 / 404 as in §3. |
| Location received for an idle or unknown courier | Ignored, still 200. |
| Courier stops sharing or loses signal | Customer map shows the stale banner; status still updates. |
| Customer has no pin | Timeline and courier marker only; no destination. |
| Tile server unreachable | The map area degrades; timeline and status are unaffected. |

## 13. Configuration & Deployment

New settings: `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`,
`MAX_ACTIVE_DELIVERIES_PER_COURIER` (default 3), `LOCATION_STALE_SECONDS` (default 120), and the
two `VITE_MAP_*` build args. They are passed through `docker-compose.yml`, documented in
`.env.example`, and the README gains a "Couriers & tracking" section: registering couriers,
setting the webhook, and testing without a phone by posting a sample update with `curl`.

## 14. Non-Goals

Dispatcher UI and manual or automatic assignment · Telegram notifications to the customer ·
proof-of-delivery code · failed delivery and returns · routes, ETA and geocoding · courier shifts
or availability · courier earnings · location history · multiple warehouses · the admin panel
(Spec 3).

## 15. Testing

Backend (pytest, real Postgres): every legal and illegal transition; a genuine two-session race on
one claim; the concurrent-delivery limit; authorization for each endpoint (non-courier, wrong
courier, wrong customer); the owner's release of a stuck shipment, including from a deactivated
courier; webhook — wrong/missing secret, disabled feature, unknown user,
non-private chat, idle courier, valid update upserts, location deleted after the last delivery;
tracking privacy (location hidden before `shipped`, hidden from other users, `is_stale`); pin
validation (both-or-neither, ranges); the migration round-trip already in the suite.

Frontend (Vitest + MSW): courier pool and delivery actions including the 409 path, `MapPicker`
output and checkout posting coordinates, tracking states, courier entry visibility. Leaflet is
mocked because jsdom has no layout.

Manual end to end: simulate the webhook with `curl` using a signed secret header, then confirm the
marker moves on a customer's order in a browser.
