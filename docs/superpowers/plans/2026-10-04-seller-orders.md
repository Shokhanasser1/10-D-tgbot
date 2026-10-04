# Seller Orders Implementation Plan

> **For agentic workers:** implement task by task, in order; each task ends green and committed.
> Condensed like the Spec 9 plan: files, interfaces and test cases are fixed here, the code is
> written test-first during execution.

**Goal:** an order knows its seller; a paid order waits for the seller's "Ready for pickup" before
couriers see it; sellers see their orders without customer data; couriers see where to collect.

**Architecture:** `orders.seller_id` (from the cart at checkout) and `shipments.ready_at` (null =
the seller is preparing). The pool and the claim add `ready_at IS NOT NULL`; nothing else in the
shipment state machine changes. `order_paid` notifies the seller instead of the couriers; a new
`order_ready` event notifies the couriers. Seller reads live in their own module and schemas, so
customer data never reaches them.

Spec: `docs/superpowers/specs/2026-10-04-seller-orders-design.md`.

## Global Constraints

- As in the Spec 9 plan (Postgres via the compose `db`, ruff, prettier, en/ru/uz, commit format).
- Another seller's order → 404; not waiting → 409 `invalid_state`; staff on seller endpoints → 403.
- Seller responses never include `delivery_address`, `customer`, `telegram_id`, phone or notes.

### Task 1: data and checkout
`app/models/{order,shipment}.py`, migration `b1c2d3e4f5a6_seller_orders.py`,
`app/services/checkout_service.py`, test factories (`add_paid_order(..., ready=True, seller_id=None)`),
the tests building `Order(...)` (`test_courier_models`, `test_models`, `test_stock`, `test_webhooks`),
`scripts/seed_courier_demo.py`, `tests/test_migrations.py` (`_insert_order` adds a seller at head).
Tests: checkout stores the cart's seller; migration fills `seller_id` from items and `ready_at`
from `created_at`; full suite green.

### Task 2: readiness, the pool, notifications
`Permission.orders_prepare` (owner, manager, dispatcher, seller), `app/services/order_ready_service.py`
(`mark_ready(db, order_id, scope) -> ReadyOut`), route `POST /internal/orders/{id}/ready`,
`courier_service.get_pool` + `dispatch_service.claim` require `ready_at`, `notification_events`
(`order_paid` → seller message, no pool message; `order_ready` → pool message with pickup),
templates `seller_new_order`, `pool_pickup`, `button_seller_order`.
Tests (`tests/test_order_ready.py`): not in pool until ready; claim of a not-ready shipment 404;
seller marks own → in pool, couriers notified with pickup; idempotent; other seller 404; dispatcher
ok; catalog_manager 403; cancelled 409; payment notifies the seller's active accounts and no
courier. Update `test_notifications` (payment no longer tells couriers), `test_payment_methods`
(cash order reaches the pool after ready), `test_order_admin` if needed.

### Task 3: seller order API
`app/schemas/seller_orders.py`, `app/services/seller_order_service.py`,
`app/api/routes/internal_seller_orders.py`.
Tests (`tests/test_seller_orders_api.py`): own paid orders only, newest first, no unpaid; no
customer keys anywhere in the JSON; detail items and subtotal; other seller / unpaid 404; staff 403.

### Task 4: platform and courier views
`app/schemas/order_admin.py` (+ `seller_id`, `seller_name`, `ready_at`, detail `seller`,
`shipment.ready_at`, `can_mark_ready`), `order_admin_service` (+ `seller_id` filter),
`app/schemas/courier.py` (`PickupOut`), `courier_service` (pool + deliveries pickup).
Tests: admin list/detail/filter; courier pool and deliveries pickup.

### Task 5: frontend
Courier cards (pickup); admin orders list (seller, Preparing badge, filter) and order page
(seller block, Mark ready); seller Orders section (list + page + Ready button) with
`permissions.ts` opening `orders` for seller accounts holding `orders.prepare`; fixtures, mocks,
strings. Tests per screen.

### Task 6: docs and checks
README, PROJECT_STATE (Spec 10 row, counts, alembic head), spec status; full backend and
frontend checks; commit. Deploy waits for the owner.
