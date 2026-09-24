# Spec 4: Stock reservation at checkout

Status: **designed, not implemented.** The owner approved the decisions in §2 and approach A in §3.
Sections §4–§9 are the design drafted from those decisions; the owner has not reviewed them section by
section yet, so confirm them before writing the implementation plan.

## 1. Problem

Today checkout only *checks* `variant.stock_qty >= qty`; stock is taken in `mark_order_paid` when the
Stripe webhook arrives. Two customers can check out the last item, both pay, and the second order gets
`orders.stock_shortfall = true`: the shop has sold something it does not have. Separately, an unpaid
`pending_payment` order never expires and the cart is already closed at checkout, so a customer who
abandons payment loses their cart.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| How long to hold stock for an unpaid order | **15 minutes**, configurable (`RESERVATION_TTL_MINUTES`) |
| What happens when the hold expires | Order → `cancelled` (reason `payment_expired`), the Stripe PaymentIntent is cancelled, stock is returned, **items go back into the customer's cart** |
| Payment that arrives after the order expired | **Always a full refund**, the order stays cancelled |
| How to reserve | **Approach A**: subtract `stock_qty` at checkout, add it back on expiry/cancel |

## 3. Approach A, and why

`stock_qty` already means "not yet sold", not "physically on the shelf": paid but undelivered orders are
already subtracted from it. Reservation only moves the subtraction from payment to checkout. So:

- no new column on `variants`; the catalog, cart, admin, low-stock and summary keep reading `stock_qty`;
- "two customers, last item" is settled by the database: a guarded
  `UPDATE variants SET stock_qty = stock_qty - :n WHERE id = :id AND stock_qty >= :n RETURNING id`
  either matches (reserved) or not (409), and row locks serialise the two checkouts;
- `stock_service.put_back` already exists for returning stock.

Rejected: a `reserved_qty` column (the `stock_qty - reserved_qty` formula would spread to every reader
for a difference nobody sees today), and a reservations table with `expires_at` (catalog reads become
aggregates, and a sweeper is still needed to cancel the order).

## 4. Data model

- `orders.reserved_until` — `timestamptz`, nullable. Set at checkout to `now() + TTL`.
  **`NULL` marks a legacy order** placed before this migration: it holds no reservation, so
  `mark_order_paid` keeps the old path for it (take stock at payment, set `stock_shortfall` if negative).
- `orders.cancel_reason = 'payment_expired'` for expired orders (`cancelled_by` stays `NULL`, as for
  script cancels). No new order status: it is a cancelled order with a machine reason.
- `stock_shortfall` stays (legacy orders and existing admin filter); new orders never set it.
- One Alembic migration adding the column. Settings: `RESERVATION_TTL_MINUTES` (15),
  `RESERVATION_SWEEP_SECONDS` (60); add both to `.env.example` and the README config table.

## 5. Checkout (`checkout_service.create_order_from_cart`)

The Stripe call must not run while variant rows are locked, so checkout becomes three short steps:

1. **Reserve.** Create the order (`reserved_until` set) and its items; reserve each variant in
   ascending id order (global lock order ends with variants) with the guarded UPDATE; mark the cart
   `checked_out`; commit. If any line fails: `rollback`, raise `ConflictError(code="insufficient_stock")`
   naming the SKU. Nothing was written.
2. **Create the PaymentIntent.** If Stripe fails: order → `cancelled` (reason `payment_setup_failed`),
   `put_back`, restore the cart (§7), commit, re-raise. The customer sees the error and still has a cart.
3. **Record the payment** row, commit, return the client secret.

If the process dies between 1 and 3, the order has no payment row; the sweeper expires it after the TTL
like any other (there is simply no PaymentIntent to cancel).

## 6. Expiry sweeper

