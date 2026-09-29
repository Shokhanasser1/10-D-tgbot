# Spec 5: Telegram notifications

Status: **designed, approved section by section by the owner (2026-09-29), not implemented.**

## 1. Problem

Everything a customer, courier or admin learns about an order today they learn by opening the Mini App
and looking. A customer does not know their order was paid or is at the door; couriers do not know a new
order is waiting in the pool; the owner does not know a refund failed. In a Telegram shop the bot chat is
the natural place for this.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| Who gets messages in v1 | customers (status, cancellations, refunds), couriers (orders in the pool), owners/dispatchers (new orders and problems) |
| How messages are sent | **outbox table in Postgres + background sender** (approach A); rejected: send right after commit (messages lost on crash/errors), Redis + worker (a new service, too much for one shop) |
| Admin history screen | not in v1 |

## 3. Events and recipients

Language: the recipient's `telegram_users.locale` (en/ru/uz, set on first Mini App visit; `en` if the
recipient has no row). Every message may carry one `web_app` button that opens a Mini App screen at
`WEBAPP_URL` + path; without an `https://` `WEBAPP_URL` the message is sent without a button.

| Event (code) | Recipient | Message (en) | Button path |
|---|---|---|---|
| payment confirmed (`order_service.mark_order_paid`, successful transition only) | customer | "Order #42 is paid. We're finding a courier." | `orders/42` |
| | every active courier | "New order in the pool: Tashkent, Amir Temur 1, 2 items." (city, street, item count only, as the pool shows) | `courier` |
| | active owners and dispatchers | "New order #42, €44.97." + " ⚠ Not enough stock." when `stock_shortfall` | `admin/orders/42` |
| courier claimed (`dispatch_service.claim`) | customer | "Courier Bekzod has taken order #42." | `orders/42` |
| picked up (`pickup`) | customer | "Order #42 is on its way. Follow the courier on the map." | `orders/42` |
| delivered (`deliver`) | customer | "Order #42 has been delivered. Thank you!" | none |
| back in the pool (`release`, `force_release`) | every active courier except the one who released it | "Order back in the pool: Tashkent, Amir Temur 1, 2 items." | `courier` |
| payment time ran out (`reservation_service.expire_order`) | customer | "Payment time for order #42 ran out. Your items are back in the cart." | `cart` |
| cancelled by the shop (`order_admin_service.cancel_order`) | customer | "Order #42 was cancelled by the shop: {reason}. Your money will be refunded." | `orders/42` |
| refund succeeded (`apply_refund_event` / `refund_payment` reaching `succeeded`) | customer | "The payment for order #42 has been refunded." | none |
| refund failed (reaching `failed`) | active owners | "⚠ The refund for order #42 failed. Retry it in the admin panel." | `admin/orders/42` |

Deliberately not sent: to the customer on release (for them the order is simply paid again); to a courier
about their own action; for `payment_setup_failed` (the customer sees the error on screen); a second
"refund succeeded" when Stripe repeats the event. A person who is several recipients at once (an owner
who is also a courier) gets each message; they mean different things.

The courier's first name is the only courier detail a customer sees, as in tracking. Pool messages never
contain the phone, house details beyond street, or notes (same data minimisation as the pool, Spec 2).

## 4. Data model

New table `notifications` (one Alembic migration):

| Column | Type | Notes |
|---|---|---|
| `id` | serial PK | |
| `chat_id` | bigint, not null | Telegram user ID (private chat ID = user ID) |
| `kind` | varchar(40), not null | e.g. `order_paid`, `pool_new`; for logs and tests |
| `dedupe_key` | varchar(120), **unique**, not null | e.g. `order_paid:42:customer:111`; replays insert nothing |
| `text` | text, not null | rendered in the recipient's language |
| `reply_markup` | jsonb, null | the inline keyboard, if any |
| `status` | varchar(20), not null, default `pending` | `pending` / `sent` / `failed` / `undeliverable` |
| `attempts` | int, not null, default 0 | |
| `next_attempt_at` | timestamptz, not null, default now() | also the lease (see §6) |
| `last_error` | varchar(500), null | Telegram's `description` only, never the URL (it holds the token) |
| `created_at` | timestamptz, not null, default now() | |
| `sent_at` | timestamptz, null | |

Partial index on `next_attempt_at WHERE status = 'pending'` for the sender.

## 5. Enqueuing

- `app/services/notification_templates.py`: the texts per kind and language (en/ru/uz), formatting of
  money (`€44.97` style, order currency) and item counts with plural forms.
- `app/services/notification_service.py`: `enqueue(db, chat_id, kind, dedupe_key, text, button_path)`
  builds `reply_markup` from `WEBAPP_URL` and inserts with `ON CONFLICT (dedupe_key) DO NOTHING`.
  No commit, no network.
