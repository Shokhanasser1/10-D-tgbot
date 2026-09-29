# Spec 6: Payments in Uzbekistan (Click/Payme via Telegram Payments, cash on delivery)

Status: **designed, approved section by section by the owner (2026-09-29), not implemented.**

## 1. Problem

The shop is in Tashkent but can only take money through Stripe, in EUR. Stripe does not onboard
merchants in Uzbekistan, so the shop cannot take real payments. Customers there pay with Uzcard/Humo
cards through Click or Payme, or in cash to the courier.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| Payment methods at launch | **Telegram Payments with Click or Payme** as the provider, and **cash on delivery** |
| Direct Payme/Click Merchant API | not now (much more work, needs a contract per provider) |
| Stripe | **kept as an option**, switched on by its keys, for shops elsewhere |
| Currency | **UZS** for the whole shop (catalog, shipping, payment) |

Telegram Payments supports exactly these two Uzbek providers; the provider is connected in
@BotFather → Payments, which issues a test or live provider token.

## 3. Payment methods

`orders.payment_method`: `telegram` | `cash` | `stripe` (varchar, not null; existing rows become `stripe`).
Each method is on when configured:

| Method | On when |
|---|---|
| `telegram` | `TELEGRAM_PAYMENT_PROVIDER_TOKEN` is set |
| `cash` | `CASH_ON_DELIVERY_ENABLED=true` |
| `stripe` | `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` are set |

`GET /checkout/methods` (customer auth) returns the enabled methods in that order, plus the shop currency.
`POST /checkout` takes `payment_method` (default: the first enabled one); a disabled or unknown method is
400. With no method enabled checkout is 400 `no_payment_method`.

## 4. Flows

Common to all: checkout reserves stock exactly as in Spec 4 (guarded UPDATE, `reserved_until`, cart
closed), then does the method-specific step.

### 4.1 Telegram Payments (Click / Payme)

