# Spec 9: Sellers and their products (stage B of the marketplace)

Status: **designed and approved by the owner (2026-10-04); implemented 2026-10-04, not deployed.**

## 1. Problem

The platform should host many independent sellers (Spec 8 §2 has the roadmap). Today products
belong to nobody: there is one shop, run by the owner's staff. This stage gives every product a
seller, lets a seller manage only their own products, and shows customers whose product they are
buying. Orders per seller (stage C) and money (stage D) come later.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| How a seller joins | **the owner adds them** in the admin panel (no applications, no self-sign-up) |
| Who delivers (stage C) | **the platform's couriers**, picking up at the seller's address |
| Money (stage D) | **through the platform**: customers pay the platform, which keeps a commission and pays sellers out |
| Several sellers in one cart | **no**: a cart holds one seller's products; adding another seller's product offers to empty the cart first |
| Where a seller works | **a new admin role, `seller`**, in the existing panel, limited to the seller's own products. Rejected: a separate `/seller/*` API and screen, which would duplicate the product editor, the largest part of the panel |
| Categories and attributes | **shared by the platform**: sellers pick them, only platform staff create or change them |

## 3. Data

New table `sellers` (`TimestampMixin`):

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | varchar(100), not null | the shop name customers see |
| `phone` | varchar(32), null | for the platform's staff and couriers (stage C) |
| `pickup_address` | varchar(500), null | where couriers collect orders; required by the API on create, null only for the migrated "Main shop" |
| `is_active` | bool, not null, default true | deactivated, never deleted |

- `products.seller_id`: FK `sellers.id` `ON DELETE RESTRICT`, **not null**, indexed.
- `admins.seller_id`: FK `sellers.id` `ON DELETE RESTRICT`, null; CHECK
  `ck_admins_seller_role`: `(role = 'seller') = (seller_id IS NOT NULL)`. One seller may have several
  accounts in the data model; the UI creates one per seller.
- `AdminRole.seller = "seller"` (the role column is a VARCHAR(20), no enum change needed).

Migration (after `f1a2b3c4d5e6`): create `sellers`; add `products.seller_id` nullable; if any
product exists, insert one seller `Main shop` (no address) and give it every product; make the
column not null; add `admins.seller_id` and the check. Downgrade deletes seller accounts
(`DELETE FROM admins WHERE role = 'seller'`), then drops the columns and the table.

## 4. Permissions and scope

New permissions in `app/core/permissions.py`:

| Permission | owner | manager | catalog_manager | dispatcher | accountant | viewer | seller |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `catalog.view` | ✓ | ✓ | ✓ | | | ✓ | ✓ own |
| `catalog.edit` (products, variants, photos, product texts) | ✓ | ✓ | ✓ | | | | ✓ own |
| **`taxonomy.edit`** (create/change categories and attributes) | ✓ | ✓ | ✓ | | | | |
| **`sellers.manage`** (add, edit, deactivate sellers) | ✓ | ✓ | | | | | |

Every other permission: the seller has none. `taxonomy.edit` takes over category and attribute
writes from `catalog.edit`; the three roles that had `catalog.edit` get it, so nothing changes for
them. `sellers.manage` needs no password re-entry: a seller account can do less than the
manager who creates it.

**Scope.** `AdminPrincipal` gains `seller_id` (null for platform staff and the internal token).
For a seller principal:

- `GET /internal/products` lists only their products; a `seller_id` filter is ignored.
- Any product, variant, image or product translation of another seller answers **404** (not 403:
  a seller cannot probe which ids exist). This covers `GET/PATCH /internal/products/{id}`,
  `POST /internal/variants`, `PATCH /internal/variants/{id}`, `POST /internal/products/{id}/images`,
  `PATCH/DELETE /internal/images/{id}`, `POST /internal/translations` with `entity_type=product`.
- `POST /internal/translations` with any other `entity_type` answers 403 (categories and
  attributes are platform data).
- `POST /internal/products` creates the product for their own seller; a `seller_id` naming
  another seller answers 404. `PATCH` cannot change `seller_id` (403).
- Categories and attributes stay readable (`GET`), so the product editor works.

Platform staff: `ProductCreate.seller_id` is required (400 without it); `ProductUpdate` may move a
product to another seller; `GET /internal/products?seller_id=` filters.

The checks live in one module, `app/services/seller_scope.py`, called by the catalog routes; the
services below them stay unaware of who is calling.

