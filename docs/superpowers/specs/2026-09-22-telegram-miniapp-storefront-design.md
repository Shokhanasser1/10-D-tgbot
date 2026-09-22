# Telegram Mini App E-Commerce — Storefront (Spec 1 of 3)

Status: Approved
Date: 2026-09-22

## 1. Purpose & Scope

Build a Telegram Mini App (WebApp) e-commerce storefront. Initial launch niche is **cosmetics**, but the architecture must not hardcode cosmetics-specific concepts — a new niche (e.g. clothing, electronics) should be addable via data (categories/attributes), not code changes.

This is a deliberate three-part product, split because the full request (storefront + own courier logistics with live GPS tracking + admin panel) spans independent subsystems that would otherwise blur scope:

1. **Spec 1 (this document)** — customer-facing storefront: catalog, cart, checkout, payment, order placement, order status view.
2. **Spec 2 (future)** — delivery/logistics engine: courier accounts & auth, order dispatch/assignment, courier-facing interface, live GPS tracking. Plugs into the `Shipment` entity defined here.
3. **Spec 3 (future)** — admin panel UI. Will consume the same internal product-management API defined here (see §5).

Out of scope for this document: anything belonging to Spec 2 or Spec 3, promo codes/loyalty programs, multi-currency.

## 2. Market & Business Context

- Target market: International / Europe.
- Languages at launch: English (default), Russian, Uzbek.
- Currency: single currency at launch — **EUR** (explicit assumption; not directly requested by the user, flagged for confirmation before implementation).
- Delivery: the business runs its own courier service (not a third-party carrier like DHL/DPD). Live dispatch/GPS is Spec 2; this spec only captures the delivery address and a placeholder shipment status.

## 3. Architecture

**Backend:** Python, FastAPI (async), SQLAlchemy 2.0 (async) + Alembic migrations, PostgreSQL 16.

**Frontend:** React + TypeScript, running as a Telegram Mini App inside the Telegram WebView, using the Telegram WebApp JS SDK for auth handshake, theming hooks, and native UI affordances (main button, back button, haptics). i18n via `react-i18next`.

**Payments:** Stripe, integrated directly in the Mini App via the Stripe Payment Element (not the Telegram Bot Payments API — avoids per-country provider restrictions and gives full control over the checkout UX). Stripe webhooks confirm payment server-side.

**Auth:** No separate registration/login. Every request is authenticated by validating Telegram's `initData` payload server-side (HMAC-SHA256 against the bot token, per Telegram's documented scheme), and the user is identified by their Telegram user ID.

**Design system:** Light, minimalist visual language taken from the project's reference screens (`reference2.png`–`reference4.png`): palette `#FFFFFF` / `#F3F4F4` / `#262626`, Inter Tight typeface, card-based product/cart layout, pill-shaped buttons, floating search/cart affordances. (`reference1.png`, a dark glassmorphic tech-product landing page, was evaluated and explicitly rejected as the visual direction for this app.)

**Deployment:** Docker Compose (FastAPI service, PostgreSQL, Nginx serving the React build / reverse-proxying the API). No cloud provider chosen yet — kept container-portable so that decision can be made later without rework.

**Multi-niche principle:** Category and Product are generic. Niche-specific concepts (cosmetics "shade", clothing "size", electronics "storage capacity") are expressed entirely as `Attribute` data scoped to categories — never as code branches or niche-specific tables. Launching a new niche means adding categories/attributes through the internal product-management API, not shipping new code.

## 4. Data Model

- **Category** `(id, slug, parent_id, sort_order)` — self-referencing hierarchy, niche-agnostic.
- **Attribute** `(id, key, category_id, value_type)` — defines an attribute (e.g. `shade`, `size`) scoped to one or more categories.
- **Product** `(id, category_id, base_sku, base_price, status[draft|active|archived], created_at)`.
- **Variant** `(id, product_id, sku, price, stock_qty, attribute_values JSONB)` — the concrete purchasable unit; cart/order line items reference `Variant`, matching the reference UI where cart lines show specific size/color, not a bare product.
- **ProductImage** `(id, product_id, variant_id nullable, url, position)`.
- **Translation** `(entity_type, entity_id, locale, field, value)` — holds translated text (product/category name, description) per locale. Adding a 4th language is a data operation, not a migration.
- **TelegramUser** `(telegram_id PK, username, first_name, last_name, phone_number nullable, locale, created_at)`.
- **Cart** `(id, telegram_id, status)` / **CartItem** `(cart_id, variant_id, qty, unit_price_snapshot)`.
- **Order** `(id, telegram_id, status[pending_payment|paid|processing|shipped|delivered|cancelled], currency, subtotal, shipping_cost, total, delivery_address JSONB, placed_at)` / **OrderItem** `(order_id, variant_id, product_name_snapshot, qty, unit_price_snapshot)`.
- **Payment** `(id, order_id, stripe_payment_intent_id, status, amount, currency)`.
- **Shipment** `(id, order_id, status[processing|shipped|delivered], courier_id nullable, tracking_status nullable)` — intentionally minimal placeholder; this is the integration seam Spec 2 will extend (courier assignment, GPS updates) without changing this schema's shape.

## 5. Key Flows & API Surface

**Flows:**
1. App open → validate `initData` → upsert `TelegramUser` → resolve locale (Telegram `language_code`, overridable by stored preference).
2. Browse: categories → filtered product list → product detail (variant picker: shade/size selection updates price/stock) → add to cart.
3. Cart: add/update/remove variant line items, live subtotal.
4. Checkout: enter/select delivery address → compute shipping cost (flat-rate/zone formula for now, no live courier API) → create `Order` (`pending_payment`) → create Stripe PaymentIntent → render Payment Element.
5. Stripe webhook confirms payment → `Order` → `paid` → placeholder `Shipment` created (`processing`).
6. "My Orders" → list + current status per order.

**REST API (FastAPI):**
- `GET /catalog/categories`
- `GET /catalog/products?category=&locale=`
- `GET /catalog/products/{id}`
- `GET/POST/PATCH/DELETE /cart/items`
- `POST /checkout`
- `POST /webhooks/stripe`
- `GET /orders`, `GET /orders/{id}`
- `POST/PATCH /internal/products`, `/internal/variants`, `/internal/categories`, `/internal/attributes` — token-protected, used to populate the catalog before Spec 3 (admin panel) exists. Spec 3 will call these same endpoints rather than introducing a parallel API.

## 6. Testing Strategy

- Backend: `pytest` + `httpx` for API integration tests (catalog, cart, checkout, webhook handling), model/migration tests.
- Frontend: Vitest + Testing Library covering catalog browsing, cart mutations, and checkout submission.

## 7. Explicit Non-Goals (this spec)

- Live courier/GPS dispatch (Spec 2).
- Admin panel UI (Spec 3).
- Promo codes / loyalty programs.
- Multi-currency support.
- Third-party carrier API integration (DHL/DPD/etc.) — the business uses its own courier service (Spec 2).