An `asyncio` task started in `lifespan` (cancelled on shutdown) runs every `RESERVATION_SWEEP_SECONDS`:
select up to 100 ids of `pending_payment` orders with `reserved_until < now()`, and call
`reservation_service.expire_order(db, order_id)` for each, each in its own session/transaction, logging
and continuing on errors.

`expire_order`:

1. If a PaymentIntent exists, **cancel it in Stripe first**. Outcomes:
   - cancelled, or already cancelled → continue;
   - Stripe refuses because it already `succeeded` or is `processing` → **stop**, leave the order alone;
     the `payment_intent.succeeded` webhook will mark it paid with its reservation intact;
   - network/API error → stop; the next tick retries.
   Cancelling first means that once the order is expired, the customer can no longer pay it, so a late
   payment (§8) is only a narrow race rather than a normal path.
2. Guarded `UPDATE orders SET status='cancelled', cancel_reason='payment_expired', cancelled_at=now()
   WHERE id=:id AND status='pending_payment' AND reserved_until < now() RETURNING id`. No match → another
   worker or the webhook got there first; return.
3. `stock_service.put_back`, `payments.status = canceled`, restore the cart (§7), commit.

Several API processes may run the sweeper at once; the guarded UPDATE makes that safe, and cancelling an
already-cancelled PaymentIntent is harmless.

## 7. Restoring the cart

Shared helper used by §5 step 2 and §6: add the order's items back to the customer's **active** cart
(create one if none), adding quantities onto existing lines for the same variant. Skip variants whose
product is no longer `active`. Price is not copied: the cart shows current prices, as it always does.

## 8. Payment after expiry (`mark_order_paid`)

The guarded `pending_payment → paid` UPDATE already matches nothing for a cancelled order. New branch:
if the order is `cancelled` and `payments.refund_status IS NULL`, set `payments.status = succeeded`,
`refund_status = pending` and start a full refund through the existing `order_admin_service._refund`
machinery (idempotency key `late-payment-<order_id>`); `refund.*` webhooks finish it as for admin refunds.
The `refund_status IS NULL` condition makes Stripe's redeliveries and admin-cancelled orders (which
already have a refund status) no-ops. Stock is not touched: it was already returned on expiry.

For orders with `reserved_until` set, the paid path no longer calls `stock_service.take`.

## 9. API and frontend

- `GET /orders/{id}` and the admin order detail gain `reserved_until` and `cancel_reason`.
- Checkout 409 `insufficient_stock` → the checkout screen shows "Some items just sold out" and sends the
  customer back to the cart (react-query invalidates cart and catalog).
- Order detail, `pending_payment`: "Complete payment by HH:MM" (local time from `reserved_until`).
  Cancelled with `payment_expired`: "Payment time ran out. Your items are back in the cart." with a
  button to the cart. Refunded late payment shows the existing refund state.
- New strings in en/ru/uz (`locales.test.ts` enforces all three).
- Admin: orders list/detail show the reason `payment_expired` like any cancel reason; no new screens.

## 10. Testing

Backend (TDD, real Postgres):
- reserve succeeds and subtracts; a short line → 409 with code, and **nothing** changed;
- two independent sessions checking out the last unit: exactly one wins (use the independent-session
  fixtures from `test_courier_concurrency.py`);
- Stripe failure at checkout → order cancelled, stock and cart restored;
- `expire_order`: Stripe cancel OK; already succeeded (order untouched); network error (untouched);
  not yet due; already expired by another worker; cart merge with an existing active cart; archived product skipped;
- `mark_order_paid`: reserved order does not take stock again; legacy order (`reserved_until NULL`) keeps
  the shortfall path; payment on an expired order starts one refund, a replay starts none;
- sweeper loop: processes due orders, survives one failing order.

Frontend: 409 handling on checkout, the pending-payment deadline, the expired state with the cart link.

## 11. Out of scope

Holding stock while items sit in the cart; partial fulfilment; per-product TTL; notifying the customer in
Telegram about expiry; admin cancel of `pending_payment` orders (the sweeper covers them).