**Signing in.** A seller signs in like any admin (Mini App initData, Login Widget, password). An
account of a deactivated seller is refused with 403 `seller_inactive`, also on every request.
`GET /internal/me` adds `seller_id` and `seller_name`.

## 5. Managing sellers

`/internal/sellers` (all need `sellers.manage`, except `GET`, which also accepts `catalog.view` so
the product editor can offer a seller list; a seller principal gets only their own seller):

- `GET /internal/sellers` → `[{id, name, phone, pickup_address, is_active, accounts: [{id,
  telegram_id, display_name, is_active}], product_count}]`, ordered by name.
- `POST /internal/sellers {name, phone?, pickup_address, telegram_id, display_name}` creates the
  seller and its account (`role=seller`) in one transaction; a `telegram_id` that already has an
  admin row answers 409 `already_exists`.
- `PATCH /internal/sellers/{id} {name?, phone?, pickup_address?, is_active?}`.

The general admin endpoints refuse the seller role: `POST /internal/admins` with `role=seller`
and `PATCH /internal/admins/{id}` changing a role to or from `seller` answer 409
`seller_role_fixed`. Deactivating a seller's account there still works.

## 6. Storefront and cart

- `GET /catalog/products` and `/catalog/products/{id}` return `seller: {id, name}`;
  `GET /catalog/products?seller=<id>` filters. Products of a deactivated seller are not listed and
  their detail answers 404; their variants cannot be added to a cart (404).
- `GET/POST/PATCH/DELETE /cart/items` return `seller: {id, name} | null`, the seller of what is in
  the cart.
- `POST /cart/items` with a variant of another seller than the cart's answers **409
  `cart_other_seller`** and changes nothing. With `replace_cart: true` it empties the cart and adds
  the item in one transaction.
- When an unpaid order expires (Spec 4), its items go back to the cart only if the cart is empty
  or holds the same seller; otherwise they are dropped (the cart already has another seller's
  products). The expiry message stays as it is.

## 7. Admin panel (frontend)

- **Sellers** section (permission `sellers.manage`, icon `Store`): list with status and product
  count, a form to add a seller (shop name, phone, pickup address, the seller's Telegram ID and
  name), inline edit, activate/deactivate. On phones the bottom tab bar gets a seventh item for
  owners and managers; labels shrink with an ellipsis instead of wrapping.
- **Products**: the list shows each product's seller and, for platform staff, a seller filter.
  The new-product form has a seller select for platform staff; a seller does not see it. The
  editor of an existing product shows the seller (platform staff can change it).
- **Categories** screen: editing is gated by `taxonomy.edit` instead of `catalog.edit`.
- **Header**: a seller sees their shop name in place of the role label.
- **Admins** screen: the role select does not offer `seller`; seller accounts show "Seller · shop
  name" as plain text instead of a role select, and can still be deactivated.
- A seller lands on Catalog (the first section they may open). The launch rule of Spec 8 already
  sends them to `/admin`, since a seller is an admin.

## 8. Storefront (frontend)

- Product card: the seller's name under the product name.
- Product page: "Seller: name"; tapping it opens the catalog filtered to that seller
  (`/?seller=<id>`), with a removable chip showing the seller's name.
- Adding another seller's product: a confirmation (Telegram's `showConfirm`, `window.confirm`
  outside Telegram) "Your cart has products from {name}. Empty it and add this one?"; yes retries
  with `replace_cart: true`.

## 9. Out of scope

Orders and notifications per seller, the pickup address on the courier's card (stage C);
commission, balances, payouts (stage D); seller self-sign-up; per-seller SKU namespaces (SKUs stay
unique across the platform); a seller's own page or logo.

## 10. Testing

Backend (pytest against Postgres):

- scope, for each catalog route in §4: a seller reaches their own product and gets 404 for
  another seller's; category/attribute writes and non-product translations are refused;
- permissions matrix: every role, including `seller`, gets exactly its permissions;
- sellers API: create (seller + account), duplicate Telegram ID, edit, deactivate (storefront
  hides the products, the account is refused with `seller_inactive`), who may call it;
- admins API refuses the seller role;
- storefront: `seller` in list/detail, `?seller=` filter, inactive seller hidden;
- cart: `cart_other_seller`, `replace_cart`, `seller` in the cart, expiry restore across sellers;
- migration: existing products end up with `Main shop`, downgrade removes seller accounts.

Frontend (Vitest + MSW): Sellers screen (list, create, deactivate), seller select and filter in
the catalog for staff and their absence for a seller, the seller label in the header, storefront
seller label and filter, the cart confirmation and the retry with `replace_cart`.