1. After reserving, the API calls Bot API `createInvoiceLink` with: `title` "Order #42", `description` the
   item names (trimmed to Telegram's limit), `payload` `order:42`, `provider_token`, `currency` = order
   currency, `prices` = one line per order item plus a shipping line when it is not free, amounts in minor
   units (`to_minor_units`), `need_*` all false (the address is already known). If Telegram fails, the
   order is undone like a Stripe failure (Spec 4 §5 step 2: cancelled `payment_setup_failed`, stock and cart
   restored) and the API answers 502 `payment_unavailable`.
2. A `payments` row is created with `method=telegram`, status `requires_payment_method`, no Stripe ID.
   The response carries `invoice_url` (instead of `client_secret`) and `reserved_until`.
3. The Mini App calls `Telegram.WebApp.openInvoice(invoice_url, callback)`. `paid` → the same
   "confirming" step as Stripe (polling the order until it is no longer `pending_payment`); `cancelled`
   → stays on the payment step with a "Pay" button that reopens the invoice; `failed` → an error.
4. Before charging, Telegram sends `pre_checkout_query` to the bot webhook. The webhook answers in its
   response body with `answerPreCheckoutQuery` (Telegram requires an answer within 10 s):
   `ok: true` only if the payload names an order that is still `pending_payment`, not past
   `reserved_until`, whose total in minor units and currency equal the query's; in that case
   `reserved_until` is also pushed to at least now + 5 min so the sweeper cannot expire the order while the
   customer is paying. Otherwise `ok: false` with an `error_message` in the customer's language
   ("Payment time ran out, please order again" / "This order can no longer be paid").
5. Telegram then sends a message with `successful_payment`. The webhook stores
   `telegram_payment_charge_id` and `provider_payment_charge_id` on the payment and calls
   `mark_order_paid` (unchanged: guarded transition, notifications from Spec 5). A replay changes nothing.

Because step 4 refuses expired orders, a Telegram payment for an expired order can only happen in the
narrow race between a positive pre-checkout answer and the sweeper; step 4's extension closes it in
practice. If it still happens, §5's late-payment path applies (manual refund).

Expiry of a Telegram order: the sweeper expires it as in Spec 4, but there is no PaymentIntent to cancel.

The bot webhook must receive `pre_checkout_query`: `set_telegram_webhook` adds it to `allowed_updates`
(re-run the script once after upgrading).

### 4.2 Cash on delivery

1. After reserving, the order moves straight to `paid` ("confirmed, waiting for a courier") in the same
   transaction, the shipment is created in the pool, and a `payments` row is created with `method=cash`,
   status `requires_payment_method` (money not collected yet). `reserved_until` is set but irrelevant:
   the sweeper only looks at `pending_payment`.
2. The response has neither `client_secret` nor `invoice_url`; the Mini App goes straight to the order.
3. Customer sees "Pay in cash on delivery: 250 000 so'm" on the order. The courier's delivery card shows
   "Collect in cash: 250 000 so'm", and the deliver button reads "Delivered, cash received".
4. `deliver` on a cash order also sets its payment to `succeeded` (cash collected) in the same transaction.

### 4.3 Stripe

Unchanged, only offered when its keys are set.

## 5. Cancellations and refunds

`payments.method` decides what cancelling a paid order means:

| Method | Money taken? | On admin cancel / late payment |
|---|---|---|
| `stripe` | yes | automatic full refund (existing) |
| `telegram` | yes | `refund_status = manual_required` (new value); owners are notified; an owner refunds in the Click/Payme merchant cabinet and presses "Refund done" |
| `cash`, before delivery | no | payment → `canceled`, no refund; the customer is told the order was cancelled, without the refund sentence |

New endpoint `POST /internal/orders/{id}/refund/confirm` (owner only): `manual_required` → `succeeded`,
409 `invalid_state` otherwise; the customer gets the Spec 5 "refunded" message. `retry_refund` stays
Stripe-only (409 for other methods).

The late-payment path (Spec 4 §8) branches the same way: Stripe refunds automatically, Telegram becomes
`manual_required`.

## 6. Currency (UZS)

- `DEFAULT_CURRENCY=UZS` in `.env.example`; shipping `SHIPPING_FLAT_RATE=20000`,
  `FREE_SHIPPING_THRESHOLD=300000`. Code defaults stay as they are; the shop's `.env` decides.
- Amounts are still `Numeric(10,2)`; payment APIs get minor units (×100), which is what both Telegram and
  Stripe expect for UZS.
- Display: currencies without fractional prices in practice (UZS) are shown without decimals, grouped by
  locale: "250 000 so'm" (uz), "250 000 сум" (ru), "UZS 250,000" (en). Frontend `Price` and the admin
  formatter use `Intl.NumberFormat` with `maximumFractionDigits: 0` for UZS; the notification templates'
  `money()` does the same with the words above.
- `seed_demo_data` gets UZS prices (e.g. 89 000, 129 000). Existing orders keep their own currency.

## 7. Admin panel and notifications

- Orders list and detail show the payment method ("Click/Payme", "Cash", "Stripe"). Cash orders show
  "cash pending" / "cash collected".
- `manual_required` detail block: amount, method, `provider_payment_charge_id` and
  `telegram_payment_charge_id` to find the payment in the cabinet, and a "Refund done" button (owner).
- Spec 5 changes:
  - cash checkout sends the customer "Order #42 is confirmed. Pay in cash on delivery: 250 000 so'm."
    (instead of "is paid");
  - pool messages for cash orders add "cash: 250 000 so'm";
  - `manual_required` notifies owners: "Refund 250 000 so'm for order #42 by hand in the Click/Payme
    cabinet (payment ID …), then press Refund done." (replaces "refund failed" for Telegram payments);
  - cancelling a cash order uses a text without the refund sentence.

## 8. Data model changes (one migration)

- `orders.payment_method` varchar(20) not null, server default `stripe` for existing rows.
- `payments.method` varchar(20) not null (same backfill); `payments.stripe_payment_intent_id` becomes
  nullable (still unique); new nullable `telegram_payment_charge_id`, `provider_payment_charge_id`
  (varchar 255).
- `RefundStatus` gains `manual_required` (non-native enum: no type migration).

## 9. Configuration

`TELEGRAM_PAYMENT_PROVIDER_TOKEN` (from @BotFather → Payments → Click or Payme; test tokens work with
the providers' test cards), `CASH_ON_DELIVERY_ENABLED` (false), `DEFAULT_CURRENCY`, shipping values;
documented in `.env.example`, `docker-compose.yml`, README and `docs/LAUNCH_GUIDE_RU.md` (a new section
"Оплата через Click/Payme" replacing Stripe as the main path; Stripe moves to "optional").

## 10. Error handling

- Telegram `createInvoiceLink` errors → undo reservation, 502 `payment_unavailable` (same handler shape as
  Stripe; the bot token never appears in logs or responses).
- `pre_checkout_query` is answered from the webhook response, so no outgoing call can fail; malformed
  payloads get `ok: false`.
- `successful_payment` for an unknown order is logged and acknowledged (200), so Telegram stops retrying.
- Only the provider token owner (the bot) can create invoices; amounts are always taken from the order,
  never from the client.

## 11. Testing

Backend (TDD, real Postgres): methods endpoint per configuration; checkout per method (telegram invoice
payload/prices/minor units, cash straight to `paid` with a shipment, disabled method 400); invoice failure
undoes the reservation; pre-checkout: ok, wrong amount, wrong currency, expired, already paid, unknown
payload, extension of `reserved_until`; successful_payment marks paid and stores both charge IDs, replay is
a no-op; cash deliver marks the payment collected; cancel per method (stripe refund, telegram
`manual_required` + owner message, cash no refund); refund/confirm; late Telegram payment →
`manual_required`; migration round-trip; UZS money formatting.

Frontend: method picker (hidden with one method), telegram flow with `openInvoice` callbacks (paid,
cancelled → reopen, failed), cash goes straight to the order, cash texts for customer and courier, admin
payment method and "Refund done", UZS price formatting.

## 12. Out of scope

Direct Payme/Click Merchant APIs and automatic refunds for them, partial refunds, cash limits, card
payments on delivery (POS terminals), multi-currency catalogs, exchange rates, fiscal receipts (OFD).
