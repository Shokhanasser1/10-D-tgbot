# Spec 11: Sellers' money (stage D of the marketplace)

Status: **designed and approved by the owner (2026-10-04); implemented 2026-10-04, not deployed.**

## 1. Problem

Customers pay the platform (Click/Payme or cash to the courier). The platform keeps a commission
and pays each seller their share by hand. Nothing records what a seller has earned, what was paid
out, or what is still owed.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| Commission | **a percentage per seller** (default 10%), of the goods total; shipping is the platform's |
| When the seller earns | **on delivery**; cancelled orders earn nothing, so nothing is ever reversed |
| Payouts | **the owner pays by hand and records it**; the system keeps "earned − paid out = owed" |
| Rate changes | the rate is **copied onto the order at checkout**: a later change never alters it |
| Old orders | delivered before this stage: no earnings back-filled |

## 3. Data

- `sellers.commission_percent` numeric(5,2), not null, default 10, check 0..100.
- `orders.commission_percent` numeric(5,2), not null: copied from the seller at checkout; the
  migration fills existing orders from their seller.
- `seller_earnings` (one per delivered order): `id`, `order_id` (unique FK), `seller_id` (FK),
  `currency`, `goods_total` (the order's subtotal), `commission_percent`, `commission`
  (`goods_total × percent / 100`, rounded half-up to cents), `amount` (`goods_total − commission`),
  `earned_at`.
- `seller_payouts`: `id`, `seller_id` (FK), `currency`, `amount` (> 0), `note` (≤ 500, optional),
  `created_by` (telegram id), `created_at`.

The balance of a seller in a currency is `sum(earnings.amount) − sum(payouts.amount)`.

## 4. Flow

- **Delivery** (courier's "Delivered", `dispatch_service.deliver`): in the same transaction, insert
  the order's earning (`ON CONFLICT (order_id) DO NOTHING`, so a replay adds nothing).
- **Recording a payout**: `POST /internal/sellers/{id}/payouts {amount, currency, note?}`
  (permission `payouts.manage`, **password re-entry** like refunds). Refused with 409
  `exceeds_balance` when the amount is more than the seller's balance in that currency, 422 for a
  non-positive amount, 404 for an unknown seller. The seller's active accounts get a Telegram
  message: "Payout recorded: X. Balance: Y."

## 5. Permissions

New `payouts.manage` (owner, accountant), 🔒 for writes. The Sellers section opens with
`sellers.manage` **or** `payouts.manage` (an accountant sees the list read-only, with balances,
and records payouts; adding and editing sellers, including the rate, stays `sellers.manage`).
`GET /internal/sellers` also accepts `payouts.manage`.

## 6. API

- `GET /internal/sellers` items gain `commission_percent` and `balances: [{currency, earned,
  paid_out, balance}]` (balances only for `payouts.manage`; empty otherwise).
- `POST/PATCH /internal/sellers` accept `commission_percent` (0..100).
- `GET /internal/sellers/{id}/ledger` (`payouts.manage`) → `{balances, earnings: [...], payouts:
  [...]}`, newest first, the last 100 of each.
- `POST /internal/sellers/{id}/payouts` as in §4.
- Seller: `GET /internal/seller/earnings` (seller accounts only) → the same shape for their own
  seller.

Earning item: `order_id, earned_at, currency, goods_total, commission_percent, commission, amount`.
Payout item: `id, created_at, currency, amount, note`.

## 7. Frontend

- **Sellers** (staff): the add/edit forms gain "Commission, %"; each row shows "Owed: X" for
  `payouts.manage`; a seller page `/admin/sellers/:id` (from the row) with balances, earnings,
  payouts and a "Record payout" form (amount, note) that asks for the password like refunds.
- **Money** (a seller account, new section `earnings`): balance, earnings by order, payouts.

## 8. Out of scope

Automatic transfers; commission figures in the Summary; exports; earnings for orders delivered
before this stage; partial refunds after delivery.

## 9. Testing

Backend: checkout copies the rate; delivery creates exactly one earning with the right rounding
(also for cash orders); a cancelled order earns nothing; balances; payout recording (🔒, positive,
not above the balance, per currency, notifies the seller); who may read and write; the seller's
own earnings only; migration (rates filled, tables created).

Frontend: commission in the seller forms; balances in the list; the seller page and the payout
form (with the confirmation flow); the seller's Money section; navigation.