- `app/services/notification_events.py`: one function per event (`order_paid`, `order_claimed`,
  `order_picked_up`, `order_delivered`, `order_back_in_pool`, `order_expired`, `order_cancelled`,
  `refund_succeeded`, `refund_failed`). Each reads what it needs with column selects, finds the
  recipients, renders and enqueues.
- The services in the table in §3 call these **inside their existing transaction, before `commit`**, and
  only on the branch where the guarded UPDATE actually matched. A rolled-back action leaves no message;
  a replayed webhook finds the dedupe key taken.
- Refund events: `refund_succeeded` / `refund_failed` are enqueued where `payments.refund_status` changes
  to that value (`refund_payment` and `apply_refund_event`). Dedupe keys: `refund_succeeded:<order_id>`
  (one per order: refunds are always in full); `refund_failed:<order_id>:<ref>` where `<ref>` is the
  Stripe refund ID when there is one, otherwise the idempotency key of that attempt (Stripe refused
  before creating a refund). One failure therefore notifies once even if both the API answer and the
  `refund.failed` webhook report it, while a retried refund that fails again notifies again.

## 6. Sender

`notification_sender.run_sender(session_factory, interval)` is started in `lifespan` next to the reservation
sweeper when `NOTIFICATION_SEND_SECONDS > 0` and `TELEGRAM_BOT_TOKEN` is set; cancelled on shutdown.
Each tick:

1. **Lease**: `UPDATE notifications SET next_attempt_at = now() + 60 s WHERE id IN (SELECT id … WHERE
   status='pending' AND next_attempt_at <= now() ORDER BY id LIMIT 25 FOR UPDATE SKIP LOCKED)
   RETURNING …`, then commit. Two API processes never take the same row, and no transaction stays open
   during an HTTP call.
2. Send each with `POST https://api.telegram.org/bot<token>/sendMessage` (httpx, 10 s timeout), ~40 ms
   apart (Telegram allows about 30 messages per second per bot).
3. Record the outcome (its own short transaction):
   - `ok` → `sent`, `sent_at = now()`;
   - 403 (blocked, or the user never opened the bot) or 400 "chat not found" → `undeliverable`, no retry;
   - 429 → keep `pending`, `next_attempt_at = now() + retry_after`, and stop this batch (the rest of the
     leased rows get their lease back to now);
   - any other 4xx → `failed` (a bad message will not get better);
   - network error or 5xx → `attempts + 1`, `next_attempt_at = now() + 5 s × 3^(attempts-1)`; after 8
     attempts `failed`.
4. Once a day (first tick after 24 h in this process): delete `sent`/`undeliverable` rows older than 30 days.

Every per-message error is caught and logged; one broken message never stops the loop. If the process dies
mid-send, the lease expires after 60 s and the message is sent again: a rare duplicate is preferred to a
lost message.

## 7. Frontend

After a successful checkout, if `initDataUnsafe.user.allows_write_to_pm` is `false`, call
`Telegram.WebApp.requestWriteAccess()` (Telegram asks "Allow the bot to message you?"). Outside Telegram,
or when already allowed, nothing happens. No other UI.

Deep links (`/orders/42`, `/courier`, `/admin/orders/42`, `/cart`) already work: nginx falls back to
`index.html` and the router handles the path.

## 8. Configuration

- `NOTIFICATION_SEND_SECONDS` (2; `0` switches the sender off in this process).
- Uses existing `TELEGRAM_BOT_TOKEN` and `WEBAPP_URL`.
- Add to `.env.example`, `docker-compose.yml`, README, `docs/LAUNCH_GUIDE_RU.md`.

## 9. Testing

Backend (TDD, real Postgres):
- each event in §3: recipients (including "active only" and "not the releasing courier"), language
  fallback, text, button path, no button without an https `WEBAPP_URL`;
- a replayed Stripe event creates no second message; a rolled-back action leaves none;
- sender against a fake Telegram: 200 → sent; 403 → undeliverable; 429 → pause and stop the batch;
  5xx → retry with backoff, `failed` after 8 attempts; other 4xx → failed; lease prevents two ticks from
  taking one row; the token never appears in `last_error` or logs; daily cleanup;
- lifespan: the sender does not start without a token or with `NOTIFICATION_SEND_SECONDS=0`.

Frontend: `requestWriteAccess` is called after checkout only when writing is not allowed.

## 10. Out of scope

Admin history screen, per-user opt-out, quiet hours, message editing (one message per event, not a live
status message), notifications for catalog changes or low stock, channels other than Telegram.
