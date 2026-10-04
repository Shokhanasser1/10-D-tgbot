# Spec 10: Orders per seller (stage C of the marketplace)

Status: **designed and approved by the owner (2026-10-04); implemented and deployed 2026-10-04.**

## 1. Problem

Since Spec 9 every product has a seller and a cart holds one seller's products, but an order does
not know its seller: a paid order goes straight into the courier pool, nobody tells the seller,
and the courier does not know where to collect it.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| When does a paid order reach the couriers? | **after the seller presses "Ready for pickup"**; until then it waits for the seller |
| May a seller cancel an order? | **no**: cancelling and refunds stay with the platform, as now |
| What does a seller see of the customer? | **only the order**: number, date, items, quantities, prices, goods total, payment method, status. No name, phone or address |
| Who else may mark an order ready? | the platform: owner, manager, dispatcher (a slow seller, or the platform's own "Main shop") |
| The customer | sees nothing new: the order shows as paid while the seller prepares it |

## 3. Data

- `orders.seller_id`: FK `sellers.id` `ON DELETE RESTRICT`, **not null**, indexed. Checkout copies
  it from the cart's products; a cart with several sellers (impossible through the API since Spec 9,
  checked again here) answers 409 `cart_other_seller`.
- `shipments.ready_at`: timestamptz, null. Null means "the seller is preparing it". Shipment statuses
  do not change: the pool is `status = processing AND courier_id IS NULL AND ready_at IS NOT NULL`,
  and every guarded transition (claim, release, pickup, deliver, cancel) stays as it is, except that
  a claim also requires `ready_at IS NOT NULL`.

Migration (after `a9b8c7d6e5f4`): add `orders.seller_id`, fill it from each order's products (the
lowest seller id if an old order ever mixed sellers); orders without items go to a "Main shop"
seller created for them; make it not null. Add `shipments.ready_at` and set it to `created_at`
for existing shipments, so orders already in the pool stay there. Downgrade drops both columns
(an order waiting for its seller then appears in the pool).

## 4. Flow

1. Payment succeeds (or a cash order is confirmed): order `paid`, shipment `processing` with
   `ready_at` null. Notifications: the customer (unchanged), the **seller's active accounts**
   ("New order #N: 3 items. Collect it and press Ready, then a courier comes." with a button to
   `admin/orders/N`), the platform's order admins (unchanged). **No pool message yet.**
2. `POST /internal/orders/{id}/ready` (permission `orders.prepare`): a guarded
   `UPDATE shipments SET ready_at = now() WHERE order_id = :id AND status = 'processing' AND
   ready_at IS NULL`. Then the couriers get the pool message, now with the pickup place
   (" Pickup: Lola Beauty, Chilonzor 5."). Answers `{order_id, ready_at}`.
   - Already ready: 200 with the existing `ready_at`, no second message.
   - Unknown order, or another seller's (for a seller): 404.
   - Not waiting (unpaid, cancelled, already with a courier): 409 `invalid_state`.
3. From here on everything works as before: claim, pickup, deliver, release (back to the pool,
   still ready), cancel by the platform before pickup.

## 5. Permissions

New permission **`orders.prepare`**: owner, manager, dispatcher, and seller (scoped to their
orders). It needs no password re-entry.

## 6. Seller API (no customer data)

Only for seller accounts (`orders.prepare` and a seller principal; staff get 403):

- `GET /internal/seller/orders?limit=&offset=` → `{items, total}`, newest first, the seller's
  orders that were paid (status `paid`, `processing`, `shipped`, `delivered`, `cancelled`; never
  `pending_payment`). Item: `id, status, placed_at, subtotal, currency, payment_method,
  item_count, shipment_status, ready_at`.
- `GET /internal/seller/orders/{id}` → the same plus `items: [{product_name, sku, qty,
  unit_price, line_total}]`. Another seller's or an unpaid order: 404.

`subtotal` is the goods total; shipping belongs to the platform.

## 7. Platform views

- `GET /internal/orders` items gain `seller_id`, `seller_name`, `ready_at`; filter `seller_id`.
- `GET /internal/orders/{id}` gains `seller: {id, name, phone, pickup_address}`,
  `shipment.ready_at` and `can_mark_ready`.
- Courier pool items and deliveries gain `pickup: {name, address, phone}` (the seller's).

## 8. Frontend

- **Seller**: an **Orders** section (seller accounts with `orders.prepare`): a list with a
  "Waiting for you" / "Ready" / delivery status badge and a page per order with its items and a
  **Ready for pickup** button. The notification's `admin/orders/N` link opens it.
- **Platform**: the orders list shows the seller, a "Preparing" badge for orders waiting for their
  seller, and a seller filter; the order page shows the seller and its pickup address and a
  **Mark ready** button.
- **Courier**: pool cards and delivery cards show "Pickup: name, address" (and the phone on a
  delivery card).

## 9. Out of scope

Commission and payouts (stage D); a "being prepared" step in the customer's timeline; seller
notifications for cancellations; seller-side cancelling.

## 10. Testing

Backend: checkout stores the seller; a paid order is not in the pool and cannot be claimed until
ready; ready by the seller, by a dispatcher, refused for another seller (404), for a catalog
manager (403), for a cancelled order (409), idempotent; notifications (seller on payment, couriers
on ready, with the pickup); seller API returns only their paid orders and no customer data; admin
list/detail carry the seller, readiness and the filter; courier pool and deliveries carry the
pickup; the migration fills `orders.seller_id` and `ready_at`.

Frontend: seller orders list and page (ready button), the staff order page's mark-ready button and
seller block, the list's seller and "Preparing" badge and filter, courier cards' pickup.
