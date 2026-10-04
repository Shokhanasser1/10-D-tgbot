# Spec 8: Role-based launch (stage A of the marketplace)

Status: **designed and approved by the owner (2026-10-04), not implemented.**

## 1. Problem

Everyone who opens the bot lands in the shop. Couriers and admins reach their own screens through
small icons in the shop's top bar (a truck, a gear), and there is no way back: the admin panel has
no link to the shop, and the courier screen sits inside the shop's shell with its cart button. The
owner wants each role to open straight into its own screen, while an ordinary customer keeps
seeing only the shop, exactly as now.

## 2. Context: the marketplace roadmap

The owner wants many independent sellers (a marketplace). The project assumes a single shop
throughout (products have no owner, an order has one shipment picked up from one place), so the
work is split into stages, each with its own spec, plan and implementation:

| Stage | Scope |
|---|---|
| **A. Role-based launch** (this spec) | each role opens into its own screen; switching between roles and the shop |
| B. Sellers and their products | seller entity added by the owner, products belong to a seller, a seller panel limited to the seller's own products, the seller shown on the product card |
| C. Orders across sellers | a cart with several sellers is split per seller; each seller sees and marks their orders as packed; couriers pick up at each seller's address |
| D. Money | platform commission, payouts to sellers, reports |

Stage B adds the seller panel to the priority list in §3.

## 3. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| Where the role is decided | in the Mini App, from the two checks it already makes (`GET /courier/me`, `GET /internal/me`); **no backend change** |
| Who goes where on launch | admin → `/admin`; else courier → `/courier`; else the shop |
| Someone with both roles | admin panel first; the other role is one tap away |
| May a courier or admin shop? | yes: their own screen has a **Shop** button, and the shop keeps the truck and gear icons back |
| Bot greeting | unchanged (the `/start` button still says "Open shop"; the Mini App routes by role) |

Rejected: a new `GET /me` endpoint listing roles (saves one parallel request but needs a backend
deploy), and per-chat menu buttons set by the bot (`setChatMenuButton`) that point couriers at
`/courier` (they must be reset on every role change, and old buttons stay in the chat with stale
URLs, as happened with the dead tunnel address on 2026-10-04).

## 4. Launch rule

The rule runs **once per page load** (each time the Mini App is opened), and only when the app was
opened at the bare root `/`.

- Opened at any other path (a notification button to `/courier`, `/orders/12`,
  `/admin/orders/5`, …): no redirect, ever, for that page load.
- Opened at `/`: the index route shows a full-screen skeleton (not the shop's top bar) while both
  role checks run in parallel, then:
  - `/internal/me` succeeded → replace the location with `/admin`;
  - else `/courier/me` returned a profile → replace with `/courier`;
  - else (both say "no role": 401/403 from `/internal/me`, `null` from `/courier/me`) → the shop.
- A check that **fails** (network error, 5xx), or has not answered after **3 seconds**, counts as
  "no role", and the decision is made from what is known: a courier whose admin check hangs still
  reaches `/courier` after 3 s. Once the shop is shown, a late answer never redirects: nothing
  yanks a customer off the screen they are using. The role screens stay
  reachable through the icons, which appear when the checks finish.
- After the rule has run, navigating back to `/` (the **Shop** button, a deactivated courier
  being sent to `/`) just shows the shop.
- The redirect uses `replace`, so Telegram's back gesture does not return to the skeleton.

Who counts as an admin is whatever `/internal/me` accepts today: an active admin of any of the six
roles. An admin who must change their password lands in the panel's forced profile screen, as now.
An inactive admin or courier gets 403 and is treated as a customer.

The same rule applies in a browser: an admin with a session cookie who opens `/` goes to `/admin`.

## 5. Switching between screens

| Screen | Switch controls |
|---|---|
| Shop (`AppShell`) | unchanged: truck icon for couriers, gear icon for admins |
| Courier (`/courier`) | moves out of `AppShell` into its own small shell: a top bar with a **Shop** button, and an **Admin** button only for admins (the screen keeps its own title); no cart, no orders icon |
| Admin panel (`AdminLayout`) | the header (next to the language selector) gets a **Shop** icon button, and a **Courier** icon button only for couriers. Not in the nav: on phones it is a bottom tab bar that is already full |

Each button appears only once its check has answered "yes"; a failed check hides it.

The admin chunk reads the courier check through the existing `useCourierProfile` hook; the courier
shell reads the admin check through `useIsAdmin` (`features/admin/entry.ts`, already in the main
chunk). Both are cached by react-query (5 min stale time), so the launch rule, the icons and the
switch buttons share one request per check.

Strings, in en/ru/uz: a new `nav.shop` ("Shop" / "Магазин" / "Do'kon"); the courier and admin
buttons reuse `courier.nav` and `admin.open`.

## 6. Out of scope

- Any backend or bot change; the `/start` greeting text.
- The seller panel (stage B).
- Remembering the last screen a person used: every launch at `/` follows §4.

## 7. Testing

Frontend (Vitest + Testing Library + MSW), launch rule:

- customer (403 from `/courier/me`, 401 from `/internal/me`) → shop, no redirect;
- courier only → `/courier`; admin only → `/admin`; both → `/admin`;
- `/internal/me` answers 500 and the courier check says yes → `/courier`; both fail → shop;
- checks slower than 3 s → shop, and no redirect when they answer later;
- opened at `/orders/1` or `/courier` → no redirect;
- after a launch redirect to `/courier`, **Shop** shows the shop and stays there;
- the skeleton, not the shop, is shown while the checks run.

Switch controls: the courier shell shows **Shop**, shows **Admin** only for admins, and has no
cart; the admin header shows **Shop**, and **Courier** only for couriers. The existing locale
parity test covers the new string.

Manual, after `npm --prefix frontend run deploy:pages`: open the bot in Telegram from the owner's
account (an admin) → the admin panel; **Shop** → the shop; gear → back to the panel. A test
account that is a courier → the courier screen. A plain account → the shop as before.

## 8. Docs

`README.md` ("Couriers & tracking", "Admin panel") and `docs/PROJECT_STATE.md` describe the
launch rule and the switch buttons.
